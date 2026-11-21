"""
URLService — Facade that delegates to SRP-compliant sub-services.

Maintains full backward compatibility: all existing imports of URLService
continue to work. Each public method delegates to the corresponding
single-responsibility service:

- create  -> URLCreationService
- update  -> URLUpdateService
- delete  -> URLDeletionService
- list    -> URLQueryService
- get     -> URLQueryService
- update_qr -> QRCodeService (set via set_qr_service)
"""

from typing import Any, Optional

from src.links.models.url import URL
from src.links.repositories.folder_repository import FolderRepository
from src.links.repositories.tag_repository import TagRepository
from src.links.services.url_creation_service import URLCreationService
from src.links.services.url_deletion_service import URLDeletionService
from src.links.services.url_query_service import URLQueryService
from src.links.services.url_update_service import URLUpdateService
from src.shared.core.interfaces import (
    IAuditService,
    IEventDispatcher,
    IURLRepository,
    IWorkspaceRepository,
)
from src.webhooks.services.webhook_service import WebhookService

# Re-exported for backward compatibility (bulk_service imports this)
RESERVED_ALIASES = {
    "admin", "api", "login", "register", "logout", "verify", "reset",
    "health", "metrics", "dashboard",
}


class URLService:
    """
    Facade over SRP-compliant URL sub-services.

    Depends on concrete repositories where interfaces don't yet exist
    (FolderRepository, TagRepository) and on abstractions where they do
    (IURLRepository, IWorkspaceRepository, etc.).
    """

    def __init__(
        self,
        url_repo: IURLRepository,
        workspace_repo: IWorkspaceRepository,
        folder_repo: FolderRepository,
        tag_repo: TagRepository,
        audit: IAuditService,
        webhooks: WebhookService,
        event_dispatcher: IEventDispatcher,
    ):
        self._creation = URLCreationService(
            url_repo=url_repo,
            workspace_repo=workspace_repo,
            folder_repo=folder_repo,
            tag_repo=tag_repo,
            audit=audit,
            webhooks=webhooks,
            event_dispatcher=event_dispatcher,
            password_service=self,
        )
        self._update = URLUpdateService(
            url_repo=url_repo,
            workspace_repo=workspace_repo,
            folder_repo=folder_repo,
            tag_repo=tag_repo,
            audit=audit,
            webhooks=webhooks,
            event_dispatcher=event_dispatcher,
            password_service=self,
        )
        self._deletion = URLDeletionService(
            url_repo=url_repo,
            workspace_repo=workspace_repo,
            audit=audit,
            webhooks=webhooks,
            event_dispatcher=event_dispatcher,
        )
        self._query = URLQueryService(
            url_repo=url_repo,
            workspace_repo=workspace_repo,
        )
        self._qr_service = None

    def set_qr_service(self, qr_service) -> None:
        """Set the QR code service (called by deps.py after construction)."""
        self._qr_service = qr_service

    # ---- IPasswordService implementation (delegated by creation/update) ----

    async def hash(self, password: Optional[str]) -> Optional[str]:
        from src.shared.core.security import hash_password_async

        if password is None:
            return None
        return await hash_password_async(password)

    # ---- Creation ----

    async def create(self, payload: Any, user_id: int) -> URL:
        return await self._creation.create(payload, user_id)

    # ---- Query ----

    async def list(self, workspace_id: int | None, user_id: int, **filters) -> dict:
        return await self._query.list(workspace_id, user_id, **filters)

    async def get(self, id: int, user_id: int) -> URL:
        return await self._query.get(id, user_id)

    # ---- Update ----

    async def update(self, id: int, payload: Any, user_id: int) -> URL:
        return await self._update.update(id, payload, user_id)

    async def update_qr(self, id: int, qr_b64: str, user_id: int) -> None:
        if self._qr_service is not None:
            await self._qr_service.generate(id, user_id)
        else:
            # Fallback: direct repository update (no access check beyond get)
            await self._query.get(id, user_id)
            await self._creation.url_repo.update(id, qr_code=qr_b64)

    # ---- Deletion ----

    async def delete(self, id: int, user_id: int) -> None:
        await self._deletion.delete(id, user_id)
