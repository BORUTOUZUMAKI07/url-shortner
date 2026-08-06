
from src.links.repositories.folder_repository import FolderRepository
from src.shared.errors import ConflictError, NotFoundError, WorkspaceNotFound
from src.workspaces.repositories.workspace_repository import WorkspaceRepository


class FolderService:
    def __init__(self, repo: FolderRepository, workspace_repo: WorkspaceRepository):
        self.repo = repo
        self.workspace_repo = workspace_repo

    async def _verify_workspace(self, workspace_id: int, user_id: int):
        ws = await self.workspace_repo.verify_access(workspace_id, user_id)
        if not ws:
            raise WorkspaceNotFound()

    async def create(self, name: str, workspace_id: int, user_id: int):
        await self._verify_workspace(workspace_id, user_id)
        if await self.repo.name_exists_in_workspace(name, workspace_id):
            raise ConflictError("Folder name already exists in this workspace.")
        return await self.repo.create(name=name, workspace_id=workspace_id)

    async def list(self, workspace_id: int, user_id: int):
        await self._verify_workspace(workspace_id, user_id)
        return await self.repo.get_workspace_folders(workspace_id)

    async def update(self, id: int, name: str, user_id: int):
        folder = await self.repo.get(id)
        if not folder:
            raise NotFoundError("Folder not found.")
        await self._verify_workspace(folder.workspace_id, user_id)
        if await self.repo.name_exists_in_workspace(name, folder.workspace_id, exclude_id=id):
            raise ConflictError("Another folder with this name already exists.")
        return await self.repo.update(id, name=name)

    async def delete(self, id: int, user_id: int):
        folder = await self.repo.get(id)
        if not folder:
            raise NotFoundError("Folder not found.")
        await self._verify_workspace(folder.workspace_id, user_id)
        await self.repo.delete(id)
