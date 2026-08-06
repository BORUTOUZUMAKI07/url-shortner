from sqlalchemy import and_, select

from src.links.models.tag import Tag
from src.shared.core.base_repository import BaseRepository


class TagRepository(BaseRepository[Tag]):
    def __init__(self, db):
        super().__init__(Tag, db)

    async def get_workspace_tags(self, workspace_id: int) -> list[Tag]:
        return await self.get_many(workspace_id=workspace_id)

    async def get_or_create(self, name: str, workspace_id: int) -> Tag:
        clean_name = name.strip().lower()
        result = await self.db.execute(
            select(Tag).where(
                and_(Tag.name == clean_name, Tag.workspace_id == workspace_id)
            )
        )
        tag = result.scalar_one_or_none()
        if not tag:
            tag = Tag(name=clean_name, workspace_id=workspace_id)
            self.db.add(tag)
        return tag

    async def name_exists_in_workspace(self, name: str, workspace_id: int) -> bool:
        clean_name = name.strip().lower()
        result = await self.db.execute(
            select(Tag).where(
                and_(Tag.name == clean_name, Tag.workspace_id == workspace_id)
            )
        )
        return result.scalar_one_or_none() is not None
