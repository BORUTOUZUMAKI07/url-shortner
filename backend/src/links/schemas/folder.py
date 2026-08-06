from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FolderCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Folder name")
    workspace_id: int = Field(..., description="Parent workspace ID")

    model_config = ConfigDict(json_schema_extra={
        "example": {"name": "Marketing Campaigns", "workspace_id": 1}
    })


class FolderUpdate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="New folder name")


class FolderResponse(BaseModel):
    id: int
    name: str
    workspace_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
