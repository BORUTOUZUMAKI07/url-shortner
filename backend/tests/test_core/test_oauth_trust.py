"""Regression tests for OAuth identity binding.

The bug these cover: `GitHubOAuthProvider.get_user_info` used to return
``verified_email = email is not None``, i.e. "GitHub gave us an address, so it
must be verified". GitHub allows an account to hold an address it has NOT
verified, and ``auth_service.oauth_callback`` then matched accounts *by email*.
Together that is an account takeover: point your own GitHub account at the
victim's address, sign in, and the victim's session is yours.

The fix has two halves, and both are asserted here:
  1. the provider reports GitHub's real ``verified`` flag; and
  2. the service establishes identity by provider subject, treating a missing
     ``verified_email`` claim as unverified rather than as permissive.
"""

import base64
import hashlib
from contextlib import ExitStack, contextmanager
from unittest.mock import patch

import pytest

from src.identity.services.auth_service import AuthService
from src.identity.services.sso.github_oauth import GitHubOAuthProvider
from src.shared.errors import OAuthFailed, UnauthorizedError

SECRET = "test-secret-key-for-testing"


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _FakeAsyncClient:
    """Serves canned /user and /user/emails payloads to the provider."""

    def __init__(self, user_payload, emails_payload, emails_status=200):
        self.user_payload = user_payload
        self.emails_payload = emails_payload
        self.emails_status = emails_status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        if url.endswith("/user/emails"):
            return _Resp(self.emails_status, self.emails_payload)
        return _Resp(200, self.user_payload)

    async def post(self, *args, **kwargs):  # pragma: no cover - unused here
        raise AssertionError("token exchange should not run in this test")


@contextmanager
def _github_api(user_payload, emails_payload, emails_status=200):
    client = _FakeAsyncClient(user_payload, emails_payload, emails_status)
    with patch(
        "src.identity.services.sso.github_oauth.httpx.AsyncClient",
        return_value=client,
    ):
        yield


class TestGitHubEmailVerification:
    async def test_prefers_verified_primary_email(self):
        with _github_api(
            {"id": 1, "login": "octocat", "email": None},
            [
                {"email": "unverified@evil.test", "primary": True, "verified": False},
                {"email": "real@example.com", "primary": False, "verified": True},
            ],
        ):
            info = await GitHubOAuthProvider().get_user_info("tok")

        # The unverified address was the primary one, but it must lose.
        assert info["email"] == "real@example.com"
        assert info["verified_email"] is True
        assert info["id"] == "1"

    async def test_verified_primary_wins_over_other_verified(self):
        with _github_api(
            {"id": 7},
            [
                {"email": "other@example.com", "primary": False, "verified": True},
                {"email": "main@example.com", "primary": True, "verified": True},
            ],
        ):
            info = await GitHubOAuthProvider().get_user_info("tok")
        assert info["email"] == "main@example.com"
        assert info["verified_email"] is True

    async def test_no_verified_email_reports_unverified(self):
        """The takeover primitive: an address that exists but is unverified."""
        with _github_api(
            {"id": 9, "email": "victim@example.com"},
            [{"email": "victim@example.com", "primary": True, "verified": False}],
        ):
            info = await GitHubOAuthProvider().get_user_info("tok")

        assert info["email"] is None
        assert info["verified_email"] is False

    async def test_no_email_list_reports_unverified(self):
        with _github_api({"id": 9, "email": None}, [], emails_status=403):
            info = await GitHubOAuthProvider().get_user_info("tok")
        assert info["verified_email"] is False

    async def test_public_email_on_user_is_not_treated_as_verified(self):
        """/user's `email` is only populated for public addresses and is still
        not proof of verification - the emails list is the authority."""
        with _github_api(
            {"id": 9, "email": "public@example.com"},
            [{"email": "public@example.com", "primary": True, "verified": False}],
        ):
            info = await GitHubOAuthProvider().get_user_info("tok")
        assert info["email"] is None
        assert info["verified_email"] is False


class _Repo:
    def __init__(self, user=None, by_sub=None, email_exists=False):
        self.user = user
        self.by_sub = by_sub
        self._email_exists = email_exists
        self.created: list[dict] = []
        self.updates: list[dict] = []

    async def get(self, user_id):
        return self.user

    async def get_by_email(self, email):
        return self.user if self._email_exists else None

    async def get_by_oauth_sub(self, provider, subject):
        return self.by_sub

    async def email_exists(self, email):
        return self._email_exists

    async def create(self, **kwargs):
        self.created.append(kwargs)
        return _User(**{k: v for k, v in kwargs.items() if hasattr(_User(), k)})

    async def update(self, user_id, **kwargs):
        self.updates.append(kwargs)
        return None


class _WorkspaceRepo:
    def __init__(self):
        self.created: list[int] = []

    async def create_default(self, user_id):
        self.created.append(user_id)


