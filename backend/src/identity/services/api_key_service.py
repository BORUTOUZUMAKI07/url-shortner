import secrets
from datetime import datetime, timedelta, timezone

from src.identity.models.api_key import APIKeyStatus
from src.identity.repositories.api_key_repository import APIKeyRepository
from src.identity.repositories.user_repository import UserRepository
from src.shared.core.api_key_auth import APIKeyQuotaManager
from src.shared.core.redis import redis_client
from src.shared.core.security import hash_password_async
from src.shared.errors import NotFoundError


class APIKeyService:
    def __init__(self, repo: APIKeyRepository, user_repo: UserRepository):
        self.repo = repo
        self.user_repo = user_repo

    def _generate_raw_key(self) -> str:
        return "lf_" + secrets.token_urlsafe(32)

    async def create(self, name: str, user_id: int, expires_at=None):
        raw_key = self._generate_raw_key()
        key_hash = await hash_password_async(raw_key)
        prefix = raw_key[:8]
        api_key = await self.repo.create(
            user_id=user_id,
            name=name,
            prefix=prefix,
            key_hash=key_hash,
            expires_at=expires_at,
        )
        return api_key, raw_key

    async def list(self, user_id: int):
        return await self.repo.get_user_keys(user_id)

    async def revoke(self, id: int, user_id: int):
        key = await self.repo.revoke(id, user_id)
        if not key:
            raise NotFoundError("API key not found.")
        return key

    async def rotate(self, id: int, user_id: int):
        old_key = await self.repo.get(id)
        if not old_key or old_key.user_id != user_id:
            raise NotFoundError("API key not found.")
        await self.repo.revoke(id, user_id)
        raw_key = self._generate_raw_key()
        new_key = await self.repo.create(
            user_id=user_id,
            name=old_key.name,
            prefix=raw_key[:8],
            key_hash=await hash_password_async(raw_key),
            expires_at=old_key.expires_at,
        )
        return new_key, raw_key

    async def get_quota(self, id: int, user_id: int):
        key = await self.repo.get(id)
        if not key or key.user_id != user_id:
            raise NotFoundError("API key not found.")
        user = await self.user_repo.get(user_id)
        if not user:
            raise NotFoundError("User not found.")
        daily_limit = APIKeyQuotaManager.get_quota_for_user(user.plan)
        remaining = await APIKeyQuotaManager.get_remaining_quota(key.id, user.plan)
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return {
            "api_key_id": key.id,
            "remaining_quota": remaining,
            "daily_limit": daily_limit,
            "resets_at": tomorrow.isoformat() + "Z",
        }

    async def get_aggregate_quota(self, user_id: int):
        """Aggregate daily quota usage across the user's active keys.

        The quota is enforced per-user (by plan) but tracked per key in Redis,
        so the dashboard needs a single call that sums the per-key counters.
        The counters are read in ONE MGET instead of one round trip per key.
        """
        keys = await self.repo.get_user_keys(user_id)
        user = await self.user_repo.get(user_id)
        if not user:
            raise NotFoundError("User not found.")
        daily_limit = APIKeyQuotaManager.get_quota_for_user(user.plan)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        active_keys = [k for k in keys if k.status == APIKeyStatus.active]
        counters = []
        if active_keys:
            counters = await redis_client.mget(
                *(f"api_key_quota:{k.id}:{today}" for k in active_keys)
            )
        used = min(daily_limit, sum(max(0, int(c)) if c else 0 for c in counters))
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return {
            "used": used,
            "limit": daily_limit,
            "remaining": max(0, daily_limit - used),
            "resets_at": tomorrow.isoformat() + "Z",
        }
