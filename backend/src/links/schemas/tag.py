from pydantic import BaseModel, ConfigDict, Field


class TagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_\-\s]+$", description="Tag name (alphanumeric, spaces, hyphens, underscores)")
    workspace_id: int = Field(..., description="Parent workspace ID")

    model_config = ConfigDict(json_schema_extra={
        "example": {"name": "summer-promo", "workspace_id": 1}
    })


class TagResponse(BaseModel):
    id: int
    name: str
    workspace_id: int

    model_config = ConfigDict(from_attributes=True)
