from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class WebhookReceivedEventResponse(BaseModel):
    id: int
    webhook_id: Optional[int] = None
    workspace_id: int
    event_type: str
    payload: str
    headers: Optional[str] = None
    signature: Optional[str] = None
    signature_valid: bool = False
    source_ip: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
