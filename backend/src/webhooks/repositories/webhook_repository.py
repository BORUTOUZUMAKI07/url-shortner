from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from src.shared.core.base_repository import BaseRepository
from src.webhooks.models.webhook import Webhook
from src.webhooks.models.webhook_event import WebhookEvent
from src.webhooks.models.webhook_subscription import WebhookSubscription


class WebhookRepository(BaseRepository[Webhook]):
    def __init__(self, db):
        super().__init__(Webhook, db)

    async def get(self, id: int) -> Webhook | None:
        result = await self.db.execute(
            select(Webhook)
            .options(selectinload(Webhook.subscriptions))
            .where(Webhook.id == id)
            .execution_options(populate_existing=True)
        )
        return result.scalar_one_or_none()

    async def get_workspace_webhooks(self, workspace_id: int) -> list[Webhook]:
        result = await self.db.execute(
            select(Webhook)
            .options(selectinload(Webhook.subscriptions))
            .where(Webhook.workspace_id == workspace_id)
            .execution_options(populate_existing=True)
        )
        return list(result.scalars().all())

    async def get_active_by_event(self, workspace_id: int, event: str) -> list[Webhook]:
        result = await self.db.execute(
            select(Webhook).where(
                and_(
                    Webhook.workspace_id == workspace_id,
                    Webhook.is_active == True,
                    Webhook.subscriptions.any(WebhookSubscription.event_type == event),
                )
            )
        )
        return list(result.scalars().all())

    async def create_with_subscriptions(self, webhook: Webhook, events: list[str]) -> Webhook:
        self.db.add(webhook)
        await self.db.flush()
        for event_type in events:
            self.db.add(WebhookSubscription(webhook_id=webhook.id, event_type=event_type))
        await self.db.commit()
        created = await self.get(webhook.id)
        return created if created is not None else webhook

    async def sync_subscriptions(self, webhook: Webhook, events: list[str]) -> None:
        existing = {sub.event_type for sub in webhook.subscriptions}
        for event_type in events:
            if event_type not in existing:
                self.db.add(WebhookSubscription(webhook_id=webhook.id, event_type=event_type))
        for sub in list(webhook.subscriptions):
            if sub.event_type not in events:
                await self.db.delete(sub)
        await self.db.commit()

    async def record_delivery(
        self,
        webhook_id: int,
        event_type: str,
        payload: str,
        status: str,
        response_code: int | None = None,
        error: str | None = None,
    ) -> None:
        self.db.add(WebhookEvent(
            webhook_id=webhook_id,
            event_type=event_type,
            payload=payload,
            status=status,
            response_code=response_code,
            error=error,
        ))
        await self.db.commit()
