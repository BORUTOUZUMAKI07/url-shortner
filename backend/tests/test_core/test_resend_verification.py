"""Resending the verification email must be honest about whether mail went out.

The profile page renders an "Email not verified" card. Before this endpoint
existed the *only* way out was the single mail sent at signup, so a lost or
expired (24h) link left the user permanently stuck.

The subtle part is the failure mode. `EmailService._send` returns silently when
SMTP is unconfigured (it logs "Would send email to...") and swallows every send
exception, so a naive "resend" endpoint would answer 200 and tell the user to
check their inbox for a message that was never going to arrive. `resend_verification`
therefore returns whether the mail was actually handed off, and the route turns
that into a 503.
"""

import pytest

from src.identity.services import auth_service as auth_module
from src.identity.services.auth_service import AuthService
from src.identity.services.email_service import EmailService


class _User:
    def __init__(self, email="me@example.com", is_verified=False, uid=1):
        self.id = uid
        self.email = email
        self.is_verified = is_verified


class _Repo:
    async def get(self, user_id):
        return None

    async def get_by_email(self, email):
        return None


class _Unused:
    def __getattr__(self, name):
        async def _noop(*a, **k):
            return None

        return _noop


def _service():
    return AuthService(
        user_repo=_Repo(),
        workspace_repo=_Unused(),
        audit=_Unused(),
    )


@pytest.fixture
def sent(monkeypatch):
    """Record every verification email instead of sending one."""
    calls: list[tuple[str, str]] = []

    async def _fake(email, token):
        calls.append((email, token))

    monkeypatch.setattr(EmailService, "send_verification_email", _fake)
    monkeypatch.setattr(EmailService, "is_configured", classmethod(lambda cls: True))
    return calls


class TestResendVerification:
    async def test_unverified_user_gets_a_fresh_link(self, sent):
        svc = _service()
        assert await svc.resend_verification(_User()) is True
        assert len(sent) == 1
        assert sent[0][0] == "me@example.com"

    async def test_regenerates_a_usable_token(self, sent):
        """The resent link must actually verify, not be a stale/garbage token."""
        svc = _service()
        await svc.resend_verification(_User())
        payload = auth_module.decode_token(sent[0][1])
        assert payload["sub"] == "me@example.com"
        assert payload["type"] == "verify"

    async def test_each_request_produces_a_distinct_token(self, sent):
        """Two resends must not hand out the same replayable link twice."""
        svc = _service()
        user = _User()
        await svc.resend_verification(user)
        await svc.resend_verification(user)
        assert sent[0][1] != sent[1][1]

    async def test_already_verified_sends_nothing(self, sent):
        """Nothing left to confirm, and it must not look like a failure."""
        svc = _service()
        assert await svc.resend_verification(_User(is_verified=True)) is True
        assert sent == []

    async def test_smtp_unconfigured_reports_failure_instead_of_silence(self, sent, monkeypatch):
        """The bug this endpoint exists to avoid: a 200 and a phantom email."""
        monkeypatch.setattr(EmailService, "is_configured", classmethod(lambda cls: False))
        svc = _service()
        assert await svc.resend_verification(_User()) is False
        assert sent == []

    async def test_does_not_flip_the_flag_itself(self, monkeypatch):
        """Only clicking the emailed link may set is_verified."""
        svc = _service()
        user = _User()
        monkeypatch.setattr(EmailService, "is_configured", classmethod(lambda cls: True))
        monkeypatch.setattr(
            EmailService, "send_verification_email",
            classmethod(lambda cls, e, t: _noop()),
        )
        await svc.resend_verification(user)
        assert user.is_verified is False


async def _noop():
    return None
