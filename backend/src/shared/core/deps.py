import time
from datetime import datetime, timezone

from fastapi import Depends, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.identity.models.user import User
from src.shared.core.database import get_db
from src.shared.core.redis import redis_client
from src.shared.core.security import decode_token, verify_password

# Positive-only cache for JWT blacklist checks — avoids a Redis REST round-trip
# on every request while a token is known to be revoked. A token that is NOT in
# the cache is never treated as revoked, so revocation is immediate: the first
# check after blacklisting hits Redis and returns TokenRevoked. The cache entry
# is short-lived and the authoritative source is always Redis.
_blacklist_cache: dict[str, float] = {}
_BLACKLIST_CACHE_TTL = 60  # seconds
from src.admin.services.admin_service import AdminService
from src.analytics.repositories.analytics_repository import AnalyticsRepository
from src.analytics.repositories.audit_log_repository import AuditLogRepository
from src.analytics.services.analytics_service import AnalyticsService
from src.analytics.services.audit_service import AuditService
from src.analytics.services.billing_service import BillingService
from src.identity.models.api_key import APIKeyStatus
from src.identity.repositories.api_key_repository import APIKeyRepository
from src.identity.repositories.user_repository import UserRepository
from src.identity.services.api_key_service import APIKeyService
from src.identity.services.auth_service import AuthService
from src.identity.services.profile_service import ProfileService
from src.links.repositories.favorite_repository import FavoriteRepository
from src.links.repositories.folder_repository import FolderRepository
from src.links.repositories.tag_repository import TagRepository
from src.links.repositories.url_repository import URLRepository
from src.links.services.bulk_service import BulkService
from src.links.services.favorite_service import FavoriteService
from src.links.services.folder_service import FolderService
from src.links.services.redirect_service import RedirectService
from src.links.services.tag_service import TagService
from src.links.services.url_service import URLService
from src.shared.core.api_key_auth import verify_api_key_quota
from src.shared.errors import InvalidToken, TokenRevoked, UnauthorizedError, UserNotFound
from src.shared.events.dispatcher import KafkaEventDispatcher
from src.webhooks.repositories.webhook_receiver_repository import WebhookReceivedEventRepository
from src.webhooks.repositories.webhook_repository import WebhookRepository
from src.webhooks.services.webhook_receiver_service import WebhookReceiverService
from src.webhooks.services.webhook_service import WebhookService
from src.workspaces.repositories.workspace_invite_repository import WorkspaceInviteRepository
from src.workspaces.repositories.workspace_member_repository import WorkspaceMemberRepository
from src.workspaces.repositories.workspace_repository import WorkspaceRepository
from src.workspaces.services.workspace_service import WorkspaceService


class PaginationParams:
    """Reusable pagination dependency — skip, limit, sort."""
    def __init__(
        self,
        skip: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(20, ge=1, le=100, description="Max records per page"),
        sort_by: str = Query("created_at", description="Sort field"),
        sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    ):
        self.skip = skip
        self.limit = limit
        self.sort_by = sort_by
        self.sort_order = sort_order

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials

    # API key auth (lf_ prefix)
    if token.startswith("lf_"):
        prefix = token[:8]
        key_record = await APIKeyRepository(db).get_by_prefix(prefix)
        if not key_record:
            raise UnauthorizedError("Invalid API key")
        if key_record.status != APIKeyStatus.active:
            raise UnauthorizedError("API key has been revoked")
        if not verify_password(token, key_record.key_hash):
            raise UnauthorizedError("Invalid API key")
        if key_record.expires_at and key_record.expires_at < datetime.now(timezone.utc):
            raise UnauthorizedError("API key has expired")
        key_record.last_used_at = datetime.now(timezone.utc)
        await db.commit()
        user = await UserRepository(db).get(key_record.user_id)
        if not user:
            raise UserNotFound()
        # Enforce the daily per-key quota (previously defined but never wired in).
        await verify_api_key_quota(key_record.id, user.plan)
        return user

    # JWT auth
    now = time.time()
    cached = _blacklist_cache.get(token)
    if cached is not None and cached > now:
        raise TokenRevoked()
    if cached is None:
        is_blacklisted = await redis_client.get(f"jwt:blacklist:{token}")
        if is_blacklisted:
            _blacklist_cache[token] = now + _BLACKLIST_CACHE_TTL
            raise TokenRevoked()
    payload = decode_token(token)
    user_id = payload.get("sub")
    token_type = payload.get("type")
    if not user_id or token_type != "access":
        raise InvalidToken()
    user = await UserRepository(db).get(int(user_id))
    if not user:
        raise UserNotFound()
    return user


