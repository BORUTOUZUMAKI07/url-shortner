from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.core import database
from src.workspaces.models.workspace_member import MemberRole
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


async def require_role(workspace_id: int, user_id: int, min_role: MemberRole, db: AsyncSession | None = None) -> bool:
    if db is not None:
        allowed = await WorkspaceRepository(db).verify_role(workspace_id, user_id, min_role)
    else:
        async with database.AsyncSessionLocal() as session:
            allowed = await WorkspaceRepository(session).verify_role(workspace_id, user_id, min_role)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires {min_role.value} role or higher.",
        )
    return True
