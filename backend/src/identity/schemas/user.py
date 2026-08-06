from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.identity.models.user import PlanEnum, RoleEnum


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
    role: RoleEnum
    plan: PlanEnum
    is_superadmin: bool
    avatar_url: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")
    refresh_token: Optional[str] = Field(None, description="Refresh token for silent re-authentication")


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr = Field(description="Registered email to receive reset link")


class ResetPasswordRequest(BaseModel):
    token: str = Field(description="Password reset token (received via email)")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password (min 8 characters)")


class VerifyEmailRequest(BaseModel):
    token: str = Field(description="Email verification token")


class GoogleOAuthInitRequest(BaseModel):
    redirect_uri: Optional[str] = Field(None, description="Optional override of OAuth redirect URI")


class GoogleOAuthInitResponse(BaseModel):
    authorization_url: str
    state: str


class GoogleOAuthCallbackRequest(BaseModel):
    code: str
    state: str
