from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password (min 8 characters)")


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr = Field(..., description="New email address")
    current_password: str = Field(..., description="Current password for verification")


class AvatarUpdateRequest(BaseModel):
    avatar: str = Field(..., description="Base64 data URI of the avatar image (e.g. data:image/png;base64,...)")


class SessionResponse(BaseModel):
    id: str
    created_at: datetime | None = None
    last_seen_at: datetime | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    is_current: bool = False

    model_config = ConfigDict(from_attributes=True)


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]


class TwoFactorSetupRequest(BaseModel):
    current_password: str = Field(..., description="Current password")


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str
    qr_code_data_uri: str


class TwoFactorConfirmRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=16, description="6-digit TOTP code")


class TwoFactorDisableRequest(BaseModel):
    current_password: str = Field(..., description="Current password")
    code: str = Field(..., min_length=6, max_length=32, description="TOTP code or recovery code")


class TwoFactorStatusResponse(BaseModel):
    enabled: bool
    confirmed_at: datetime | None = None
    recovery_codes_remaining: int = 0


class RecoveryCodesResponse(BaseModel):
    recovery_codes: list[str]


class AccountExportResponse(BaseModel):
    exported_at: datetime
    profile: dict
    workspaces: list[dict]
    links: list[dict]
    api_keys: list[dict]
    favorites: list[dict]
    audit_retention_policy: dict


class AccountDeleteRequest(BaseModel):
    current_password: str = Field(..., description="Current password for confirmation")
    confirmation: str = Field(..., description="Type DELETE to confirm account deletion")
