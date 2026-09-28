import asyncio
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import ExpiredSignatureError, JWTError, jwt
from passlib.context import CryptContext

from src.shared.core.config import settings
from src.shared.errors import InvalidToken, TokenExpired

pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

async def hash_password_async(password: str) -> str:
    """Argon2 hashing is ~100-200ms of CPU — offload it so the event loop
    isn't blocked for every password-protected URL / API key / login."""
    return await asyncio.to_thread(hash_password, password)

async def verify_password_async(plain: str, hashed: str) -> bool:
    return await asyncio.to_thread(verify_password, plain, hashed)

# Claims this module owns. A caller passing them in would be silently ignored
# (they were overwritten before, which hid bugs like a caller asking for a
# 30-day token and getting the default), so now they raise.
_RESERVED_CLAIMS = frozenset({"exp", "type", "jti", "sid"})


def _encode(data: dict, reserved: dict) -> str:
    collisions = _RESERVED_CLAIMS & data.keys()
    if collisions:
        raise ValueError(
            "Reserved JWT claim(s) cannot be supplied by the caller: "
            + ", ".join(sorted(collisions))
        )
    return jwt.encode({**data, **reserved}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    return _encode(data, {"exp": expire, "type": "access"})

def create_refresh_token(data: dict, sid: Optional[str] = None) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    # jti (unique per token) + sid (stable per session, survives rotation) enable
    # refresh-token reuse detection: a rotated-out token whose jti no longer
    # matches the session record means the token was replayed.
    return _encode(data, {
        "exp": expire,
        "type": "refresh",
        "jti": secrets.token_urlsafe(32),
        "sid": sid or secrets.token_urlsafe(32),
    })

def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except ExpiredSignatureError:
        raise TokenExpired()
    except JWTError:
        raise InvalidToken()

def reset_fingerprint(password_hash: str) -> str:
    """A short stable fingerprint of a password hash.

    Binding a reset token to this makes the token single-use *in effect*: once
    the password changes, the fingerprint no longer matches and the old token is
    dead. Without it a captured reset link stayed valid for its whole hour, so an
    attacker who saw one could re-apply it *after* the legitimate user had
    already reset, and take the account anyway.

    Deliberately stateless - no Redis record, so there is no cache to depend on
    and no fail-open/fail-closed decision to get wrong.
    """
    return hashlib.sha256(password_hash.encode()).hexdigest()[:16]


def create_email_verification_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=24)
    # The jti is load-bearing for "resend": without a nonce the token is a pure
    # function of (email, current second), so two issuances in the same second are
    # byte-identical and a resend cannot produce a genuinely new link.
    return jwt.encode(
        {"sub": email, "exp": expire, "type": "verify", "jti": secrets.token_urlsafe(16)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def create_password_reset_token(email: str, password_hash: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {
            "sub": email,
            "exp": expire,
            "type": "reset",
            "jti": secrets.token_urlsafe(16),
            "pfp": reset_fingerprint(password_hash),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
