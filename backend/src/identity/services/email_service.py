import asyncio
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from src.shared import get_logger
from src.shared.core.config import settings


def normalize_smtp_password(raw: str) -> str:
    """Strip the display grouping Gmail puts in app passwords.

    Gmail shows a 16-character app password as "abcd efgh ijkl mnop". Those
    spaces are cosmetic; a value pasted with them intact makes server.login()
    fail with 535 - which the old code caught and logged, so the address was
    told a reset link was on its way when nothing had been sent.
    """
    return raw.replace(" ", "")


class EmailService:
    SMTP_HOST: str = settings.SMTP_HOST
    SMTP_PORT: int = settings.SMTP_PORT
    SMTP_USER: str = settings.SMTP_USER
    SMTP_PASSWORD: str = normalize_smtp_password(settings.SMTP_PASSWORD)
    FROM_EMAIL: str = settings.FROM_EMAIL
    FROM_NAME: str = settings.FROM_NAME
    SMTP_TIMEOUT_SECONDS: float = 10.0

    @classmethod
    def is_configured(cls) -> bool:
        return bool(
            cls.SMTP_HOST
            and cls.SMTP_USER
            and normalize_smtp_password(cls.SMTP_PASSWORD)
        )

    @classmethod
    async def send_verification_email(cls, email: str, token: str) -> None:
        verify_url = f"{settings.FRONTEND_URL or 'http://localhost:3000'}/verify-email?token={token}"
        subject = "Verify your email — LinkForge"
        html = f"""
        <h2>Welcome to LinkForge!</h2>
        <p>Click the link below to verify your email address:</p>
        <p><a href="{verify_url}">{verify_url}</a></p>
        <p>This link expires in 24 hours.</p>
        """
        await cls._send(email, subject, html)

    @classmethod
    async def send_password_reset(cls, email: str, token: str) -> None:
        reset_url = f"{settings.FRONTEND_URL or 'http://localhost:3000'}/reset-password?token={token}"
        subject = "Reset your password — LinkForge"
        html = f"""
        <h2>Password Reset Request</h2>
        <p>Click the link below to reset your password:</p>
        <p><a href="{reset_url}">{reset_url}</a></p>
        <p>This link expires in 1 hour.</p>
        <p>If you didn't request this, you can safely ignore this email.</p>
        """
        await cls._send(email, subject, html)

    @classmethod
    async def send_invite_email(cls, workspace_name: str, role: str, email: str, token: str) -> None:
        accept_url = f"{settings.FRONTEND_URL or 'http://localhost:3000'}/workspaces?invite_token={token}"
        subject = f"You've been invited to {workspace_name} — LinkForge"
        html = f"""
        <h2>Workspace Invitation</h2>
        <p>You've been invited to <strong>{workspace_name}</strong> as <strong>{role}</strong>.</p>
        <p><a href="{accept_url}">Accept Invitation</a></p>
        <p>Or copy this link: {accept_url}</p>
        <p>This invitation expires in 7 days.</p>
        """
        await cls._send(email, subject, html)

    @classmethod
    async def _send(cls, to_email: str, subject: str, html: str) -> None:
        logger = get_logger("email")
        if not cls.is_configured():
            logger.info(f"[EMAIL] Would send email to {to_email}: {subject}")
            return
        try:
            await asyncio.wait_for(
                asyncio.to_thread(cls._send_sync, to_email, subject, html, logger),
                timeout=cls.SMTP_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            # Without this, smtplib.SMTP() blocks forever on an unreachable or
            # stalling server, the request never completes, and the UI sits on
            # "Sending..." indefinitely. A hard ceiling is the whole fix.
            logger.error(
                f"[EMAIL] Timed out after {cls.SMTP_TIMEOUT_SECONDS}s sending "
                f"to {to_email} via {cls.SMTP_HOST}:{cls.SMTP_PORT}"
            )

    @classmethod
    def _send_sync(cls, to_email: str, subject: str, html: str, logger) -> None:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"{cls.FROM_NAME} <{cls.FROM_EMAIL}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html"))
            # timeout on the constructor covers DNS + TCP + the SMTP greeting.
            # Without it a blackholed connection hangs the worker thread forever.
            with smtplib.SMTP(cls.SMTP_HOST, cls.SMTP_PORT, timeout=cls.SMTP_TIMEOUT_SECONDS) as server:
                server.ehlo()
                server.starttls()
                server.ehlo()
                server.login(cls.SMTP_USER, cls.SMTP_PASSWORD)
                server.sendmail(cls.FROM_EMAIL, [to_email], msg.as_string())
            logger.info(f"Email sent to {to_email}: {subject}")
        except Exception as e:
            # Swallowed, as before - callers treat a failed mail as "sent" so we
            # never disclose whether an address exists. But the timeout means the
            # failure now arrives at a known time and is logged, instead of the
            # request hanging open forever.
            logger.error(f"Failed to send email to {to_email}: {type(e).__name__}: {e}")
