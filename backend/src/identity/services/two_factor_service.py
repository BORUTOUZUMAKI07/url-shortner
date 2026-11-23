"""TOTP two-factor authentication helpers.

Secrets are encrypted at rest with Fernet, using a key derived from
settings.SECRET_KEY. Recovery codes are random, shown once, and stored only as
Argon2 hashes.
"""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from io import BytesIO

import pyotp
import qrcode
from cryptography.fernet import Fernet, InvalidToken

from src.shared.core.config import settings
from src.shared.core.security import hash_password, verify_password


def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_totp_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode("utf-8")).decode("utf-8")


def decrypt_totp_secret(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Invalid encrypted TOTP secret") from exc


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_otpauth_uri(email: str, secret: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name=settings.TOTP_ISSUER)


def qr_data_uri(otpauth_uri: str) -> str:
    qr = qrcode.QRCode(border=2, box_size=6)
    qr.add_data(otpauth_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, "PNG")
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def verify_totp_code(secret: str, code: str, last_counter: int | None = None) -> int | None:
    """Return the accepted TOTP counter, or None if invalid/replayed."""
    totp = pyotp.TOTP(secret)
    normalized = "".join(ch for ch in code if ch.isdigit())
    if len(normalized) != 6:
        return None
    # valid_window=1 allows adjacent 30s step for clock skew.
    ok = totp.verify(normalized, valid_window=1)
    if not ok:
        return None
    # pyotp's verify doesn't expose counter directly; compute current counter.
    # We accept the code; replay protection: reject if counter <= last_counter.
    import time

    counter = int(time.time()) // totp.interval
    # Find which counter in the window matched to be precise.
    matched_counter = None
    for offset in (-1, 0, 1):
        candidate = counter + offset
        if totp.generate_otp(candidate) == normalized:
            matched_counter = candidate
            break
    if matched_counter is None:
        matched_counter = counter
    if last_counter is not None and matched_counter <= last_counter:
        return None
    return matched_counter


def generate_recovery_codes(count: int | None = None) -> list[str]:
    n = count or settings.TWO_FACTOR_RECOVERY_CODES
    # 10-char grouped codes, readable but high entropy.
    codes: list[str] = []
    for _ in range(n):
        raw = secrets.token_hex(5).upper()  # 10 hex chars
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


def hash_recovery_codes(codes: list[str]) -> str:
    return json.dumps([hash_password(c) for c in codes])


def verify_recovery_code(stored_json: str | None, code: str) -> tuple[bool, str | None]:
    """Return (matched, updated_json). Consumes the matched code."""
    if not stored_json:
        return False, stored_json
    try:
        hashes = json.loads(stored_json)
    except Exception:
        return False, stored_json
    if not isinstance(hashes, list):
        return False, stored_json
    normalized = code.strip().upper()
    for i, h in enumerate(hashes):
        if isinstance(h, str) and verify_password(normalized, h):
            remaining = hashes[:i] + hashes[i + 1 :]
            return True, json.dumps(remaining)
    return False, stored_json
