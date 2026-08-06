
from src.links.repositories.tag_repository import TagRepository
from src.shared.errors import ConflictError, NotFoundError, WorkspaceNotFound
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


class TagService:
    def __init__(self, repo: TagRepository, workspace_repo: WorkspaceRepository):
        self.repo = repo
        self.workspace_repo = workspace_repo

    async def _verify_workspace(self, workspace_id: int, user_id: int):
        ws = await self.workspace_repo.verify_access(workspace_id, user_id)
        if not ws:
            raise WorkspaceNotFound()

    async def create(self, name: str, workspace_id: int, user_id: int):
        await self._verify_workspace(workspace_id, user_id)
        if await self.repo.name_exists_in_workspace(name, workspace_id):
            raise ConflictError("Tag already exists in this workspace.")
        return await self.repo.create(name=name.strip().lower(), workspace_id=workspace_id)

    async def list(self, workspace_id: int, user_id: int):
        await self._verify_workspace(workspace_id, user_id)
        return await self.repo.get_workspace_tags(workspace_id)

    async def delete(self, id: int, user_id: int):
        tag = await self.repo.get(id)
        if not tag:
            raise NotFoundError("Tag not found.")
        await self._verify_workspace(tag.workspace_id, user_id)
        await self.repo.delete(id)
