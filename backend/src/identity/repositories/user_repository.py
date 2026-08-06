from sqlalchemy import select

from src.identity.models.user import User
from src.shared.core.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db):
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> User | None:
        return await self.get_by(email=email)

    async def get_by_google_id(self, google_id: str) -> User | None:
        return await self.get_by(google_id=google_id)

    async def email_exists(self, email: str) -> bool:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none() is not None
