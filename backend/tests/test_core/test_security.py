from datetime import timedelta
from unittest.mock import patch

import jwt
import pytest
from jwt import ExpiredSignatureError, InvalidTokenError

from src.shared.core.config import settings
from src.shared.core.security import (
    create_access_token,
    create_email_verification_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.shared.errors import InvalidToken, TokenExpired


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


@patch("src.shared.core.security.settings.SECRET_KEY", "test-secret-key-for-testing-32-bytes!!")
@patch("src.shared.core.security.settings.ALGORITHM", "HS256")
@patch("src.shared.core.security.settings.ACCESS_TOKEN_EXPIRE_MINUTES", 60)
class TestJWTFunctions:
    def test_create_access_token_returns_string(self, *_):
        token = create_access_token({"sub": "1", "email": "test@example.com"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_default_expiry(self, *_):
        token = create_access_token({"sub": "1"})
        payload = jwt.decode(token, "test-secret-key-for-testing-32-bytes!!", algorithms=["HS256"], audience=settings.JWT_AUDIENCE)
        assert payload["sub"] == "1"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_access_token_custom_expiry(self, *_):
        token = create_access_token({"sub": "1"}, expires_delta=timedelta(minutes=5))
        payload = jwt.decode(token, "test-secret-key-for-testing-32-bytes!!", algorithms=["HS256"], audience=settings.JWT_AUDIENCE)
        assert payload["sub"] == "1"

    def test_create_refresh_token(self, *_):
        token = create_refresh_token({"sub": "1"})
        payload = jwt.decode(token, "test-secret-key-for-testing-32-bytes!!", algorithms=["HS256"], audience=settings.JWT_AUDIENCE)
        assert payload["sub"] == "1"
        assert payload["type"] == "refresh"
        # jti (unique per token) + sid (stable per session) power reuse detection
        assert payload["jti"]
        assert payload["sid"]

    def test_create_refresh_token_keeps_supplied_sid(self, *_):
        token1 = create_refresh_token({"sub": "1"}, sid="fixed-session")
        token2 = create_refresh_token({"sub": "1"}, sid="fixed-session")
        p1 = jwt.decode(token1, "test-secret-key-for-testing-32-bytes!!", algorithms=["HS256"], audience=settings.JWT_AUDIENCE)
        p2 = jwt.decode(token2, "test-secret-key-for-testing-32-bytes!!", algorithms=["HS256"], audience=settings.JWT_AUDIENCE)
        assert p1["sid"] == p2["sid"] == "fixed-session"
        # ...but each rotation mints a fresh jti so a rotated-out token is detectable
        assert p1["jti"] != p2["jti"]

    def test_create_refresh_token_auto_sid_is_unique_per_token(self, *_):
        p1 = jwt.decode(create_refresh_token({"sub": "1"}), "test-secret-key-for-testing-32-bytes!!", algorithms=["HS256"], audience=settings.JWT_AUDIENCE)
        p2 = jwt.decode(create_refresh_token({"sub": "1"}), "test-secret-key-for-testing-32-bytes!!", algorithms=["HS256"], audience=settings.JWT_AUDIENCE)
        assert p1["sid"] != p2["sid"]

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
        with patch("src.shared.core.security.jwt.decode") as mock_decode:
            mock_decode.side_effect = InvalidTokenError()
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
        payload = jwt.decode(token, "test-secret-key-for-testing-32-bytes!!", algorithms=["HS256"], audience=settings.JWT_AUDIENCE)
        assert payload["sub"] == "user@example.com"
        assert payload["type"] == "verify"

    def test_create_password_reset_token(self, *_):
        token = create_password_reset_token("user@example.com", "$argon2id$v=19$m=1,t=1,p=1$c2FsdA$aGFzaA")
        payload = jwt.decode(token, "test-secret-key-for-testing-32-bytes!!", algorithms=["HS256"], audience=settings.JWT_AUDIENCE)
        assert payload["sub"] == "user@example.com"
        assert payload["type"] == "reset"

    def test_decode_token_passes_extra_claims(self, *_):
        token = create_access_token({"sub": "1", "custom": "value"})
        payload = decode_token(token)
        assert payload["custom"] == "value"

    def test_tokens_carry_issuer_audience_and_issued_at(self, *_):
        for token in (
            create_access_token({"sub": "1"}),
            create_refresh_token({"sub": "1"}),
            create_email_verification_token("user@example.com"),
            create_password_reset_token("user@example.com", "$argon2id$v=19$m=1,t=1,p=1$c2FsdA$aGFzaA"),
        ):
            payload = jwt.decode(token, "test-secret-key-for-testing-32-bytes!!", algorithms=["HS256"], audience=settings.JWT_AUDIENCE)
            assert payload["iss"] == settings.JWT_ISSUER
            assert payload["aud"] == settings.JWT_AUDIENCE
            assert isinstance(payload["iat"], (int, float))

    def test_decode_rejects_wrong_audience(self, *_):
        token = jwt.encode(
            {
                "sub": "1",
                "type": "access",
                "exp": 9999999999,
                "iat": 1,
                "iss": settings.JWT_ISSUER,
                "aud": "some-other-service",
            },
            "test-secret-key-for-testing-32-bytes!!",
            algorithm="HS256",
        )
        with pytest.raises(InvalidToken):
            decode_token(token)

    def test_decode_rejects_wrong_issuer(self, *_):
        token = jwt.encode(
            {
                "sub": "1",
                "type": "access",
                "exp": 9999999999,
                "iat": 1,
                "iss": "some-other-issuer",
                "aud": settings.JWT_AUDIENCE,
            },
            "test-secret-key-for-testing-32-bytes!!",
            algorithm="HS256",
        )
        with pytest.raises(InvalidToken):
            decode_token(token)

    def test_decode_rejects_token_without_issuer_or_audience(self, *_):
        token = jwt.encode(
            {"sub": "1", "type": "access", "exp": 9999999999},
            "test-secret-key-for-testing-32-bytes!!",
            algorithm="HS256",
        )
        with pytest.raises(InvalidToken):
            decode_token(token)
