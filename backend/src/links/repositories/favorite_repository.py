from sqlalchemy import and_, delete, select

from src.links.models.favorite import Favorite
from src.shared.core.base_repository import BaseRepository


class FavoriteRepository(BaseRepository[Favorite]):
    def __init__(self, db):
        super().__init__(Favorite, db)

    async def get_by_user_and_url(self, user_id: int, url_id: int) -> Favorite | None:
        return await self.get_by(user_id=user_id, url_id=url_id)

    async def is_favorited(self, user_id: int, url_id: int) -> bool:
        return await self.get_by_user_and_url(user_id, url_id) is not None

    async def get_user_favorites(self, user_id: int, skip: int = 0, limit: int = 100) -> list[Favorite]:
        return await self.get_many(user_id=user_id, skip=skip, limit=limit)

    async def remove(self, user_id: int, url_id: int) -> bool:
        stmt = delete(Favorite).where(
            and_(Favorite.user_id == user_id, Favorite.url_id == url_id)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0  # type: ignore[attr-defined, no-any-return]

    async def count_user_favorites(self, user_id: int) -> int:
        stmt = select(Favorite).where(Favorite.user_id == user_id)
        result = await self.db.execute(stmt)
        return len(result.all())
