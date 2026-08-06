from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_serializer, field_validator

from src.links.models.url import URLStatus


class URLCreate(BaseModel):
    original_url: HttpUrl = Field(description="The original long URL to shorten")
    workspace_id: int = Field(..., description="Workspace to create the URL in")
    custom_alias: Optional[str] = Field(None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$", description="Custom short code alias (alphanumeric, hyphens, underscores)")
    folder_id: Optional[int] = Field(None, description="Folder to organize this URL")
    domain: Optional[str] = Field(None, description="Custom domain for the short link")
    password: Optional[str] = Field(None, min_length=1, max_length=128, description="Password protection for the link")
    is_ab_test: bool = Field(False, description="Enable A/B testing with iOS/Android destinations")
    is_one_time: bool = Field(False, description="One-time access link (self-destructs after first view)")
    ios_url: Optional[HttpUrl] = Field(None, description="iOS-specific redirect URL (A/B testing)")
    android_url: Optional[HttpUrl] = Field(None, description="Android-specific redirect URL (A/B testing)")
    expires_at: Optional[datetime] = Field(None, description="URL expiration date/time")
    tags: Optional[List[str]] = Field(None, description="Tags to attach to the URL")

    model_config = ConfigDict(json_schema_extra={
        "example": {
            "original_url": "https://example.com/very/long/url",
            "workspace_id": 1,
            "custom_alias": "my-link",
            "is_one_time": False,
            "tags": ["promo", "summer"],
        }
    })


class URLResponse(BaseModel):
    id: int
    short_code: str
    original_url: str
    workspace_id: int
    folder_id: Optional[int]
    custom_alias: Optional[str]
    domain: Optional[str]
    is_ab_test: bool
    is_one_time: bool
    ios_url: Optional[str]
    android_url: Optional[str]
    expires_at: Optional[datetime]
    status: URLStatus
    qr_code: Optional[str] = None
    created_at: datetime
    tags: List[str] = []

    model_config = ConfigDict(from_attributes=True)

    @field_validator('tags', mode='before')
    @classmethod
    def handle_tags_field(cls, v: Any) -> List[str]:
        if isinstance(v, list):
            if len(v) > 0 and hasattr(v[0], 'name'):
                return [t.name for t in v]
            return v  # type: ignore[no-any-return]
        return v  # type: ignore[no-any-return]

    @field_serializer("tags", when_used="json-unless-none")
    def serialize_tags(self, v) -> List[str]:
        if not v:
            return []
        if isinstance(v, list) and len(v) > 0 and hasattr(v[0], 'name'):
            return [t.name for t in v]
        return v  # type: ignore[no-any-return]


class URLListResponse(BaseModel):
    items: List[URLResponse]
    total: int

class URLUpdate(BaseModel):
    original_url: Optional[HttpUrl] = Field(None, description="New destination URL")
    folder_id: Optional[int] = Field(None, description="Move to a different folder")
    domain: Optional[str] = Field(None, description="Change custom domain")
    password: Optional[str] = Field(None, min_length=1, max_length=128, description="Update password protection")
    is_ab_test: Optional[bool] = Field(None, description="Enable/disable A/B testing")
    ios_url: Optional[HttpUrl] = Field(None, description="Update iOS redirect URL")
    android_url: Optional[HttpUrl] = Field(None, description="Update Android redirect URL")
    expires_at: Optional[datetime] = Field(None, description="Update expiration date")
    status: Optional[URLStatus] = Field(None, description="Change URL status (active/disabled)")
    tags: Optional[List[str]] = Field(None, description="Replace existing tags")
