from sqlalchemy import and_, or_, select

from src.shared.core.base_repository import BaseRepository
from src.workspaces.models.workspace import Workspace
from src.workspaces.models.workspace_member import ROLE_HIERARCHY, MemberRole, WorkspaceMember


class WorkspaceRepository(BaseRepository[Workspace]):
    def __init__(self, db):
        super().__init__(Workspace, db)

    async def get_user_workspaces(self, user_id: int) -> list[Workspace]:
        owned = await self.get_many(owner_id=user_id)
        member_rows = await self.db.execute(
            select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id)
        )
        member_ids = [row[0] for row in member_rows.all() if row[0] not in {w.id for w in owned}]
        if not member_ids:
            return owned
        result = await self.db.execute(
            select(Workspace).where(Workspace.id.in_(member_ids))
        )
        return owned + list(result.scalars().all())

    async def verify_access(self, workspace_id: int, user_id: int) -> Workspace | None:
        # Single query: owner OR member via a LEFT JOIN — previously two
        # sequential round trips (owner SELECT, then member SELECT).
        result = await self.db.execute(
            select(Workspace)
            .outerjoin(
                WorkspaceMember,
                and_(WorkspaceMember.workspace_id == Workspace.id, WorkspaceMember.user_id == user_id),
            )
            .where(
                and_(
                    Workspace.id == workspace_id,
                    or_(Workspace.owner_id == user_id, WorkspaceMember.user_id == user_id),
                )
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def verify_role(self, workspace_id: int, user_id: int, min_role: MemberRole) -> bool:
        """True if the user is the workspace owner or a member with a role >= min_role.
        The owner always retains full access, regardless of any membership row."""
        result = await self.db.execute(
            select(Workspace.owner_id, WorkspaceMember.role)
            .outerjoin(
                WorkspaceMember,
                and_(WorkspaceMember.workspace_id == Workspace.id, WorkspaceMember.user_id == user_id),
            )
            .where(Workspace.id == workspace_id)
            .limit(1)
        )
        row = result.first()
        if not row:
            return False
        owner_id, role = row
        if owner_id == user_id:
            return True
        return ROLE_HIERARCHY.get(role, 0) >= ROLE_HIERARCHY.get(min_role, 0)

    async def create_default(self, user_id: int) -> Workspace:
        ws = await self.create(name="Personal Workspace", owner_id=user_id)
        from src.workspaces.models.workspace_member import MemberRole
        from src.workspaces.repositories.workspace_member_repository import WorkspaceMemberRepository
        member_repo = WorkspaceMemberRepository(self.db)
        await member_repo.add_member(ws.id, user_id, MemberRole.admin)
        return ws
