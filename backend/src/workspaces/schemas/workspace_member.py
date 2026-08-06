from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.workspaces.models.workspace_member import MemberRole


class MemberResponse(BaseModel):
    id: int
    user_id: int
    email: str | None = None
    role: MemberRole
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UpdateMemberRole(BaseModel):
    role: MemberRole = Field(..., description="New role for the member (admin, editor, viewer)")


class WorkspaceMemberResponse(BaseModel):
    id: int
    workspace_id: int
    user_id: int
    role: MemberRole
    joined_at: datetime

    model_config = ConfigDict(from_attributes=True)
