from src.identity.models.user import User
from src.identity.repositories.user_repository import UserRepository
from src.shared.core.security import hash_password_async, verify_password_async
from src.shared.errors import EmailAlreadyExists, InvalidCredentials


class ProfileService:
    def __init__(self, repo: UserRepository):
        self.repo = repo

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not await verify_password_async(current_password, user.password_hash):
            raise InvalidCredentials()
        await self.repo.update(user.id, password_hash=await hash_password_async(new_password))

    async def change_email(self, user: User, current_password: str, new_email: str) -> None:
        if not await verify_password_async(current_password, user.password_hash):
            raise InvalidCredentials()
        if await self.repo.email_exists(new_email):
            raise EmailAlreadyExists()
        await self.repo.update(user.id, email=new_email, is_verified=False)

    async def upload_avatar(self, user: User, avatar: str) -> None:
        await self.repo.update(user.id, avatar_url=avatar)
