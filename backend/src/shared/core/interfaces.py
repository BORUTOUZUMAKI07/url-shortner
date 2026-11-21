"""
SOLID-compliant protocol interfaces for repositories and services.

Using `Protocol` (structural subtyping) instead of `ABC` (nominal subtyping)
so concrete classes satisfy interfaces implicitly by having the right methods,
without explicit inheritance.
"""

from typing import Any, Optional, Protocol, TypeVar, runtime_checkable

from src.links.models.url import URL, URLStatus
from src.webhooks.models.webhook import Webhook
from src.workspaces.models.workspace import Workspace
from src.workspaces.models.workspace_member import MemberRole

# ---------------------------------------------------------------------------
# Generic repository interface
# ---------------------------------------------------------------------------

ModelType = TypeVar("ModelType", covariant=True)


@runtime_checkable
class IRepository(Protocol[ModelType]):
    """Generic repository contract."""

    async def get(self, id: int) -> Optional[ModelType]:
        ...

    async def create(self, **kwargs) -> ModelType:
        ...

    async def update(self, id: int, **values) -> Optional[ModelType]:
        ...

    async def delete(self, id: int) -> bool:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...

    async def flush(self) -> None:
        ...


# ---------------------------------------------------------------------------
# URL repository interface
# ---------------------------------------------------------------------------

@runtime_checkable
class IURLRepository(Protocol):
    """Contract for URL data access."""

    async def get_by_short_code(self, short_code: str) -> Optional[URL]:
        ...

    async def get_by_custom_alias(self, alias: str) -> Optional[URL]:
        ...

    async def get(self, id: int) -> Optional[URL]:
        ...

    async def alias_exists(self, alias: str) -> bool:
        ...

    async def get_workspace_urls(
        self,
        workspace_id: Optional[int],
        folder_id: Optional[int] = None,
        tag: Optional[str] = None,
        search: Optional[str] = None,
        status_filter: Optional[URLStatus] = None,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        url_ids: Optional[list[int]] = None,
    ) -> dict[str, object]:
        ...

    async def soft_delete(self, id: int) -> None:
        ...

    async def consume_one_time(self, id: int) -> int:
        ...

    async def bulk_update(
        self, url_ids: list[int], workspace_id: int, **values
    ) -> None:
        ...

    async def get_urls_by_ids(
        self, url_ids: list[int], workspace_id: int
    ) -> list[URL]:
        ...

    async def get_url_id_by_short_code(self, short_code: str) -> Optional[int]:
        ...

    async def get_url_ids_by_short_codes(
        self, short_codes: list[str]
    ) -> dict[str, int]:
        ...

    async def next_short_code(self) -> str:
        ...

    async def create_url(self, url: URL) -> URL:
        ...

    async def add_nested(self, url: URL) -> None:
        ...

    async def reactivate(
        self, url_ids: list[int], workspace_id: int
    ) -> int:
        ...

    async def get_all_workspace_urls(self, workspace_id: int) -> list[URL]:
        ...

    async def update_qr_code(self, id: int, qr_b64: str) -> None:
        ...

    async def update(self, id: int, **values) -> Optional[URL]:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...

    async def flush(self) -> None:
        ...


# ---------------------------------------------------------------------------
# Workspace repository interface
# ---------------------------------------------------------------------------

@runtime_checkable
class IWorkspaceRepository(Protocol):
    """Contract for workspace data access."""

    async def get(self, id: int) -> Optional[Workspace]:
        ...

    async def create(self, **kwargs) -> Workspace:
        ...

    async def verify_access(
        self, workspace_id: int, user_id: int
    ) -> Optional[Workspace]:
        ...

    async def verify_role(
        self,
        workspace_id: int,
        user_id: int,
        required_role: MemberRole,
    ) -> bool:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...


# ---------------------------------------------------------------------------
# Webhook repository interface
# ---------------------------------------------------------------------------

@runtime_checkable
class IWebhookRepository(Protocol):
    """Contract for webhook data access."""

    async def get(self, id: int) -> Optional[Webhook]:
        ...

    async def create(self, **kwargs) -> Webhook:
        ...

    async def list_by_workspace(
        self, workspace_id: int
    ) -> list[Webhook]:
        ...

    async def commit(self) -> None:
        ...

    async def rollback(self) -> None:
        ...


# ---------------------------------------------------------------------------
# Service interfaces
# ---------------------------------------------------------------------------

@runtime_checkable
class IURLCreationService(Protocol):
    """Contract for creating URLs (SRP: only creation logic)."""

    async def create(
        self, payload: Any, user_id: int
    ) -> URL:
        ...


@runtime_checkable
class IURLUpdateService(Protocol):
    """Contract for updating URLs (SRP: only update logic)."""

    async def update(
        self, id: int, payload: Any, user_id: int
    ) -> URL:
        ...

    async def update_qr(
        self, id: int, qr_b64: str, user_id: int
    ) -> None:
        ...


@runtime_checkable
class IURLDeletionService(Protocol):
    """Contract for deleting URLs (SRP: only deletion logic)."""

    async def delete(self, id: int, user_id: int) -> None:
        ...


@runtime_checkable
class IURLQueryService(Protocol):
    """Contract for reading URLs (SRP: only read/query logic)."""

    async def list(
        self,
        workspace_id: Optional[int],
        user_id: int,
        **filters,
    ) -> dict[str, object]:
        ...

    async def get(self, id: int, user_id: int) -> URL:
        ...


@runtime_checkable
class IQRCodeService(Protocol):
    """Contract for QR code generation (SRP: only QR logic)."""

    async def generate(
        self, short_code: str, backend_url: str
    ) -> str:
        ...


@runtime_checkable
class IWorkspaceService(Protocol):
    """Contract for workspace operations."""

    async def create(
        self, payload: Any, user_id: int
    ) -> Workspace:
        ...

    async def list(self, user_id: int) -> list[Workspace]:
        ...

    async def verify_access(
        self, workspace_id: int, user_id: int
    ) -> Optional[Workspace]:
        ...


@runtime_checkable
class IWebhookService(Protocol):
    """Contract for webhook delivery."""

    async def deliver_event(
        self,
        workspace_id: int,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        ...


@runtime_checkable
class IEventDispatcher(Protocol):
    """Contract for event publishing."""

    async def dispatch(
        self,
        topic: str,
        value: dict,
        key: Optional[str] = None,
    ) -> None:
        ...


@runtime_checkable
class IAuditService(Protocol):
    """Contract for audit logging."""

    async def log(
        self,
        actor_id: int,
        action: str,
        resource_type: str,
        resource_id: int,
        before: Optional[dict] = None,
        after: Optional[dict] = None,
        workspace_id: Optional[int] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        ...


@runtime_checkable
class IPasswordService(Protocol):
    """Contract for password hashing (SRP: only password logic)."""

    async def hash(self, password: Optional[str]) -> Optional[str]:
        ...
