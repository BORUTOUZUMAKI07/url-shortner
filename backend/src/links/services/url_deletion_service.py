"""
URLDeletionService — Single Responsibility: delete (soft-delete) short URLs.
"""


from src.links.models.url import URLStatus
from src.shared.core.interfaces import (
    IAuditService,
    IEventDispatcher,
    IURLRepository,
    IWebhookService,
    IWorkspaceRepository,
)
from src.shared.errors import RoleTooLow, URLNotFound
from src.workspaces.models.workspace_member import MemberRole


class URLDeletionService:
    """Delete short URLs (soft-delete). Single responsibility: deletion only."""

    def __init__(
        self,
        url_repo: IURLRepository,
        workspace_repo: IWorkspaceRepository,
        audit: IAuditService,
        webhooks: IWebhookService,
        event_dispatcher: IEventDispatcher,
    ):
        self.url_repo = url_repo
        self.workspace_repo = workspace_repo
        self.audit = audit
        self.webhooks = webhooks
        self.event_dispatcher = event_dispatcher

    async def _verify_workspace_access(self, workspace_id: int, user_id: int):
        ws = await self.workspace_repo.verify_access(workspace_id, user_id)
        if not ws:
            raise URLNotFound()

    async def _verify_write_role(
        self, workspace_id: int, user_id: int
    ):
        if not await self.workspace_repo.verify_role(
            workspace_id, user_id, MemberRole.editor
        ):
            raise RoleTooLow("editor")

    async def delete(self, id: int, user_id: int) -> None:
        url = await self.url_repo.get(id)
        if not url or url.status == URLStatus.deleted:
            raise URLNotFound()
        await self._verify_workspace_access(url.workspace_id, user_id)
        await self._verify_write_role(url.workspace_id, user_id)
        await self.url_repo.soft_delete(id)

        try:
            await self.audit.log(
                actor_id=user_id,
                action="delete",
                resource_type="url",
                resource_id=url.id,
                before={
                    "short_code": url.short_code,
                    "original_url": url.original_url,
                },
                workspace_id=url.workspace_id,
            )
        except Exception:
            await self.url_repo.rollback()
            raise

        await self.webhooks.deliver_event(
            url.workspace_id,
            "url.deleted",
            {
                "short_code": url.short_code,
                "original_url": url.original_url,
                "workspace_id": url.workspace_id,
                "user_id": user_id,
            },
        )
