import base64
import hashlib
import time
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import pytest
from jose import jwt
from passlib.hash import sha256_crypt

from src.identity.services.auth_service import AuthService
from src.identity.services.sso.github_oauth import GitHubOAuthProvider
from src.identity.services.sso.google_oauth import GoogleOAuthProvider
from src.shared.core.security import create_refresh_token
from src.shared.errors import TokenRevoked, UnauthorizedError

SECRET = "test-secret-key-for-testing"


class FakeUser:
    id = 1
    is_active = True
    is_verified = True
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

    async def get_by_oauth_sub(self, provider, subject):
        return None

    async def email_exists(self, email):
        return self.user is not None

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

    async def mget(self, *keys):
        return tuple(self.data.get(k) for k in keys)

    async def setex(self, key, ttl, value):
        self.data[key] = value
        return True

    async def delete(self, key):
        self.data.pop(key, None)
        return 1

    async def delete_many(self, *keys):
        for k in keys:
            self.data.pop(k, None)
        return len(keys)

    async def eval(self, script, numkeys, *args):
        """Model the three scripts auth_service actually runs.

        A real EVAL runs Lua; this cannot. Returning one canned value for every
        script is a lie that hides shape changes — the scripts in auth_service
        return different types (an int status from the refresh rotation, a
        [state, verifier] pair from the OAuth state consume, an int 1 from the
        OAuth state create) and take different argument shapes. A call site that
        unpacked the wrong one, or passed keys where it should have passed
        values, would pass here and fail in production.

        So each known script is matched on its own body and then *modelled*
        against the double's own store, which is what the caller actually
        depends on. Dispatch is on script text, not on argument count: two of
        these scripts are called with the same `numkeys` and the same two keys,
        and only their bodies differ.
        """
        body = str(script)

        if "SETEX" in body:
            # _INIT_OAUTH_STATE_LUA: SETEX KEYS[1] ARGV[2], SETEX KEYS[2]
            # ARGV[3], with the shared TTL in ARGV[1].
            ttl, value_a, value_b = str(args[2]), str(args[3]), str(args[4])
            assert ttl.isdigit(), f"Lua would reject a non-numeric TTL: {ttl!r}"
            self.data[str(args[0])] = value_a
            self.data[str(args[1])] = value_b
            return 1

        if numkeys == 2 and any(str(k).startswith("oauth:state:") for k in args):
            # _CONSUME_OAUTH_STATE_LUA: read both, delete both, report a
            # missing key as falsy (Lua cannot put nil in a table).
            state_key, pkce_key = str(args[0]), str(args[1])
            state = self.data.get(state_key)
            verifier = self.data.get(pkce_key)
            if state is not None or verifier is not None:
                self.data.pop(state_key, None)
                self.data.pop(pkce_key, None)
            return (state, verifier)

        return self.eval_result


