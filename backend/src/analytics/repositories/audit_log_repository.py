from sqlalchemy import and_, desc, select

from src.analytics.models.audit_log import AuditLog
from src.shared.core.base_repository import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, db):
        super().__init__(AuditLog, db)

    async def log(
        self,
        actor_id: int | None,
        action: str,
        resource_type: str,
        resource_id: int | None = None,
        before_state: str | None = None,
        after_state: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        workspace_id: int | None = None,
    ) -> AuditLog:
        return await self.create(
            actor_id=actor_id, action=action, resource_type=resource_type,
            resource_id=resource_id, before_state=before_state,
            after_state=after_state, ip_address=ip_address,
            user_agent=user_agent, workspace_id=workspace_id,
        )

    async def get_workspace_logs(
        self, workspace_id: int, skip: int = 0, limit: int = 100
    ) -> list[AuditLog]:
        stmt = select(AuditLog).where(AuditLog.workspace_id == workspace_id).order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_resource_logs(
        self, resource_type: str, resource_id: int, skip: int = 0, limit: int = 100
    ) -> list[AuditLog]:
        stmt = select(AuditLog).where(
            and_(AuditLog.resource_type == resource_type, AuditLog.resource_id == resource_id)
        ).order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_actor_logs(
        self, actor_id: int, skip: int = 0, limit: int = 100
    ) -> list[AuditLog]:
        stmt = select(AuditLog).where(AuditLog.actor_id == actor_id).order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
