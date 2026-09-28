from src.links.models.url import URLStatus
from src.links.repositories.favorite_repository import FavoriteRepository
from src.links.repositories.url_repository import URLRepository
from src.shared.errors import ConflictError, NotFoundError, URLNotFound
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


class FavoriteService:
    def __init__(
        self,
        repo: FavoriteRepository,
        url_repo: URLRepository,
        workspace_repo: WorkspaceRepository,
    ):
        self.repo = repo
        self.url_repo = url_repo
        self.workspace_repo = workspace_repo

    async def add(self, url_id: int, user_id: int):
        url = await self.url_repo.get(url_id)
        # Report "not found" rather than "forbidden" so this cannot be used to
        # probe which URL ids exist platform-wide.
        if not url or url.status == URLStatus.deleted:
            raise URLNotFound()
        # Without this, any authenticated user could favourite (and thereby
        # confirm the existence of) a URL in a workspace they do not belong to
        # by passing an arbitrary url_id. `verify_access` RETURNS the workspace
        # or None - it does not raise - so the result has to be checked here.
        if url.workspace_id is not None:
            accessible = await self.workspace_repo.verify_access(url.workspace_id, user_id)
            if not accessible:
                raise URLNotFound()
        if await self.repo.is_favorited(user_id, url_id):
            raise ConflictError("URL already favorited.")
        return await self.repo.create(user_id=user_id, url_id=url_id)

    async def remove(self, url_id: int, user_id: int):
        removed = await self.repo.remove(user_id, url_id)
        if not removed:
            raise NotFoundError("Favorite not found.")

    async def list(self, user_id: int, skip: int = 0, limit: int = 100):
        return await self.repo.get_user_favorites(user_id, skip=skip, limit=limit)

    async def check(self, url_id: int, user_id: int) -> bool:
        return await self.repo.is_favorited(user_id, url_id)
