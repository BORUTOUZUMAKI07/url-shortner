from sqlalchemy import and_, select

from src.shared.core.base_repository import BaseRepository
from src.workspaces.models.workspace_invite import InviteStatus, WorkspaceInvite


class WorkspaceInviteRepository(BaseRepository[WorkspaceInvite]):
    def __init__(self, db):
        super().__init__(WorkspaceInvite, db)

    async def get_by_token(self, token: str) -> WorkspaceInvite | None:
        return await self.get_by(token=token)

    async def get_pending_for_email(self, workspace_id: int, email: str) -> WorkspaceInvite | None:
        return await self.get_by(workspace_id=workspace_id, email=email, status=InviteStatus.pending)

    async def get_workspace_invites(self, workspace_id: int) -> list[WorkspaceInvite]:
        return await self.get_many(workspace_id=workspace_id, status=InviteStatus.pending)

    async def accept(self, token: str) -> WorkspaceInvite | None:
        invite = await self.get_by_token(token)
        if not invite or invite.status != InviteStatus.pending:
            return None
        return await self.update(invite.id, status=InviteStatus.accepted)

    async def cancel(self, invite_id: int) -> WorkspaceInvite | None:
        invite = await self.get(invite_id)
        if not invite:
            return None
        return await self.update(invite.id, status=InviteStatus.cancelled)

    async def expire_stale(self) -> int:
        from datetime import datetime, timezone
        result = await self.db.execute(
            select(WorkspaceInvite).where(
                and_(
                    WorkspaceInvite.status == InviteStatus.pending,
                    WorkspaceInvite.expires_at < datetime.now(timezone.utc),
                )
            )
        )
        stale = result.scalars().all()
        for invite in stale:
            await self.update(invite.id, status=InviteStatus.expired)
        return len(stale)
