"""Базовый репозиторий с типовыми запросами (аналог core/BaseRepository.kt).

Доменные репозитории наследуются от него и добавляют только специфичные для
своей модели запросы. Session по-прежнему приходит через DI (Scope.REQUEST);
commit — ответственность сервиса, репозиторий только стейджит изменения.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base


class BaseRepository[ModelT: Base]:
    """CRUD по одной модели. Наследники задают `model` и дописывают свои методы.

    Пример:
        class UserRepository(BaseRepository[User]):
            model = User
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> Sequence[ModelT]:
        result = await self._session.execute(select(self.model))
        return result.scalars().all()

    async def get(self, id: Any) -> ModelT | None:
        return await self._session.get(self.model, id)

    async def get_by(self, **filters: Any) -> ModelT | None:
        result = await self._session.execute(select(self.model).filter_by(**filters))
        return result.scalar_one_or_none()

    async def list_by(self, **filters: Any) -> Sequence[ModelT]:
        result = await self._session.execute(select(self.model).filter_by(**filters))
        return result.scalars().all()

    async def add(self, entity: ModelT) -> ModelT:
        self._session.add(entity)
        await self._session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        await self._session.delete(entity)
        await self._session.flush()

    async def delete_by(self, **filters: Any) -> None:
        await self._session.execute(delete(self.model).filter_by(**filters))
        await self._session.flush()
