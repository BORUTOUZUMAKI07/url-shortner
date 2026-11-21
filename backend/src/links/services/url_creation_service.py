"""
URLCreationService — Single Responsibility: create new short URLs.

Depends on abstractions where available (IURLRepository, IWorkspaceRepository,
IEventDispatcher, IAuditService, IWebhookService, IPasswordService) and concrete
repositories where interfaces don't yet exist (FolderRepository, TagRepository).
"""

from typing import Any

from sqlalchemy.exc import IntegrityError

from src.links.models.url import URL, URLStatus
from src.links.repositories.folder_repository import FolderRepository
from src.links.repositories.tag_repository import TagRepository
from src.shared.core.config import settings
from src.shared.core.interfaces import (
    IAuditService,
    IEventDispatcher,
    IPasswordService,
    IURLRepository,
    IWebhookService,
    IWorkspaceRepository,
)
from src.shared.errors import (
    AliasConflict,
    AliasReserved,
    FolderNotInWorkspace,
    RoleTooLow,
    WorkspaceNotFound,
)
from src.workspaces.models.workspace_member import MemberRole

RESERVED_ALIASES = {
    "admin", "api", "login", "register", "logout", "verify", "reset",
    "health", "metrics", "dashboard",
}


class URLCreationService:
    """Create new short URLs. Single responsibility: creation only."""

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
            raise WorkspaceNotFound()

    async def _verify_write_role(
        self, workspace_id: int, user_id: int
    ):
        if not await self.workspace_repo.verify_role(
            workspace_id, user_id, MemberRole.editor
        ):
            raise RoleTooLow("editor")

    async def create(self, payload: Any, user_id: int) -> URL:
        await self._verify_workspace_access(payload.workspace_id, user_id)
        await self._verify_write_role(payload.workspace_id, user_id)

        if payload.folder_id:
            if not await self.folder_repo.folder_belongs_to_workspace(
                payload.folder_id, payload.workspace_id
            ):
                raise FolderNotInWorkspace()

        short_code = None
        if payload.custom_alias:
            alias = payload.custom_alias.strip().lower()
            if alias in RESERVED_ALIASES:
                raise AliasReserved(alias)
            if await self.url_repo.alias_exists(alias):
                raise AliasConflict()
            short_code = alias
        else:
            short_code = await self.url_repo.next_short_code()

        password_hash = await self.password_service.hash(payload.password)

        url = URL(
            short_code=short_code,
            original_url=str(payload.original_url),
            user_id=user_id,
            workspace_id=payload.workspace_id,
            folder_id=payload.folder_id,
            custom_alias=payload.custom_alias,
            domain=payload.domain,
            password_hash=password_hash,
            is_ab_test=payload.is_ab_test,
            is_one_time=payload.is_one_time,
            ios_url=str(payload.ios_url) if payload.ios_url else None,
            android_url=str(payload.android_url) if payload.android_url else None,
            expires_at=payload.expires_at,
            status=URLStatus.active,
        )

        if payload.tags:
            db_tags = []
            for tag_name in set(payload.tags):
                tag = await self.tag_repo.get_or_create(
                    tag_name, payload.workspace_id
                )
                db_tags.append(tag)
            url.tags = db_tags

        try:
            url = await self.url_repo.create_url(url)
        except IntegrityError:
            await self.url_repo.rollback()
            raise AliasConflict()

        try:
            await self.event_dispatcher.dispatch(
                "url-created",
                {
                    "short_code": url.short_code,
                    "original_url": url.original_url,
                    "workspace_id": url.workspace_id,
                    "user_id": url.user_id,
                    "base_url": settings.FRONTEND_URL,
                },
                key=url.short_code,
            )
        except Exception:
            # Event dispatch is fire-and-forget
            pass

        try:
            await self.audit.log(
                actor_id=user_id,
                action="create",
                resource_type="url",
                resource_id=url.id,
                after={
                    "short_code": url.short_code,
                    "original_url": url.original_url,
                },
                workspace_id=payload.workspace_id,
            )
        except Exception:
            await self.url_repo.rollback()
            refetched = await self.url_repo.get(url.id)
            assert refetched is not None
            url = refetched

        await self.webhooks.deliver_event(
            payload.workspace_id,
            "url.created",
            {
                "short_code": url.short_code,
                "original_url": url.original_url,
                "workspace_id": url.workspace_id,
                "user_id": user_id,
            },
        )

        return url
