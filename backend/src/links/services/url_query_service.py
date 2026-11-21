"""
URLQueryService — Single Responsibility: read/list URLs.
"""

from typing import Optional

from src.links.models.url import URL, URLStatus
from src.shared.core.interfaces import (
    IURLRepository,
    IWorkspaceRepository,
)
from src.shared.errors import URLNotFound


class URLQueryService:
    """Read and list short URLs. Single responsibility: queries only."""

    def __init__(
        self,
        url_repo: IURLRepository,
        workspace_repo: IWorkspaceRepository,
    ):
        self.url_repo = url_repo
        self.workspace_repo = workspace_repo

    async def _verify_workspace_access(self, workspace_id: int, user_id: int):
        ws = await self.workspace_repo.verify_access(workspace_id, user_id)
        if not ws:
            raise URLNotFound()

    async def list(
        self,
        workspace_id: Optional[int],
        user_id: int,
        **filters,
    ) -> dict[str, object]:
        if workspace_id is not None:
            await self._verify_workspace_access(workspace_id, user_id)
        return await self.url_repo.get_workspace_urls(
            workspace_id, user_id=user_id, **filters
        )

    async def get(self, id: int, user_id: int) -> URL:
        url = await self.url_repo.get(id)
        if not url or url.status == URLStatus.deleted:
            raise URLNotFound()
        await self._verify_workspace_access(url.workspace_id, user_id)
        return url
