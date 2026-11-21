"""
URLUpdateService — Single Responsibility: update existing short URLs.

Depends on abstractions where available and concrete repositories where
interfaces don't yet exist.
"""

from typing import Any

from src.links.models.url import URL, URLStatus
from src.links.repositories.folder_repository import FolderRepository
from src.links.repositories.tag_repository import TagRepository
from src.shared.core.interfaces import (
    IAuditService,
    IEventDispatcher,
    IPasswordService,
    IURLRepository,
    IWebhookService,
    IWorkspaceRepository,
)
from src.shared.errors import (
    FolderNotInWorkspace,
    RoleTooLow,
    URLNotFound,
)
from src.workspaces.models.workspace_member import MemberRole


class URLUpdateService:
    """Update existing short URLs. Single responsibility: updates only."""

    def __init__(
        self,
        url_repo: IURLRepository,
        workspace_repo: IWorkspaceRepository,
        folder_repo: FolderRepository,
        tag_repo: TagRepository,
        audit: IAuditService,
        webhooks: IWebhookService,
        event_dispatcher: IEventDispatcher,
        password_service: IPasswordService,
    ):
        self.url_repo = url_repo
        self.workspace_repo = workspace_repo
        self.folder_repo = folder_repo
        self.tag_repo = tag_repo
        self.audit = audit
        self.webhooks = webhooks
        self.event_dispatcher = event_dispatcher
        self.password_service = password_service

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

    async def update(self, id: int, payload: Any, user_id: int) -> URL:
        url = await self.url_repo.get(id)
        if not url or url.status == URLStatus.deleted:
            raise URLNotFound()
        await self._verify_workspace_access(url.workspace_id, user_id)
        await self._verify_write_role(url.workspace_id, user_id)

        before = {
            "original_url": url.original_url,
            "status": url.status.value,
            "folder_id": url.folder_id,
        }

        if payload.folder_id is not None:
            if not await self.folder_repo.folder_belongs_to_workspace(
                payload.folder_id, url.workspace_id
            ):
                raise FolderNotInWorkspace()
            url.folder_id = payload.folder_id

        if payload.original_url is not None:
            url.original_url = str(payload.original_url)

        if payload.domain is not None:
            url.domain = payload.domain

        # password: omitted => keep; explicit null => clear; explicit string => set.
        if "password" in payload.model_fields_set:
            url.password_hash = await self.password_service.hash(
                payload.password
            )

        if payload.is_ab_test is not None:
            url.is_ab_test = payload.is_ab_test

        if payload.ios_url is not None:
            url.ios_url = str(payload.ios_url) if payload.ios_url else None

        if payload.android_url is not None:
            url.android_url = str(payload.android_url) if payload.android_url else None

        # expires_at: omitted => keep; explicit null => clear; explicit value => set.
        if "expires_at" in payload.model_fields_set:
            url.expires_at = payload.expires_at

        if payload.status is not None:
            url.status = payload.status

        if payload.tags is not None:
            db_tags = []
            for tag_name in set(payload.tags):
                tag = await self.tag_repo.get_or_create(
                    tag_name, url.workspace_id
                )
                db_tags.append(tag)
            url.tags = db_tags

        await self.url_repo.commit()
        await self.url_repo.flush()

        refetched = await self.url_repo.get(url.id)
        assert refetched is not None
        url = refetched

        after = {
            "original_url": url.original_url,
            "status": url.status.value,
            "folder_id": url.folder_id,
        }

        try:
            await self.audit.log(
                actor_id=user_id,
                action="update",
                resource_type="url",
                resource_id=url.id,
                before=before,
                after=after,
                workspace_id=url.workspace_id,
            )
        except Exception:
            await self.url_repo.rollback()
            raise

        await self.webhooks.deliver_event(
            url.workspace_id,
            "url.updated",
            {
                "short_code": url.short_code,
                "original_url": url.original_url,
                "workspace_id": url.workspace_id,
                "user_id": user_id,
            },
        )

        result = await self.url_repo.get(url.id)
        assert result is not None
        return result

    async def update_qr(self, id: int, qr_b64: str, user_id: int) -> None:
        url = await self.url_repo.get(id)
        if not url or url.status == URLStatus.deleted:
            raise URLNotFound()
        await self._verify_workspace_access(url.workspace_id, user_id)
        await self._verify_write_role(url.workspace_id, user_id)
        await self.url_repo.update(id, qr_code=qr_b64)
