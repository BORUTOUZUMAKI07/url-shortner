"""PII / secret redaction for the log stream.

Regex-based scrubber for common personally identifiable information and
high-value secrets (emails, phone numbers, SSNs, IP addresses, cloud keys,
bearer tokens, private-key blocks, home-directory paths, and the credentials
inside a database DSN).

Why this exists: every log record is shipped off-box over OTLP to New Relic
(and can additionally be captured by Sentry). A stray DSN, an ``Authorization``
header, or a user's email address in an application log is a data leak to a
third party. Redaction is therefore applied at the *log handler* boundary —
see :class:`RedactionFilter` — so it cannot be forgotten at a call site.

All matchers are deliberately conservative (format-checked) so ordinary log
lines are not mangled. This is defense-in-depth, not a replacement for
structured schema validation or pseudonymization at write time.
"""

import logging
import re
from typing import Any

from src.shared.core.config import settings

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+?\d{1,3}[\s.\-]?)?\(?\d{3}\)?[\s.\-]?\d{3}[\s.\-]?\d{4}(?!\d)"
)
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_AWS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA|AGPA|AIDA|AROA)[A-Z0-9]{16}\b")
_BEARER_TOKEN_RE = re.compile(
    r"\b(?:Bearer|sk-|ghp_|gho_|github_pat_|xox[baprs]-)[A-Za-z0-9._\-]{8,}\b",
    re.IGNORECASE,
)
_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----.*?-----END "
    r"(?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----",
    re.DOTALL,
)
_HOME_PATH_RE = re.compile(
    r"(?<![\\/\w])(?:C:\\Users\\[^\\\s]+|/home/[^/\s]+|/Users/[^/\s]+)"
)
# The `user:password@` of a DSN. Group 1 is the scheme and group 2 the username
# (kept — it identifies the role, e.g. `postgres.<ref>`, which is genuinely
# useful when debugging a pooler); only the password is dropped.
_DSN_CREDENTIALS_RE = re.compile(
    r"(?i)\b(postgres(?:ql)?(?:\+\w+)?://)([^:/@\s]+):([^@/\s]*)@"
)

# Keys whose *entire value* is replaced in structured payloads (they are
# secrets by name even when the value does not match a format pattern).
_SECRET_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "secret",
    "secret_key",
    "password",
    "passwd",
    "token",
    "access_token",
    "refresh_token",
    "session_id",
    "private_key",
    "encryption_key",
    "jwt",
}

# Attributes present on every LogRecord (plus formatter extras) — never
# rewritten by redact_record, either because they are non-string or because
# they are handled explicitly.
_STANDARD_RECORD_ATTRS = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}


def redact_dsn(dsn: str) -> str:
    """Strip the password from a Postgres DSN, keeping it diagnosable.

    Truncation is not a substitute: ``dsn[:40]`` only avoids the password for
    a particular provider/username length. A ``+asyncpg`` driver suffix or a
    shorter username moves the cut back onto the secret.
    """
    if not dsn:
        return dsn
    return _DSN_CREDENTIALS_RE.sub(
        lambda m: f"{m.group(1)}{m.group(2)}:{settings.PII_REDACTION_REPLACEMENT}@",
        dsn,
        count=1,
    )


def redact_text(text: str, replacement: str | None = None) -> str:
    """Scrub every recognized PII/secret pattern from ``text``.

    Order matters: DSN credentials are stripped first (so the ``@`` separator
    inside a DSN is gone before the email regex runs), then private keys
    (whose bodies contain colon/dash patterns the SSN/phone matchers could
    otherwise touch), then the narrower format matchers.
    """
    if not text:
        return text
    repl = replacement if replacement is not None else settings.PII_REDACTION_REPLACEMENT
    scrubbed = _DSN_CREDENTIALS_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}:{repl}@", text)
    scrubbed = _PRIVATE_KEY_RE.sub(repl, scrubbed)
    scrubbed = _EMAIL_RE.sub(repl, scrubbed)
    scrubbed = _SSN_RE.sub(repl, scrubbed)
    scrubbed = _cc_sub(scrubbed, repl)
    scrubbed = _PHONE_RE.sub(repl, scrubbed)
    scrubbed = _IP_RE.sub(repl, scrubbed)
    scrubbed = _AWS_KEY_RE.sub(repl, scrubbed)
    scrubbed = _BEARER_TOKEN_RE.sub(repl, scrubbed)
    scrubbed = _HOME_PATH_RE.sub(repl, scrubbed)
    return scrubbed


def _cc_sub(text: str, repl: str) -> str:
    """Redact 13-16+ digit card-like runs without mangling short numeric IDs."""
    return re.sub(r"\b(?:\d{4}[ -]?){3,4}\d{1,4}\b", repl, text)


def redact_value(value: Any) -> Any:
    """Recursively scrub scalar strings inside dict/list structures."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in _SECRET_KEYS:
                out[k] = settings.PII_REDACTION_REPLACEMENT
            else:
                out[k] = redact_value(v)
        return out
    if isinstance(value, list):
        return [redact_value(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact_value(v) for v in value)
    return value


def redact_record(record: logging.LogRecord) -> None:
    """Scrub a ``LogRecord`` in place. Idempotent, and never raises.

    ``record.msg``/``record.args`` are collapsed to an already-formatted,
    already-redacted string with ``args`` cleared, so a second pass (this
    filter runs once per handler) cannot re-format or double-scrub.
    """
    if isinstance(record.msg, str):
        record.msg = redact_text(record.getMessage())
        record.args = None

    for key, value in list(record.__dict__.items()):
        if key in _STANDARD_RECORD_ATTRS:
            continue
        if isinstance(value, str):
            record.__dict__[key] = redact_text(value)
        elif isinstance(value, (dict, list, tuple)):
            record.__dict__[key] = redact_value(value)


class RedactionFilter(logging.Filter):
    """Log filter that scrubs PII/secrets before any handler formats a record.

    Attach to **handlers**, not loggers: a logger's own filters are not
    consulted for records emitted by its children, so a logger-level filter
    would miss ``url-shortener.redirect_service`` and every similar child.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            redact_record(record)
        except Exception:  # noqa: BLE001 - logging must never break on redaction
            pass
        return True


__all__ = [
    "RedactionFilter",
    "redact_dsn",
    "redact_record",
    "redact_text",
    "redact_value",
]
