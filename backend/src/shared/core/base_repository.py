from typing import Generic, Optional, TypeVar

from sqlalchemy import delete, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.core.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def create(self, **kwargs) -> ModelType:
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.commit()
        await self.db.refresh(instance)
        return instance

    async def get(self, id: int) -> Optional[ModelType]:
        return await self.db.get(self.model, id)

    async def get_by(self, **filters) -> Optional[ModelType]:
        stmt = select(self.model).filter_by(**filters)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_many(self, skip: int = 0, limit: int = 100, **filters) -> list[ModelType]:
        stmt = select(self.model).filter_by(**filters).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def update(self, id: int, **values) -> Optional[ModelType]:
        stmt = update(self.model).where(self.model.id == id).values(**values)  # type: ignore[attr-defined]
        await self.db.execute(stmt)
        await self.db.commit()
        return await self.get(id)

    async def delete(self, id: int) -> bool:
        stmt = delete(self.model).where(self.model.id == id)  # type: ignore[attr-defined]
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount > 0  # type: ignore[attr-defined, no-any-return]

    async def count(self, **filters) -> int:
        stmt = select(func.count()).select_from(self.model).filter_by(**filters)
        result = await self.db.execute(stmt)
        return result.scalar_one()  # type: ignore[no-any-return]

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        stmt = select(self.model).order_by(desc("created_at")).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()

    async def flush(self) -> None:
        await self.db.flush()
