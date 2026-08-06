import json

from src.analytics.repositories.audit_log_repository import AuditLogRepository
from src.shared.core.audit_context import audit_ctx_var
from src.shared.errors import ForbiddenError, WorkspaceNotFound
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


class AuditService:
    def __init__(self, repo: AuditLogRepository, workspace_repo: WorkspaceRepository):
        self.repo = repo
        self.workspace_repo = workspace_repo

    async def log(
        self,
        actor_id: int | None,
        action: str,
        resource_type: str,
        resource_id: int | None = None,
        before: dict | None = None,
        after: dict | None = None,
        workspace_id: int | None = None,
    ) -> None:
        ctx = audit_ctx_var.get()
        before_json = json.dumps(before) if before else None
        after_json = json.dumps(after) if after else None
        await self.repo.log(
            actor_id=actor_id, action=action, resource_type=resource_type,
            resource_id=resource_id, before_state=before_json,
            after_state=after_json,
            ip_address=ctx.ip_address if ctx else None,
            user_agent=ctx.user_agent if ctx else None,
            workspace_id=workspace_id,
        )

    async def get_workspace_logs(self, workspace_id: int, user_id: int, skip: int = 0, limit: int = 100):
        ws = await self.workspace_repo.verify_access(workspace_id, user_id)
        if not ws:
            raise WorkspaceNotFound()
        return await self.repo.get_workspace_logs(workspace_id, skip=skip, limit=limit)

    async def get_resource_logs(self, resource_type: str, resource_id: int, user_id: int, skip: int = 0, limit: int = 100):
        logs = await self.repo.get_resource_logs(resource_type, resource_id, skip=0, limit=1)
        if logs and logs[0].workspace_id:
            ws = await self.workspace_repo.verify_access(logs[0].workspace_id, user_id)
            if not ws:
                raise WorkspaceNotFound()
        return await self.repo.get_resource_logs(resource_type, resource_id, skip=skip, limit=limit)

    async def get_actor_logs(self, actor_id: int, user_id: int, skip: int = 0, limit: int = 100):
        if actor_id != user_id:
            raise ForbiddenError("You can only view your own audit logs")
        return await self.repo.get_actor_logs(actor_id, skip=skip, limit=limit)
