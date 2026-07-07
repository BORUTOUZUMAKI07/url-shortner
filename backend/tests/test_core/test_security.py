from datetime import timedelta
from unittest.mock import patch

import pytest
from jose import ExpiredSignatureError, JWTError, jwt

from src.core.security import (
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.errors import InvalidToken, TokenExpired


def test_hash_password_returns_string():
    result = hash_password("testpass123")
    assert isinstance(result, str)
    assert result != "testpass123"


def test_verify_password_correct():
    hashed = hash_password("testpass123")
    assert verify_password("testpass123", hashed) is True


def test_verify_password_incorrect():
    hashed = hash_password("testpass123")
    assert verify_password("wrongpass", hashed) is False


def test_verify_password_empty_plain():
    hashed = hash_password("testpass123")
    assert verify_password("", hashed) is False


@patch("src.core.security.settings.SECRET_KEY", "test-secret-key-for-testing")
@patch("src.core.security.settings.ALGORITHM", "HS256")
@patch("src.core.security.settings.ACCESS_TOKEN_EXPIRE_MINUTES", 60)
class TestJWTFunctions:
    def test_create_access_token_returns_string(self, *_):
        token = create_access_token({"sub": "1", "email": "test@example.com"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_default_expiry(self, *_):
        token = create_access_token({"sub": "1"})
        payload = jwt.decode(token, "test-secret-key-for-testing", algorithms=["HS256"])
        assert payload["sub"] == "1"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_access_token_custom_expiry(self, *_):
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(minutes=5))
        payload = jwt.decode(token, "test-secret-key-for-testing", algorithms=["HS256"])
        assert payload["sub"] == "1"

    def test_create_refresh_token(self, *_):
        token = create_refresh_token({"sub": "1"})
        payload = jwt.decode(token, "test-secret-key-for-testing", algorithms=["HS256"])
        assert payload["sub"] == "1"
        assert payload["type"] == "refresh"

    def test_decode_token_valid(self, *_):
        token = create_access_token({"sub": "1"})
        payload = decode_token(token)
        assert payload["sub"] == "1"
        assert payload["type"] == "access"

    def test_decode_token_expired(self, *_):
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(seconds=-1))
        with pytest.raises(TokenExpired):
            decode_token(token)

    def test_decode_token_invalid_signature(self, *_):
        with patch("src.core.security.jwt.decode") as mock_decode:
            mock_decode.side_effect = JWTError()
            with pytest.raises(InvalidToken):
                decode_token("invalid-token")

    def test_decode_token_malformed(self, *_):
        with pytest.raises(InvalidToken):
            decode_token("not-a-jwt-token")

    def test_decode_token_empty_string(self, *_):
        with pytest.raises(InvalidToken):
            decode_token("")

    def test_create_email_verification_token(self, *_):
        token = create_email_verification_token("user@example.com")
        payload = jwt.decode(token, "test-secret-key-for-testing", algorithms=["HS256"])
        assert payload["sub"] == "user@example.com"
        assert payload["type"] == "verify"

    def test_create_password_reset_token(self, *_):
        token = create_password_reset_token("user@example.com")
        payload = jwt.decode(token, "test-secret-key-for-testing", algorithms=["HS256"])
        assert payload["sub"] == "user@example.com"
        assert payload["type"] == "reset"

    def test_decode_token_passes_extra_claims(self, *_):
        token = create_access_token({"sub": "1", "custom": "value"})
        payload = decode_token(token)
        assert payload["custom"] == "value"
