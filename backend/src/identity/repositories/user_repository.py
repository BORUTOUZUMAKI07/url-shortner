from sqlalchemy import func, select

from src.identity.models.user import User
from src.shared.core.base_repository import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, db):
        super().__init__(User, db)

    async def get_by_email(self, email: str) -> User | None:
        return await self.get_by(email=email)

    # Provider-subject lookups. These are the ONLY safe way to map an OAuth
    # identity onto a local account - the provider's "sub" is immutable,
    # whereas an email address can be re-pointed by whoever controls the
    # provider account.
    async def get_by_oauth_sub(self, provider: str, subject: str) -> User | None:
        """Resolve an OAuth identity to a user by its provider subject.

        This is the ONLY way an OAuth caller is resolved. It is deliberately not
        a pair of `get_by_google_id` / `get_by_github_id` helpers — those existed
        and had no callers, because the provider-specific column is only ever
        needed behind this dispatch.
        """
        column = {"google": User.google_id, "github": User.github_id}.get(provider)
        if column is None:
            return None
        result = await self.db.execute(select(User).where(column == subject))
        return result.scalar_one_or_none()

    async def count_superadmins(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(User).where(User.is_superadmin.is_(True))
        )
        return result.scalar_one()  # type: ignore[no-any-return]

    async def email_exists(self, email: str) -> bool:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none() is not None
