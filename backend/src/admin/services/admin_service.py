from src.identity.models.user import User
from src.identity.repositories.user_repository import UserRepository
from src.identity.services.session_revocation import revoke_refresh_family
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

    async def _assert_not_last_active_admin(self, user: User, acting_user_id: int) -> None:
        """Refuse any change that would remove the platform's ability to recover.

        Two ways to lock everyone out permanently: demoting or deactivating the
        final superadmin, and an admin removing their own access by mistake.
        Both are silent, irreversible through the UI, and require a direct
        database edit to undo.
        """
        if not user.is_superadmin or not user.is_active:
            return
        if user.id == acting_user_id:
            raise BadRequestError(
                "You cannot change your own superadmin/active status — ask another admin."
            )
        if await self.user_repo.count_superadmins() <= 1:
            raise BadRequestError(
                "Refusing to remove the last active superadmin. Promote another user first."
            )

    async def toggle_superadmin(self, user_id: int, acting_user_id: int | None = None) -> User:
        user = await self.get_user(user_id)
        if user.is_superadmin:
            await self._assert_not_last_active_admin(user, acting_user_id or user_id)
        await self.user_repo.update(user_id, is_superadmin=not user.is_superadmin)
        updated = await self.user_repo.get(user_id)
        assert updated is not None
        return updated

    async def toggle_active(self, user_id: int, acting_user_id: int | None = None) -> User:
        user = await self.get_user(user_id)
        if user.is_active:
            await self._assert_not_last_active_admin(user, acting_user_id or user_id)
        new_state = not user.is_active
        await self.user_repo.update(user_id, is_active=new_state)
        if not new_state:
            # A deactivated user must not keep an active session.
            await revoke_refresh_family(user_id)
        updated = await self.user_repo.get(user_id)
        assert updated is not None
        return updated

    async def delete_user(self, user_id: int, acting_user_id: int | None = None) -> str:
        user = await self.get_user(user_id)
        # Hard delete cascades the user's workspaces, URLs and membership rows.
        # Do it to the wrong account and there is no undo — prefer
        # toggle_active, which is reversible.
        #
        # The self-delete check comes FIRST, and unconditionally: run after
        # _assert_not_last_active_admin it was only reachable for non-superadmins
        # (the helper returns early for everyone else), so a superadmin deleting
        # themselves got the generic "ask another admin" message instead of the
        # actionable "deactivate it instead".
        if user_id == acting_user_id:
            raise BadRequestError(
                "You cannot delete your own account from the admin panel — deactivate it instead."
            )
        await self._assert_not_last_active_admin(user, acting_user_id or user_id)
        await revoke_refresh_family(user_id)
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
