from src.identity.models.user import User
from src.identity.repositories.user_repository import UserRepository
from src.links.models.url import URL
from src.links.repositories.url_repository import URLRepository
from src.shared.errors import BadRequestError, NotFoundError
from src.workspaces.models.workspace import Workspace
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


class AdminService:
    def __init__(
        self,
        user_repo: UserRepository,
        workspace_repo: WorkspaceRepository,
        url_repo: URLRepository,
    ):
        self.user_repo = user_repo
        self.workspace_repo = workspace_repo
        self.url_repo = url_repo

    async def seed_superadmin(self, current_user: User) -> str:
        if await self.user_repo.get_by(is_superadmin=True):
            raise BadRequestError("Superadmin already exists")
        await self.user_repo.update(current_user.id, is_superadmin=True)
        return current_user.email

    async def list_users(self, skip: int, limit: int) -> tuple[int, list[User]]:
        total = await self.user_repo.count()
        users = await self.user_repo.list_all(skip=skip, limit=limit)
        return total, users

    async def get_user(self, user_id: int) -> User:
        user = await self.user_repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        return user

    async def toggle_superadmin(self, user_id: int) -> User:
        user = await self.get_user(user_id)
        await self.user_repo.update(user_id, is_superadmin=not user.is_superadmin)
        updated = await self.user_repo.get(user_id)
        assert updated is not None
        return updated

    async def delete_user(self, user_id: int) -> str:
        user = await self.get_user(user_id)
        await self.user_repo.delete(user_id)
        return user.email

    async def list_workspaces(self, skip: int, limit: int) -> tuple[int, list[Workspace]]:
        total = await self.workspace_repo.count()
        workspaces = await self.workspace_repo.list_all(skip=skip, limit=limit)
        return total, workspaces

    async def list_all_urls(self, skip: int, limit: int) -> tuple[int, list[URL]]:
        total = await self.url_repo.count()
        urls = await self.url_repo.list_all(skip=skip, limit=limit)
        return total, urls

    async def platform_stats(self) -> dict:
        return {
            "total_users": await self.user_repo.count(),
            "total_workspaces": await self.workspace_repo.count(),
            "total_urls": await self.url_repo.count(),
        }