async def get_audit_service(db: AsyncSession = Depends(get_db)) -> AuditService:
    return AuditService(
        repo=AuditLogRepository(db),
        workspace_repo=WorkspaceRepository(db),
    )


async def get_profile_service(db: AsyncSession = Depends(get_db)) -> ProfileService:
    return ProfileService(repo=UserRepository(db))


async def get_billing_service(db: AsyncSession = Depends(get_db)) -> BillingService:
    return BillingService(repo=UserRepository(db))


async def get_admin_service(db: AsyncSession = Depends(get_db)) -> AdminService:
    return AdminService(
        user_repo=UserRepository(db),
        workspace_repo=WorkspaceRepository(db),
        url_repo=URLRepository(db),
    )


async def get_webhook_service(db: AsyncSession = Depends(get_db)) -> WebhookService:
    return WebhookService(
        repo=WebhookRepository(db),
        workspace_repo=WorkspaceRepository(db),
    )


async def get_url_service(
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    webhooks: WebhookService = Depends(get_webhook_service),
) -> URLService:
    return URLService(
        url_repo=URLRepository(db),
        workspace_repo=WorkspaceRepository(db),
        folder_repo=FolderRepository(db),
        tag_repo=TagRepository(db),
        audit=audit,
        webhooks=webhooks,
        event_dispatcher=KafkaEventDispatcher(),
    )


async def get_workspace_service(
    db: AsyncSession = Depends(get_db),
    audit: AuditService = Depends(get_audit_service),
    webhook_svc: WebhookService = Depends(get_webhook_service),
) -> WorkspaceService:
    return WorkspaceService(
        repo=WorkspaceRepository(db),
        member_repo=WorkspaceMemberRepository(db),
        invite_repo=WorkspaceInviteRepository(db),
        user_repo=UserRepository(db),
        audit=audit,
        webhook_svc=webhook_svc,
    )


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(
        user_repo=UserRepository(db),
        workspace_repo=WorkspaceRepository(db),
    )


async def get_folder_service(db: AsyncSession = Depends(get_db)) -> FolderService:
    return FolderService(
        repo=FolderRepository(db),
        workspace_repo=WorkspaceRepository(db),
    )


async def get_tag_service(db: AsyncSession = Depends(get_db)) -> TagService:
    return TagService(
        repo=TagRepository(db),
        workspace_repo=WorkspaceRepository(db),
    )


async def get_favorite_service(db: AsyncSession = Depends(get_db)) -> FavoriteService:
    return FavoriteService(
        repo=FavoriteRepository(db),
        url_repo=URLRepository(db),
    )


async def get_analytics_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(
        url_repo=URLRepository(db),
        analytics_repo=AnalyticsRepository(db),
        workspace_repo=WorkspaceRepository(db),
    )


async def get_api_key_service(db: AsyncSession = Depends(get_db)) -> APIKeyService:
    return APIKeyService(
        repo=APIKeyRepository(db),
        user_repo=UserRepository(db),
    )


async def get_bulk_service(db: AsyncSession = Depends(get_db)) -> BulkService:
    return BulkService(
        url_repo=URLRepository(db),
        folder_repo=FolderRepository(db),
        tag_repo=TagRepository(db),
        workspace_repo=WorkspaceRepository(db),
    )


async def get_redirect_service(db: AsyncSession = Depends(get_db)) -> RedirectService:
    return RedirectService(
        url_repo=URLRepository(db),
        workspace_repo=WorkspaceRepository(db),
        events=KafkaEventDispatcher(),
    )


async def get_webhook_receiver_service(db: AsyncSession = Depends(get_db)) -> WebhookReceiverService:
    return WebhookReceiverService(
        repo=WebhookReceivedEventRepository(db),
        webhook_repo=WebhookRepository(db),
        workspace_repo=WorkspaceRepository(db),
    )