@contextmanager
def fake_redis(redis: FakeRedis):
    """Point both redis consumers at the same double.

    Refresh-family revocation lives in its own module (shared by AuthService and
    ProfileService), so it holds its own `redis_client` reference. Both must be
    patched or the revocation assertions would silently read a real Redis.
    """
    with ExitStack() as stack:
        stack.enter_context(patch("src.identity.services.auth_service.redis_client", redis))
        stack.enter_context(patch("src.identity.services.session_revocation.redis_client", redis))
        yield redis


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
        with fake_redis(redis):
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
        with fake_redis(redis):
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
        with fake_redis(redis):
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
        with fake_redis(redis):
            result = await svc.refresh(legacy)
        new = jwt.decode(result.refresh_token, SECRET, algorithms=["HS256"])
        assert new["sid"] and new["jti"]
        assert any(k.startswith("refresh:session:") for k in redis.data)

    @patch("src.shared.core.security.settings.SECRET_KEY", SECRET)
    @patch("src.shared.core.security.settings.ALGORITHM", "HS256")
    async def test_login_stores_refresh_session(self):
        redis = FakeRedis()
        svc = _svc(FakeUser())
        with fake_redis(redis):
            token = await svc.login("test@example.com", "testpass123")
        sid = jwt.decode(token.refresh_token, SECRET, algorithms=["HS256"])["sid"]
        assert f"refresh:session:{sid}" in redis.data

    @patch("src.shared.core.security.settings.SECRET_KEY", SECRET)
    @patch("src.shared.core.security.settings.ALGORITHM", "HS256")
    async def test_deactivated_user_cannot_refresh(self):
        class Inactive(FakeUser):
            is_active = False

        redis = FakeRedis()
        svc = _svc(Inactive())
        token = create_refresh_token({"sub": "1"})
        with fake_redis(redis):
            with pytest.raises(UnauthorizedError):
                await svc.refresh(token)


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

    async def test_oauth_init_writes_state_and_verifier_in_one_round_trip(self):
        """A split write can leave a state with no verifier, and PKCE then
        silently stops existing.

        Two separate SETEX calls meant a transient Redis error between them left
        `oauth:state:{state}` stored and `oauth:pkce:{state}` absent. The
        callback resolves a missing verifier to `None` and calls
        `authenticate(code, code_verifier=None)` — a token exchange with no PKCE
        at all, after having advertised a code_challenge to the provider.

        Nothing looks wrong: the code is single-use and short-lived, so it
        surfaces as one sign-in that is slightly more forgeable and nothing
        else. The single round trip is the fix, so the round trip is what is
        pinned — not merely that both keys happen to be present, which the
        split version also satisfied.
        """

        class CountingRedis(FakeRedis):
            """Counts every round trip, not just EVAL.

            Counting only `eval` would report "0 round trips" for a version that
            used two plain SETEX calls, which reads like a measurement rather
            than the answer it is.
            """

            def __init__(self):
                super().__init__()
                self.ops = []

            async def setex(self, key, ttl, value):
                self.ops.append(f"SETEX {key}")
                return await super().setex(key, ttl, value)

            async def eval(self, script, numkeys, *args):
                kind = "EVAL:init" if "SETEX" in str(script) else f"EVAL:{numkeys}k"
                self.ops.append(kind)
                return await super().eval(script, numkeys, *args)

        class FakeProvider:
            def is_configured(self):
                return True

            def get_authorization_url(self, state, code_challenge=None):
                return f"https://provider/auth?state={state}"

        redis = CountingRedis()
        with patch("src.identity.services.auth_service.redis_client", redis), patch(
            "src.identity.services.sso.SSOProviderRegistry.get", return_value=FakeProvider()
        ):
            _, state = await _svc().oauth_init("google")

        assert redis.ops == ["EVAL:init"], (
            "oauth_init must write state and PKCE verifier in one atomic round trip; "
            f"got {redis.ops}"
        )
        # Both keys present, from that one call.
        assert redis.data[f"oauth:state:{state}"] == "1"
        assert redis.data[f"oauth:pkce:{state}"]

    async def test_oauth_init_leaves_nothing_behind_when_redis_fails(self):
        """A half-written state is worse than none: it is a valid state with no
        verifier, which is the exact shape that disables PKCE."""
        import src.identity.services.auth_service as auth_mod

        class ExplodingRedis(FakeRedis):
            async def eval(self, script, numkeys, *args):
                raise ConnectionError("upstream unavailable")

        class FakeProvider:
            def is_configured(self):
                return True

            def get_authorization_url(self, state, code_challenge=None):
                return f"https://provider/auth?state={state}"

        redis = ExplodingRedis()
        with patch.object(auth_mod, "redis_client", redis), patch(
            "src.identity.services.sso.SSOProviderRegistry.get", return_value=FakeProvider()
        ):
            with pytest.raises(ConnectionError):
                await _svc().oauth_init("google")

        assert redis.data == {}, "a failed init must not leave a partial state behind"

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
