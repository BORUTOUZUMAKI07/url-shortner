from datetime import datetime, timezone

from sqlalchemy import and_, select

from src.identity.models.api_key import APIKey, APIKeyStatus
from src.shared.core.base_repository import BaseRepository


class APIKeyRepository(BaseRepository[APIKey]):
    def __init__(self, db):
        super().__init__(APIKey, db)

    async def get_user_keys(self, user_id: int) -> list[APIKey]:
        return await self.get_many(user_id=user_id)

    async def get_by_prefix(self, prefix: str) -> APIKey | None:
        return await self.get_by(prefix=prefix)

    async def revoke(self, id: int, user_id: int) -> APIKey | None:
        result = await self.db.execute(
            select(APIKey).where(and_(APIKey.id == id, APIKey.user_id == user_id))
        )
        key = result.scalar_one_or_none()
        if key:
            key.status = APIKeyStatus.revoked
            await self.db.commit()
        return key

    async def update_last_used(self, id: int) -> None:
        key = await self.get(id)
        if key:
            key.last_used_at = datetime.now(timezone.utc)
            await self.db.commit()
