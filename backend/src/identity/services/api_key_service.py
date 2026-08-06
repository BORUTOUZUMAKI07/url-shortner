import secrets
from datetime import datetime, timedelta, timezone

from src.identity.repositories.api_key_repository import APIKeyRepository
from src.identity.repositories.user_repository import UserRepository
from src.shared.core.api_key_auth import APIKeyQuotaManager
from src.shared.core.security import hash_password
from src.shared.errors import NotFoundError


class APIKeyService:
    def __init__(self, repo: APIKeyRepository, user_repo: UserRepository):
        self.repo = repo
        self.user_repo = user_repo

    def _generate_raw_key(self) -> str:
        return "lf_" + secrets.token_urlsafe(32)

    async def create(self, name: str, user_id: int, expires_at=None):
        raw_key = self._generate_raw_key()
        key_hash = hash_password(raw_key)
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
            key_hash=hash_password(raw_key),
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
