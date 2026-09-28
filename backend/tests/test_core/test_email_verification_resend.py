"""Require-email-verification readiness.

Two pieces make flipping REQUIRE_EMAIL_VERIFICATION survivable:

1. The refresh endpoint enforces the same gate as login. Without it, anyone who
   logged in before the flag was enabled keeps an immortal session via refresh
   — the policy would be a lie for every pre-existing session.

2. `resend_verification_for_email` — an *unauthenticated* resend modeled on
   forgot_password. The login gate that refuses access to an unverified user
   also bars them from the authenticated resend endpoint, so without this the
   only recovery is the single signup mail (24h token) — gone within a day. It
   must not reveal whether an address exists (same contract as forgot_password).
"""
from contextlib import ExitStack, contextmanager
from unittest.mock import AsyncMock, patch

import pytest

from src.identity.services.auth_service import AuthService
from src.shared.errors import UnauthorizedError

SECRET = "test-secret-key-for-testing"


class FakeUser:
    id = 7
    is_active = True
    is_verified = False
    email = "unverified@example.com"


class FakeRepo:
    """Both user and workspace stand-in: `get`/`get_by_email` return the user."""

    def __init__(self, user=None):
        self.user = user

    async def get(self, user_id):
        return self.user

    async def get_by_email(self, email):
        return self.user

    async def create(self, **kwargs):
        return self.user

    async def email_exists(self, email):
        return self.user is not None


class _Redis:
    """In-memory double for the gate tests.

    Rotation semantics live in test_auth_reuse_pkce (this double's eval returns
    a canned 1 because the gate tests do not assert on rotation behaviour); what
    this double must model faithfully is the get/blacklist/session surface the
    refresh path touches before and after the gate.
    """

    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def setex(self, key, ttl, value):
        self.data[key] = value

    async def delete(self, key):
        self.data.pop(key, None)

    async def eval(self, script, numkeys, *args):
        return 1


def _svc(user=None) -> AuthService:
    return AuthService(user_repo=FakeRepo(user), workspace_repo=FakeRepo())


@contextmanager
def _patched(redis, *, require_verification=None):
    """Point both redis consumers at the same double (auth_service AND
    session_revocation hold their own references) plus the flag under test."""
    patches = [
        patch("src.identity.services.auth_service.redis_client", redis),
        patch("src.identity.services.session_revocation.redis_client", redis),
    ]
    if require_verification is not None:
        patches.append(
            patch(
                "src.identity.services.auth_service.settings.REQUIRE_EMAIL_VERIFICATION",
                require_verification,
            )
        )
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        yield redis


class TestResendVerificationForEmail:
    async def test_unknown_email_answers_generically_and_sends_nothing(self):
        send = AsyncMock()
        with patch("src.identity.services.auth_service.EmailService.send_verification_email", send):
            result = await _svc().resend_verification_for_email("ghost@example.com")
        assert result is True
        send.assert_not_awaited()

    async def test_verified_address_answers_generically_and_sends_nothing(self):
        user = FakeUser()
        user.is_verified = True
        send = AsyncMock()
        with patch("src.identity.services.auth_service.EmailService.send_verification_email", send):
            result = await _svc(user).resend_verification_for_email(user.email)
        assert result is True
        send.assert_not_awaited()

    async def test_smtp_unconfigured_signals_failure(self):
        # The only honest answer when mail cannot go out is "this server cannot
        # send mail" — a 503 the frontend can show instead of the default
        # "check your inbox" that would promise a mail that can never arrive
        # anywhere.
        with patch("src.identity.services.auth_service.EmailService.is_configured", return_value=False):
            result = await _svc(FakeUser()).resend_verification_for_email("unverified@example.com")
        assert result is False

    async def test_smtp_configured_emails_once_with_token(self):
        send = AsyncMock()
        with patch("src.identity.services.auth_service.EmailService.is_configured", return_value=True), \
             patch("src.identity.services.auth_service.EmailService.send_verification_email", send):
            result = await _svc(FakeUser()).resend_verification_for_email("unverified@example.com")
        assert result is True
        send.assert_awaited_once()
        emailed_address, token = send.call_args.args
        assert emailed_address == "unverified@example.com"
        assert token


class TestRefreshVerificationGate:
    @patch("src.shared.core.security.settings.SECRET_KEY", SECRET)
    @patch("src.shared.core.security.settings.ALGORITHM", "HS256")
    async def test_refresh_rejects_unverified_user_when_required(self):
        from src.shared.core.security import create_refresh_token

        token = create_refresh_token({"sub": "7"})
        with _patched(_Redis(), require_verification=True):
            with pytest.raises(UnauthorizedError):
                await _svc(FakeUser()).refresh(token)

    @patch("src.shared.core.security.settings.SECRET_KEY", SECRET)
    @patch("src.shared.core.security.settings.ALGORITHM", "HS256")
    async def test_refresh_allows_verified_user_when_required(self):
        from src.shared.core.security import create_refresh_token

        user = FakeUser()
        user.is_verified = True
        token = create_refresh_token({"sub": "7"})
        with _patched(_Redis(), require_verification=True):
            result = await _svc(user).refresh(token)
        assert result.access_token
        assert result.refresh_token

    @patch("src.shared.core.security.settings.SECRET_KEY", SECRET)
    @patch("src.shared.core.security.settings.ALGORITHM", "HS256")
    async def test_refresh_allows_unverified_user_when_flag_off(self):
        """Default-off must keep working for the existing (unverified) users."""
        from src.shared.core.security import create_refresh_token

        token = create_refresh_token({"sub": "7"})
        with _patched(_Redis()):
            result = await _svc(FakeUser()).refresh(token)
        assert result.access_token
