from sqlalchemy import and_, select, update

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

    # NOTE: there used to be an `accept(token)` here — get the invite, check it
    # is pending, then update. That read-then-update is not atomic, and its None
    # return (meaning "no longer pending") was the one signal a concurrent
    # cancellation could trip; the caller discarded it. `claim_pending` replaces
    # it with a conditional UPDATE, which needs no re-read to be safe.

    async def claim_pending(self, invite_id: int) -> bool:
        """Atomically transition a still-pending invite to accepted.

        The conditional UPDATE is the authoritative gate, and it is atomic: of
        any number of concurrent accepts, exactly one sees rowcount == 1 and
        every other caller sees 0. A plain read of `status` cannot do this, which
        is how a cancelled invite used to still hand out membership.

        This deliberately does NOT commit. The caller inserts the membership row
        next and lets that single commit persist both, so an invite can never be
        consumed without the membership it paid for, and a failure in between
        rolls the claim back with it.
        """
        result = await self.db.execute(
            update(WorkspaceInvite)
            .where(
                and_(
                    WorkspaceInvite.id == invite_id,
                    WorkspaceInvite.status == InviteStatus.pending,
                )
            )
            .values(status=InviteStatus.accepted)
        )
        await self.db.flush()
        return result.rowcount > 0  # type: ignore[attr-defined, no-any-return]

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
