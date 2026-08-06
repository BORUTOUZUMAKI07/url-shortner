from sqlalchemy import and_, select

from src.links.models.folder import Folder
from src.shared.core.base_repository import BaseRepository


class FolderRepository(BaseRepository[Folder]):
    def __init__(self, db):
        super().__init__(Folder, db)

    async def get_workspace_folders(self, workspace_id: int) -> list[Folder]:
        return await self.get_many(workspace_id=workspace_id)

    async def name_exists_in_workspace(self, name: str, workspace_id: int, exclude_id: int | None = None) -> bool:
        query = select(Folder).where(
            and_(Folder.name == name, Folder.workspace_id == workspace_id)
        )
        if exclude_id is not None:
            query = query.where(Folder.id != exclude_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None

    async def folder_belongs_to_workspace(self, folder_id: int, workspace_id: int) -> bool:
        result = await self.db.execute(
            select(Folder).where(and_(Folder.id == folder_id, Folder.workspace_id == workspace_id))
        )
        return result.scalar_one_or_none() is not None
