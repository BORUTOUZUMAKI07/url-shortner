from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from src.workspaces.models.workspace_invite import InviteStatus


class InviteCreate(BaseModel):
    email: EmailStr = Field(description="Email address of the invited user")
    role: str = Field(default="editor", pattern="^(admin|editor|viewer)$", description="Role to assign (admin, editor, viewer)")

    model_config = ConfigDict(json_schema_extra={
        "example": {"email": "colleague@example.com", "role": "editor"}
    })


class InviteResponse(BaseModel):
    id: int
    workspace_id: int
    email: str
    invited_by: int
    role: str
    status: InviteStatus
    token: str | None = None
    expires_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AcceptInviteRequest(BaseModel):
    token: str = Field(description="Invite token from the invitation email")
