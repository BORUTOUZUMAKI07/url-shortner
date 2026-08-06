from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int]
    action: str
    resource_type: str
    resource_id: Optional[int]
    before_state: Optional[str]
    after_state: Optional[str]
    ip_address: Optional[str]
    user_agent: Optional[str]
    workspace_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
