from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Workspace display name")

    model_config = ConfigDict(json_schema_extra={
        "example": {"name": "My Project"}
    })


class WorkspaceResponse(BaseModel):
    id: int
    name: str
    owner_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
