from sqlalchemy import and_, delete, select
from sqlalchemy.orm import selectinload

from src.shared.core.base_repository import BaseRepository
from src.workspaces.models.workspace_member import MemberRole, WorkspaceMember


class WorkspaceMemberRepository(BaseRepository[WorkspaceMember]):
    def __init__(self, db):
        super().__init__(WorkspaceMember, db)

    async def get_member(self, workspace_id: int, user_id: int) -> WorkspaceMember | None:
        return await self.get_by(workspace_id=workspace_id, user_id=user_id)

    async def get_workspace_members(self, workspace_id: int) -> list[WorkspaceMember]:
        stmt = select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id).options(selectinload(WorkspaceMember.user))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def is_member(self, workspace_id: int, user_id: int) -> bool:
        return await self.get_member(workspace_id, user_id) is not None

    async def add_member(self, workspace_id: int, user_id: int, role: MemberRole = MemberRole.editor) -> WorkspaceMember:
        return await self.create(workspace_id=workspace_id, user_id=user_id, role=role)

    async def update_role(self, workspace_id: int, user_id: int, role: MemberRole) -> WorkspaceMember | None:
        member = await self.get_member(workspace_id, user_id)
        if not member:
            return None
        return await self.update(member.id, role=role)

    async def remove_member(self, workspace_id: int, user_id: int) -> bool:
        stmt = delete(WorkspaceMember).where(
            and_(WorkspaceMember.workspace_id == workspace_id, WorkspaceMember.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0  # type: ignore[attr-defined, no-any-return]

    async def get_user_workspace_ids(self, user_id: int) -> list[int]:
        result = await self.db.execute(
            select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id)
        )
        return [row[0] for row in result.all()]

    async def get_role(self, workspace_id: int, user_id: int) -> MemberRole | None:
        member = await self.get_member(workspace_id, user_id)
        return member.role if member else None
