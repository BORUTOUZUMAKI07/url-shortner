from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr = Field(description="User email address")
    password: str = Field(..., min_length=8, max_length=128, description="Account password (min 8 characters)")

    model_config = ConfigDict(json_schema_extra={
        "example": {"email": "user@example.com", "password": "securePass123"}
    })


class UserLogin(BaseModel):
    email: EmailStr = Field(description="Registered email address")
    password: str = Field(..., description="Account password")


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    is_verified: bool
    is_active: bool
    is_superadmin: bool
    avatar_url: str | None = None
    two_factor_enabled: bool = False
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    refresh_token: Optional[str] = Field(None, description="Refresh token for silent re-authentication")


class TwoFactorChallengeResponse(BaseModel):
    two_factor_required: bool = True
    challenge_token: str
    token_type: str = "bearer"


class LoginResponse(BaseModel):
    """Either a token pair or a 2FA challenge."""

    access_token: str | None = None
    token_type: str = "bearer"
    refresh_token: str | None = None
    two_factor_required: bool = False
    challenge_token: str | None = None

    @property
    def is_challenge(self) -> bool:
        return self.two_factor_required and bool(self.challenge_token)


class TokenWithUser(Token):
    user: UserResponse


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class OAuthExchangeRequest(BaseModel):
    code: str = Field(description="Short-lived one-time OAuth handoff code from the callback redirect")


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(description="Registered email to receive reset link")


class ResetPasswordRequest(BaseModel):
    token: str = Field(description="Password reset token (received via email)")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password (min 8 characters)")


class VerifyEmailRequest(BaseModel):
    token: str = Field(description="Email verification token")


class ResendVerificationRequest(BaseModel):
    email: EmailStr = Field(description="Address to (re-)send the verification link to")


class TwoFactorVerifyRequest(BaseModel):
    challenge_token: str = Field(..., description="Temporary 2FA challenge token from login")
    code: str = Field(..., min_length=6, max_length=32, description="TOTP code or recovery code")


class GoogleOAuthInitRequest(BaseModel):
    redirect_uri: Optional[str] = Field(None, description="Optional override of OAuth redirect URI")


class GoogleOAuthInitResponse(BaseModel):
    authorization_url: str
    state: str


class GoogleOAuthCallbackRequest(BaseModel):
    code: str
    state: str
