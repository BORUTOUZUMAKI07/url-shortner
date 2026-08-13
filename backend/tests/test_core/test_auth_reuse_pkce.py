import base64
import hashlib
import time
from unittest.mock import patch

import pytest
from jose import jwt
from passlib.hash import sha256_crypt

from src.identity.services.auth_service import AuthService
from src.identity.services.sso.github_oauth import GitHubOAuthProvider
from src.identity.services.sso.google_oauth import GoogleOAuthProvider
from src.shared.core.security import create_refresh_token
from src.shared.errors import TokenRevoked

SECRET = "test-secret-key-for-testing"


class FakeUser:
    id = 1
    # Tests run with the fast sha256_crypt pwd_context (tests/conftest.py
    # `fast_password_hashing`), so the fake's hash must use that scheme too.
    password_hash = sha256_crypt.using(rounds=1000).hash("testpass123")


class FakeUserRepo:
    def __init__(self, user=None):
        self.user = user

    async def get(self, user_id):
        return self.user

    async def get_by_email(self, email):
        return self.user

    async def create(self, **kwargs):
        return None

    async def update(self, *args, **kwargs):
        return None


class FakeRedis:
    """In-memory Redis double; eval returns a scriptable result so we can drive
    the reuse-detection branches (1=rotated, 0=reuse, -1=missing session)."""

    def __init__(self):
        self.data = {}
        self.eval_result = 1

    async def get(self, key):
        return self.data.get(key)

    async def setex(self, key, ttl, value):
        self.data[key] = value
        return True

    async def delete(self, key):
        self.data.pop(key, None)
        return 1

    async def eval(self, script, numkeys, *args):
        return self.eval_result


def _svc(user=None) -> AuthService:
    return AuthService(user_repo=FakeUserRepo(user), workspace_repo=FakeUserRepo())


class TestRefreshReuseDetection:
    @patch("src.shared.core.security.settings.SECRET_KEY", SECRET)
    @patch("src.shared.core.security.settings.ALGORITHM", "HS256")
    async def test_refresh_rotates_and_preserves_sid(self):
        redis = FakeRedis()
        svc = _svc(FakeUser())
        old = create_refresh_token({"sub": "1"})
        old_sid = jwt.decode(old, SECRET, algorithms=["HS256"])["sid"]
        with patch("src.identity.services.auth_service.redis_client", redis):
            result = await svc.refresh(old)
        new = jwt.decode(result.refresh_token, SECRET, algorithms=["HS256"])
        assert new["sid"] == old_sid
        assert new["jti"] != jwt.decode(old, SECRET, algorithms=["HS256"])["jti"]
        # old token is blacklisted so it can never be used again
        assert f"jwt:blacklist:{old}" in redis.data

    @patch("src.shared.core.security.settings.SECRET_KEY", SECRET)
    @patch("src.shared.core.security.settings.ALGORITHM", "HS256")
    async def test_refresh_reuse_detected_revokes_family(self):
        redis = FakeRedis()
        svc = _svc(FakeUser())
        token = create_refresh_token({"sub": "1"})
        sid = jwt.decode(token, SECRET, algorithms=["HS256"])["sid"]
        redis.data[f"refresh:session:{sid}"] = "{}"
        redis.eval_result = 0  # Lua says: presented jti matches neither current nor grace prev
        with patch("src.identity.services.auth_service.redis_client", redis):
            with pytest.raises(TokenRevoked):
                await svc.refresh(token)
        assert redis.data.get("refresh:revoked:1") == "1"

    @patch("src.shared.core.security.settings.SECRET_KEY", SECRET)
    @patch("src.shared.core.security.settings.ALGORITHM", "HS256")
    async def test_refresh_missing_session_rejects_without_family_revoke(self):
        redis = FakeRedis()
        svc = _svc(FakeUser())
        token = create_refresh_token({"sub": "1"})
        redis.eval_result = -1  # no session record for this sid
        with patch("src.identity.services.auth_service.redis_client", redis):
            with pytest.raises(TokenRevoked):
                await svc.refresh(token)
        assert "refresh:revoked:1" not in redis.data

    @patch("src.shared.core.security.settings.SECRET_KEY", SECRET)
    @patch("src.shared.core.security.settings.ALGORITHM", "HS256")
    async def test_refresh_legacy_token_upgrades_to_detection(self):
        redis = FakeRedis()
        svc = _svc(FakeUser())
        # A pre-session-metadata token (issued by the old code) must still rotate.
        legacy = jwt.encode(
            {"sub": "1", "type": "refresh", "exp": int(time.time()) + 3600},
            SECRET,
            algorithm="HS256",
        )
        with patch("src.identity.services.auth_service.redis_client", redis):
            result = await svc.refresh(legacy)
        new = jwt.decode(result.refresh_token, SECRET, algorithms=["HS256"])
        assert new["sid"] and new["jti"]
        assert any(k.startswith("refresh:session:") for k in redis.data)

    @patch("src.shared.core.security.settings.SECRET_KEY", SECRET)
    @patch("src.shared.core.security.settings.ALGORITHM", "HS256")
    async def test_login_stores_refresh_session(self):
        redis = FakeRedis()
        svc = _svc(FakeUser())
        with patch("src.identity.services.auth_service.redis_client", redis):
            token = await svc.login("test@example.com", "testpass123")
        sid = jwt.decode(token.refresh_token, SECRET, algorithms=["HS256"])["sid"]
        assert f"refresh:session:{sid}" in redis.data


class TestOAuthPKCE:
    @patch("src.shared.core.security.settings.SECRET_KEY", SECRET)
    @patch("src.shared.core.security.settings.ALGORITHM", "HS256")
    async def test_oauth_init_stores_verifier_and_sends_s256_challenge(self):
        class FakeProvider:
            def __init__(self):
                self.last_challenge = None

            def is_configured(self):
                return True

            def get_authorization_url(self, state, code_challenge=None):
                self.last_challenge = code_challenge
                return f"https://provider/auth?state={state}"

        provider = FakeProvider()
        redis = FakeRedis()
        svc = _svc()
        with patch("src.identity.services.auth_service.redis_client", redis), patch(
            "src.identity.services.sso.SSOProviderRegistry.get", return_value=provider
        ):
            url, state = await svc.oauth_init("google")

        verifier = redis.data[f"oauth:pkce:{state}"]
        assert verifier
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode("ascii")).digest()
        ).rstrip(b"=").decode("ascii")
        assert provider.last_challenge == expected
        assert f"oauth:state:{state}" in redis.data
        assert state in url

    def test_google_authorization_url_has_pkce_and_forced_consent(self):
        url = GoogleOAuthProvider().get_authorization_url("state", code_challenge="challenge123")
        assert "code_challenge=challenge123" in url
        assert "code_challenge_method=S256" in url
        assert "prompt=consent+select_account" in url

    def test_github_authorization_url_has_pkce_and_account_picker(self):
        url = GitHubOAuthProvider().get_authorization_url("state", code_challenge="challenge123")
        assert "code_challenge=challenge123" in url
        assert "code_challenge_method=S256" in url
        assert "prompt=select_account" in url

    def test_authorization_url_without_challenge_has_no_pkce_params(self):
        url = GoogleOAuthProvider().get_authorization_url("state")
        assert "code_challenge" not in url
