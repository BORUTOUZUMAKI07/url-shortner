from sqlalchemy import select

from src.shared.core.base_repository import BaseRepository
from src.webhooks.models.webhook_received_event import WebhookReceivedEvent


class WebhookReceivedEventRepository(BaseRepository[WebhookReceivedEvent]):
    def __init__(self, db):
        super().__init__(WebhookReceivedEvent, db)

    async def get_workspace_events(
        self, workspace_id: int, skip: int = 0, limit: int = 50
    ) -> list[WebhookReceivedEvent]:
        result = await self.db.execute(
            select(WebhookReceivedEvent)
            .where(WebhookReceivedEvent.workspace_id == workspace_id)
            .order_by(WebhookReceivedEvent.created_at.desc())
            .offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def log_event(
        self, workspace_id: int, event_type: str, payload: str,
        headers: str | None = None, signature: str | None = None,
        signature_valid: bool = False, source_ip: str | None = None,
        webhook_id: int | None = None,
    ) -> WebhookReceivedEvent:
        event = WebhookReceivedEvent(
            workspace_id=workspace_id, event_type=event_type,
            payload=payload, headers=headers, signature=signature,
            signature_valid=signature_valid, source_ip=source_ip,
            webhook_id=webhook_id,
        )
        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)
        return event
