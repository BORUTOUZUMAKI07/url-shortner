from sqlalchemy import and_, select

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
        result = await self.db.execute(
            select(Workspace).where(
                and_(Workspace.id == workspace_id, Workspace.owner_id == user_id)
            )
        )
        workspace = result.scalar_one_or_none()
        if workspace:
            return workspace
        is_member = await self.db.execute(
            select(WorkspaceMember).where(
                and_(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == user_id,
                )
            )
        )
        if is_member.scalar_one_or_none():
            return await self.get(workspace_id)
        return None

    async def verify_role(self, workspace_id: int, user_id: int, min_role: MemberRole) -> bool:
        """True if the user owns the workspace or is a member with a role >= min_role."""
        owner = await self.db.execute(
            select(Workspace).where(
                and_(Workspace.id == workspace_id, Workspace.owner_id == user_id)
            )
        )
        if owner.scalar_one_or_none():
            return True
        member = await self.db.execute(
            select(WorkspaceMember).where(
                and_(
                    WorkspaceMember.workspace_id == workspace_id,
                    WorkspaceMember.user_id == user_id,
                )
            )
        )
        m = member.scalar_one_or_none()
        if not m:
            return False
        return ROLE_HIERARCHY.get(m.role, 0) >= ROLE_HIERARCHY.get(min_role, 0)

    async def create_default(self, user_id: int) -> Workspace:
        ws = await self.create(name="Personal Workspace", owner_id=user_id)
        from src.workspaces.models.workspace_member import MemberRole
        from src.workspaces.repositories.workspace_member_repository import WorkspaceMemberRepository
        member_repo = WorkspaceMemberRepository(self.db)
        await member_repo.add_member(ws.id, user_id, MemberRole.admin)
        return ws
