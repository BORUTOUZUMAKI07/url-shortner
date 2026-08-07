from sqlalchemy import and_, select
from sqlalchemy.orm import selectinload

from src.shared.core.base_repository import BaseRepository
from src.webhooks.models.webhook import Webhook
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
