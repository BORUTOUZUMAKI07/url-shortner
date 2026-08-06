from pydantic import BaseModel, EmailStr, Field


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password (min 8 characters)")


class ChangeEmailRequest(BaseModel):
    new_email: EmailStr = Field(..., description="New email address")
    current_password: str = Field(..., description="Current password for verification")


class AvatarUpdateRequest(BaseModel):
    avatar: str = Field(..., description="Base64 data URI of the avatar image (e.g. data:image/png;base64,...)")
