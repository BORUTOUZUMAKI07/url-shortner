from sqlalchemy import and_, or_, select, update
from sqlalchemy.orm import selectinload

from src.links.models.tag import Tag
from src.links.models.url import URL, URLStatus
from src.shared.core.base_repository import BaseRepository


class URLRepository(BaseRepository[URL]):
    def __init__(self, db):
        super().__init__(URL, db)

    async def get_by_short_code(self, short_code: str) -> URL | None:
        result = await self.db.execute(select(URL).options(selectinload(URL.tags)).where(URL.short_code == short_code))
        return result.scalar_one_or_none()

    async def get_by_custom_alias(self, alias: str) -> URL | None:
        return await self.get_by(custom_alias=alias)

    async def get(self, id: int) -> URL | None:
        result = await self.db.execute(select(URL).options(selectinload(URL.tags)).where(URL.id == id))
        return result.scalar_one_or_none()

    async def alias_exists(self, alias: str) -> bool:
        result = await self.db.execute(
            select(URL).where(or_(URL.custom_alias == alias, URL.short_code == alias))
        )
        return result.scalar_one_or_none() is not None

    async def get_workspace_urls(
        self,
        workspace_id: int | None,
        folder_id: int | None = None,
        tag: str | None = None,
        search: str | None = None,
        status_filter: URLStatus | None = None,
        skip: int = 0,
        limit: int = 100,
        user_id: int | None = None,
    ) -> dict[str, object]:
        query = select(URL).where(URL.status != URLStatus.deleted)
        if workspace_id is not None:
            query = query.where(URL.workspace_id == workspace_id)
        elif user_id is not None:
            from src.workspaces.models.workspace import Workspace
            from src.workspaces.models.workspace_member import WorkspaceMember
            query = query.where(URL.workspace_id.in_(
                select(Workspace.id).where(
                    or_(
                        Workspace.owner_id == user_id,
                        Workspace.id.in_(select(WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user_id))
                    )
                )
            ))
        if folder_id is not None:
            query = query.where(URL.folder_id == folder_id)
        if status_filter:
            query = query.where(URL.status == status_filter)
        if tag:
            query = query.join(URL.tags).where(Tag.name == tag.strip().lower())
        if search:
            term = f"%{search.strip().lower()}%"
            query = query.where(
                or_(
                    URL.original_url.ilike(term),
                    URL.short_code.ilike(term),
                    URL.custom_alias.ilike(term),
                )
            )
        query = query.order_by(URL.created_at.desc())

        # Get total count first
        from sqlalchemy import func
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Then get paginated items
        query = query.options(selectinload(URL.tags)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return {"items": list(result.scalars().all()), "total": total}

    async def soft_delete(self, id: int) -> None:
        await self.db.execute(update(URL).where(URL.id == id).values(status=URLStatus.deleted))
        await self.db.commit()

    async def bulk_update(self, url_ids: list[int], workspace_id: int, **values) -> None:
        await self.db.execute(
            update(URL)
            .where(and_(URL.id.in_(url_ids), URL.workspace_id == workspace_id))
            .values(**values)
        )
        await self.db.commit()

    async def get_short_codes_by_ids(self, url_ids: list[int], workspace_id: int) -> list[tuple[int, str]]:
        result = await self.db.execute(
            select(URL.id, URL.short_code).where(
                and_(URL.id.in_(url_ids), URL.workspace_id == workspace_id)
            )
        )
        return list(result.all())  # type: ignore[arg-type]

    async def get_url_id_by_short_code(self, short_code: str) -> int | None:
        result = await self.db.execute(select(URL.id).where(URL.short_code == short_code))
        return result.scalar_one_or_none()