class _Provider:
    name = "github"

    def is_configured(self):
        return True

    def get_authorization_url(self, state, code_challenge=None):
        return f"https://github.test/auth?state={state}"

    async def authenticate(self, code, code_verifier=None):
        return self.user_info


class _User:
    def __init__(self, **kw):
        self.id = 1
        self.email = "existing@example.com"
        self.is_active = True
        self.is_verified = True
        self.oauth_provider = None
        self.oauth_avatar_url = None
        self.google_id = None
        self.github_id = None
        for k, v in kw.items():
            setattr(self, k, v)


@contextmanager
def _callback_env(repo, user_info):
    """Wire AuthService with valid state/PKCE already in the fake Redis."""
    from tests.test_core.test_auth_reuse_pkce import FakeRedis, fake_redis

    redis = FakeRedis()
    state = "st"
    verifier = "verifier"
    redis.data[f"oauth:state:{state}"] = "1"
    redis.data[f"oauth:pkce:{state}"] = verifier
    provider = _Provider()
    provider.user_info = user_info
    svc = AuthService(user_repo=repo, workspace_repo=_WorkspaceRepo())
    with fake_redis(redis), ExitStack() as stack:
        stack.enter_context(
            patch("src.identity.services.sso.SSOProviderRegistry.get", return_value=provider)
        )
        stack.enter_context(
            patch("src.shared.core.security.settings.SECRET_KEY", SECRET),
        )
        stack.enter_context(
            patch("src.shared.core.security.settings.ALGORITHM", "HS256"),
        )
        yield svc


def _info(**kw):
    base = {"id": "555", "email": "new@example.com", "verified_email": True, "picture": None}
    base.update(kw)
    return base


class TestOAuthCallbackTrust:
    async def test_rejects_unverified_email(self):
        repo = _Repo()
        with _callback_env(repo, _info(verified_email=False)) as svc:
            with pytest.raises(OAuthFailed):
                await svc.oauth_callback("github", "code", "st")
        assert repo.created == []

    async def test_rejects_missing_verified_claim(self):
        """`is not True`, not `is False` - a provider that omits the claim must
        not be able to mint a login."""
        info = _info()
        info.pop("verified_email")
        repo = _Repo()
        with _callback_env(repo, info) as svc:
            with pytest.raises(OAuthFailed):
                await svc.oauth_callback("github", "code", "st")
        assert repo.created == []

    async def test_rejects_missing_subject(self):
        repo = _Repo()
        with _callback_env(repo, _info(id="")) as svc:
            with pytest.raises(OAuthFailed):
                await svc.oauth_callback("github", "code", "st")

    async def test_identity_resolved_by_subject_not_email(self):
        """The provider subject is the link. An address that happens to match an
        unrelated account must not be used to find the caller."""
        repo = _Repo(user=None, by_sub=_User(id=42, github_id="555"), email_exists=True)
        with _callback_env(repo, _info()) as svc:
            token = await svc.oauth_callback("github", "code", "st")
        assert token.access_token
        # No new account, and the already-linked subject was not rewritten.
        assert repo.created == []
        assert all("github_id" not in u for u in repo.updates)

    async def test_refuses_to_merge_into_other_providers_account(self):
        """An address that exists on a Google-bound account must not be
        claimable by a GitHub identity."""
        repo = _Repo(
            user=_User(id=42, oauth_provider="google", google_id="g-1"),
            by_sub=None,
            email_exists=True,
        )
        with _callback_env(repo, _info()) as svc:
            with pytest.raises(OAuthFailed):
                await svc.oauth_callback("github", "code", "st")
        assert repo.updates == []

    async def test_links_subject_onto_unbound_account_with_same_email(self):
        repo = _Repo(user=_User(id=42), by_sub=None, email_exists=True)
        with _callback_env(repo, _info()) as svc:
            await svc.oauth_callback("github", "code", "st")
        assert repo.updates[0]["github_id"] == "555"
        assert repo.updates[0]["oauth_provider"] == "github"

    async def test_new_account_created_with_provider_subject(self):
        repo = _Repo(user=None, by_sub=None, email_exists=False)
        with _callback_env(repo, _info(email="new@example.com")) as svc:
            await svc.oauth_callback("github", "code", "st")
        created = repo.created[0]
        assert created["github_id"] == "555"
        assert created["oauth_provider"] == "github"
        assert created["is_verified"] is True
        # A random, unrecoverable password: the account is OAuth-only.
        assert created["password_hash"] != "new@example.com"

    async def test_deactivated_user_cannot_sign_in_via_oauth(self):
        repo = _Repo(user=_User(id=42, is_active=False), by_sub=None, email_exists=True)
        with _callback_env(repo, _info()) as svc:
            with pytest.raises(UnauthorizedError):
                await svc.oauth_callback("github", "code", "st")
