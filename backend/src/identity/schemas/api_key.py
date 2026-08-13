from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from src.identity.models.api_key import APIKeyStatus


class APIKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable name for this API key")
    expires_at: Optional[datetime] = Field(None, description="Optional expiration date/time")

    model_config = ConfigDict(json_schema_extra={
        "example": {"name": "CI/CD Pipeline Key", "expires_at": "2026-12-31T23:59:59Z"}
    })


class APIKeyResponse(BaseModel):
    id: int
    name: str
    prefix: str
    status: APIKeyStatus
    expires_at: Optional[datetime]
    last_used_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class APIKeyCreateResponse(APIKeyResponse):
    key: str


class APIKeyAggregateQuota(BaseModel):
    """Per-user daily API-key quota usage summed across all active keys."""

    used: int
    limit: int
    remaining: int
    resets_at: str
