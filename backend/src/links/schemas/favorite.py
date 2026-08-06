from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FavoriteCreate(BaseModel):
    url_id: int = Field(..., description="URL ID to mark as favorite")


class FavoriteResponse(BaseModel):
    id: int
    url_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FavoriteURLResponse(BaseModel):
    id: int
    url_id: int
    short_code: str
    original_url: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
