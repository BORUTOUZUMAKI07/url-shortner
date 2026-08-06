import uuid
from datetime import datetime, timezone
from typing import Optional

from beanie import Document
from pydantic import Field
from pymongo import ASCENDING, IndexModel


class ClickEvent(Document):
    """
    Raw click event stored in MongoDB via Beanie ODM.
    Written by analytics_worker after consuming from Kafka.
    The event_id field provides idempotency - duplicate Kafka deliveries
    are rejected by the unique index on event_id (At-Least-Once + Idempotent Consumer).
    """
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    short_code: str
    original_url: str
    workspace_id: int

    # Request metadata
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referer: Optional[str] = None

    # Parsed from User-Agent
    browser: Optional[str] = None
    os: Optional[str] = None
    device: Optional[str] = None

    # Geo-IP resolved
    country: Optional[str] = None
    city: Optional[str] = None

    # UTM params
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None

    clicked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Settings:
        name = "click_events"
        indexes = [
            "short_code",
            "workspace_id",
            "clicked_at",
            IndexModel([("event_id", ASCENDING)], unique=True, name="event_id_unique_idx"),  # Unique index for idempotency
        ]
