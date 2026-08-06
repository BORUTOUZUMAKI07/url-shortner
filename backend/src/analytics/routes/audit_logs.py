from typing import List

from fastapi import APIRouter, Depends

from src.analytics.schemas.audit_log import AuditLogResponse
from src.analytics.services.audit_service import AuditService
from src.identity.models.user import User
from src.shared.core.deps import PaginationParams, get_audit_service, get_current_user

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.get("/workspace/{workspace_id}", response_model=List[AuditLogResponse],
    summary="Get audit logs for workspace",
    description="Returns a paginated audit trail of all events in a workspace.")
async def get_workspace_logs(
    workspace_id: int,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    svc: AuditService = Depends(get_audit_service),
):
    return await svc.get_workspace_logs(workspace_id, current_user.id, skip=pagination.skip, limit=pagination.limit)


@router.get("/resource/{resource_type}/{resource_id}", response_model=List[AuditLogResponse],
    summary="Get audit logs for a resource")
async def get_resource_logs(
    resource_type: str,
    resource_id: int,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    svc: AuditService = Depends(get_audit_service),
):
    return await svc.get_resource_logs(resource_type, resource_id, current_user.id, skip=pagination.skip, limit=pagination.limit)


@router.get("/actor/{actor_id}", response_model=List[AuditLogResponse],
    summary="Get audit logs by actor")
async def get_actor_logs(
    actor_id: int,
    pagination: PaginationParams = Depends(),
    current_user: User = Depends(get_current_user),
    svc: AuditService = Depends(get_audit_service),
):
    return await svc.get_actor_logs(actor_id, current_user.id, skip=pagination.skip, limit=pagination.limit)
