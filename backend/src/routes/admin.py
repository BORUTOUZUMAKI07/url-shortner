from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.deps import PaginationParams, get_current_user
from src.models.url import URL
from src.models.user import User
from src.models.workspace import Workspace

router = APIRouter(prefix="/admin", tags=["Admin"])


async def require_superadmin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superadmin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Superadmin access required")
    return current_user


@router.post("/seed", summary="Make yourself superadmin (only if none exists)")
async def seed_superadmin(current_user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.is_superadmin == True))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Superadmin already exists")
    merged = await db.merge(current_user)
    merged.is_superadmin = True
    await db.commit()
    return {"detail": f"{merged.email} is now superadmin"}


@router.get("/users", summary="List all users")
async def list_users(
    pagination: PaginationParams = Depends(),
    _admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    total = await db.scalar(select(func.count(User.id)))
    result = await db.execute(select(User).offset(pagination.skip).limit(pagination.limit).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return {"total": total, "skip": pagination.skip, "limit": pagination.limit, "users": users}


@router.get("/users/{user_id}", summary="Get user details")
async def get_user(
    user_id: int,
    _admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.patch("/users/{user_id}/toggle-superadmin", summary="Toggle superadmin status")
async def toggle_superadmin(
    user_id: int,
    _admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_superadmin = not user.is_superadmin
    await db.commit()
    return {"detail": f"User {user.email} superadmin={user.is_superadmin}"}


@router.delete("/users/{user_id}", summary="Delete a user and all their data")
async def delete_user(
    user_id: int,
    _admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
    return {"detail": f"User {user.email} deleted"}


@router.get("/workspaces", summary="List all workspaces")
async def list_workspaces(
    pagination: PaginationParams = Depends(),
    _admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    total = await db.scalar(select(func.count(Workspace.id)))
    result = await db.execute(select(Workspace).offset(pagination.skip).limit(pagination.limit).order_by(Workspace.created_at.desc()))
    workspaces = result.scalars().all()
    return {"total": total, "skip": pagination.skip, "limit": pagination.limit, "workspaces": workspaces}


@router.get("/urls", summary="List all URLs across all workspaces")
async def list_all_urls(
    pagination: PaginationParams = Depends(),
    _admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    total = await db.scalar(select(func.count(URL.id)))
    result = await db.execute(select(URL).offset(pagination.skip).limit(pagination.limit).order_by(URL.created_at.desc()))
    urls = result.scalars().all()
    return {"total": total, "skip": pagination.skip, "limit": pagination.limit, "urls": urls}


@router.get("/stats", summary="Platform-wide statistics")
async def platform_stats(
    _admin: User = Depends(require_superadmin),
    db: AsyncSession = Depends(get_db),
):
    total_users = await db.scalar(select(func.count(User.id)))
    total_workspaces = await db.scalar(select(func.count(Workspace.id)))
    total_urls = await db.scalar(select(func.count(URL.id)))
    return {
        "total_users": total_users,
        "total_workspaces": total_workspaces,
        "total_urls": total_urls,
    }
