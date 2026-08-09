from fastapi import APIRouter, Depends, HTTPException, status

from src.admin.services.admin_service import AdminService
from src.identity.models.user import User
from src.shared.core.deps import PaginationParams, get_admin_service, get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])


async def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return current_user


@router.post("/seed", summary="Make yourself superadmin (only if none exists)")
async def seed_superadmin(
    current_user: User = Depends(get_current_user),
    service: AdminService = Depends(get_admin_service),
):
    email = await service.seed_superadmin(current_user)
    return {"detail": f"{email} is now superadmin"}


@router.get("/users", summary="List all users")
async def list_users(
    pagination: PaginationParams = Depends(),
    _admin: User = Depends(require_superadmin),
    service: AdminService = Depends(get_admin_service),
):
    total, users = await service.list_users(pagination.skip, pagination.limit)
    return {"total": total, "skip": pagination.skip, "limit": pagination.limit, "users": users}


@router.get("/users/{user_id}", summary="Get user details")
async def get_user(
    user_id: int,
    _admin: User = Depends(require_superadmin),
    service: AdminService = Depends(get_admin_service),
):
    return await service.get_user(user_id)


@router.patch("/users/{user_id}/toggle-superadmin", summary="Toggle superadmin status")
async def toggle_superadmin(
    user_id: int,
    _admin: User = Depends(require_superadmin),
    service: AdminService = Depends(get_admin_service),
):
    user = await service.toggle_superadmin(user_id)
    return {"detail": f"User {user.email} superadmin={user.is_superadmin}"}


@router.delete("/users/{user_id}", summary="Delete a user and all their data")
async def delete_user(
    user_id: int,
    _admin: User = Depends(require_superadmin),
    service: AdminService = Depends(get_admin_service),
):
    email = await service.delete_user(user_id)
    return {"detail": f"User {email} deleted"}


@router.get("/workspaces", summary="List all workspaces")
async def list_workspaces(
    pagination: PaginationParams = Depends(),
    _admin: User = Depends(require_superadmin),
    service: AdminService = Depends(get_admin_service),
):
    total, workspaces = await service.list_workspaces(pagination.skip, pagination.limit)
    return {"total": total, "skip": pagination.skip, "limit": pagination.limit, "workspaces": workspaces}


@router.get("/urls", summary="List all URLs across all workspaces")
async def list_all_urls(
    pagination: PaginationParams = Depends(),
    _admin: User = Depends(require_superadmin),
    service: AdminService = Depends(get_admin_service),
):
    total, urls = await service.list_all_urls(pagination.skip, pagination.limit)
    return {"total": total, "skip": pagination.skip, "limit": pagination.limit, "urls": urls}


@router.get("/stats", summary="Platform-wide statistics")
async def platform_stats(
    _admin: User = Depends(require_superadmin),
    service: AdminService = Depends(get_admin_service),
):
    return await service.platform_stats()
