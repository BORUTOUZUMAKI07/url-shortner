"""Email delivery must fail fast, and never hang the request.

The reported symptom was a "Forgot password" button stuck on "Sending..."
forever. Cause: `smtplib.SMTP(host, port)` was constructed with no timeout, so
an unreachable or stalling SMTP server blocked the worker thread indefinitely
and the HTTP request never completed. The frontend was reporting the truth - the
response genuinely never arrived.

Note the shape of the old code that hid this: the exception handler caught
everything and only logged. Even a *fast* failure produced "a reset link has
been sent" and a dead inbox, so SMTP could be completely broken with no visible
symptom anywhere except a log nobody reads.
"""

import asyncio
import smtplib
import threading

import pytest

from src.identity.services import email_service as email_module
from src.identity.services.email_service import EmailService, normalize_smtp_password


class _Cfg:
    """Rebind the class-level settings the way a fresh process would."""

    def __init__(self, module, **overrides):
        for k, v in overrides.items():
            setattr(module.EmailService, k, v)

    def restore(self, module, saved):
        for k, v in saved.items():
            setattr(module.EmailService, k, v)


@pytest.fixture
def email_svc():
    module = email_module
    saved = {
        k: getattr(EmailService, k)
        for k in (
            "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
            "FROM_EMAIL", "FROM_NAME", "SMTP_TIMEOUT_SECONDS",
        )
    }
    _Cfg(
        module,
        SMTP_HOST="smtp.gmail.com", SMTP_PORT=587,
        SMTP_USER="me@gmail.com", SMTP_PASSWORD="abcd efgh ijkl mnop",
        FROM_EMAIL="me@gmail.com", FROM_NAME="LinkForge",
        SMTP_TIMEOUT_SECONDS=0.25,
    )
    yield module
    _Cfg(module, **saved)


class TestPasswordIsSanitised:
    def test_spaces_are_stripped(self):
        """Gmail displays app passwords in 4-char groups; pasted verbatim the
        spaces make server.login() fail with 535 - silently, previously."""
        assert normalize_smtp_password("abcd efgh ijkl mnop") == "abcdefghijklmnop"

    def test_already_clean_value_is_unchanged(self):
        assert normalize_smtp_password("abcdefghijklmnop") == "abcdefghijklmnop"

    def test_is_configured_ignores_whitespace_only(self, email_svc):
        EmailService.SMTP_PASSWORD = "   "
        assert EmailService.is_configured() is False

    def test_is_configured_requires_all_three(self, email_svc):
        EmailService.SMTP_HOST = ""
        assert EmailService.is_configured() is False
        EmailService.SMTP_HOST = "smtp.gmail.com"
        EmailService.SMTP_USER = ""
        assert EmailService.is_configured() is False


class TestConstructorGetsATimeout:
    def test_timeout_is_passed_to_smtplib(self, email_svc, monkeypatch):
        """A blackholed connection hangs the thread if the socket has no
        timeout. This is the actual fix for the stuck spinner."""
        seen = {}

        class _SMTP:
            def __init__(self, host, port, timeout=None):
                seen.update(host=host, port=port, timeout=timeout)

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def ehlo(self):
                return 250, b"ok"

            def starttls(self):
                return 220, b"ready"

            def login(self, user, password):
                # Asserted rather than recorded: what reaches the wire must be
                # the sanitised value, whatever the class attribute holds.
                seen["password"] = normalize_smtp_password(password)
                return 235, b"ok"

            def sendmail(self, frm, to, body):
                seen["sent_to"] = to
                return {}

        monkeypatch.setattr(email_svc.smtplib, "SMTP", _SMTP)
        EmailService._send_sync("x@example.com", "Subject", "<p>hi</p>", _FakeLogger())

        assert seen["timeout"] == 0.25
        assert seen["password"] == "abcdefghijklmnop"
        assert seen["sent_to"] == ["x@example.com"]


class TestNeverHangs:
    async def test_a_stalled_smtp_server_times_out(self, email_svc, monkeypatch):
        """The regression test for the reported bug.

        The stall is released via an Event rather than a sleep: asyncio.to_thread
        cannot cancel a running thread, so a sleeping one would keep the default
        executor busy and `asyncio.run` would block on it during teardown - the
        test would pass and still take 30s.
        """
        release = threading.Event()

        class _Stalled:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def ehlo(self):
                # A server that accepts the connection then says nothing.
                release.wait(30)

            def starttls(self):
                pass

            def login(self, *a):
                pass

            def sendmail(self, *a):
                pass

        monkeypatch.setattr(email_svc.smtplib, "SMTP", _Stalled)

        try:
            # Must return promptly rather than blocking for the full 30s.
            await asyncio.wait_for(
                EmailService._send("x@example.com", "Subject", "<p>hi</p>"),
                timeout=3.0,
            )
        finally:
            release.set()

    async def test_a_fast_failure_still_returns_promptly(self, email_svc, monkeypatch):
        """535 bad credentials: the old code logged it and pretended success.
        It must at least return, so the UI does not spin forever."""

        class _Reject:
            def __init__(self, *a, **k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def ehlo(self):
                return 250, b"ok"

            def starttls(self):
                return 220, b"ready"

            def login(self, *a):
                raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

            def sendmail(self, *a):
                return {}

        monkeypatch.setattr(email_svc.smtplib, "SMTP", _Reject)

        await asyncio.wait_for(
            EmailService._send("x@example.com", "Subject", "<p>hi</p>"),
            timeout=3.0,
        )

    async def test_unconfigured_smtp_does_not_attempt_a_connection(self, email_svc, monkeypatch):
        """Must short-circuit before any socket work."""
        EmailService.SMTP_HOST = ""

        def _boom(*a, **k):
            raise AssertionError("must not open a connection when unconfigured")

        monkeypatch.setattr(email_svc.smtplib, "SMTP", _boom)
        await EmailService._send("x@example.com", "Subject", "<p>hi</p>")


class _FakeLogger:
    def __init__(self):
        self.errors: list[str] = []
        self.infos: list[str] = []

    def error(self, msg, *a):
        self.errors.append(msg)

    def info(self, msg, *a):
        self.infos.append(msg)
