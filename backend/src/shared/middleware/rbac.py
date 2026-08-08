from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware

from src.links.models.folder import Folder
from src.links.models.tag import Tag
from src.links.models.url import URL
from src.shared.core import database
from src.shared.core.security import decode_token
from src.workspaces.models.workspace_member import MemberRole
from src.workspaces.repositories.workspace_repository import WorkspaceRepository

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class RBACMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in WRITE_METHODS or not request.url.path.startswith("/api/v1/"):
            return await call_next(request)
        if request.url.path.startswith("/api/v1/admin/"):
            return await call_next(request)

        user_id = self._resolve_user_id(request)
        if user_id is None:
            return await call_next(request)

        workspace_id = await self._resolve_workspace_id(request)
        if workspace_id is None:
            return await call_next(request)

        await require_role(workspace_id, user_id, MemberRole.editor)
        return await call_next(request)

    @staticmethod
    def _resolve_user_id(request: Request) -> int | None:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None
        token = auth_header[7:]
        if token.startswith("lf_"):
            return None
        try:
            payload = decode_token(token)
        except Exception:
            return None
        sub = payload.get("sub")
        if not sub or payload.get("type") != "access":
            return None
        try:
            return int(sub)
        except (TypeError, ValueError):
            return None

    async def _resolve_workspace_id(self, request: Request) -> int | None:
        path = request.url.path.rstrip("/")
        parts = path.split("/")

        if "workspaces" in parts:
            idx = parts.index("workspaces")
            if idx + 1 < len(parts):
                try:
                    return int(parts[idx + 1])
                except ValueError:
                    pass

        if "/urls/bulk" in path:
            wid = request.query_params.get("workspace_id")
            if wid and wid.isdigit():
                return int(wid)

        if "webhooks" in parts:
            for i, part in enumerate(parts):
                if part == "workspace" and i + 1 < len(parts):
                    try:
                        return int(parts[i + 1])
                    except ValueError:
                        continue

        async with database.AsyncSessionLocal() as db:
            if "urls" in parts:
                idx = parts.index("urls")
                if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                    url = await db.get(URL, int(parts[idx + 1]))
                    return url.workspace_id if url else None
            if "folders" in parts:
                idx = parts.index("folders")
                if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                    folder = await db.get(Folder, int(parts[idx + 1]))
                    return folder.workspace_id if folder else None
            if "tags" in parts:
                idx = parts.index("tags")
                if idx + 1 < len(parts) and parts[idx + 1].isdigit():
                    tag = await db.get(Tag, int(parts[idx + 1]))
                    return tag.workspace_id if tag else None
        return None


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
