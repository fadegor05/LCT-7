"""Каталог типов оборудования с кешированием (APP-scoped cache)."""

import asyncio
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.methodology.models import EquipmentType

# Коды оборудования, которое требует специального подтверждения.
# Зеркалирует meta.class_specificity.specific из ml/configs/rules.json.
SPECIFIC_EQUIPMENT_CODES: frozenset[str] = frozenset(
    {
        "drilling_rig",
        "pile_driver",
        "dwall_rig",
        "paver",
        "grader",
        "concrete_pump",
        "roller",
    }
)


@dataclass(frozen=True)
class EquipmentTypeInfo:
    """Информация о типе оборудования (без Pydantic)."""

    id: uuid.UUID
    code: str
    title: str
    synonyms: tuple[str, ...] | list[str]
    is_coarse: bool = False


class EquipmentCatalog:
    """Кешированный каталог типов оборудования.

    Loads equipment types from the database on first call and caches them.
    Supports lookups by ID and code. Cache can be invalidated.
    """

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]):
        """Инициализировать каталог с sessionmaker."""
        self._sessionmaker = sessionmaker
        self._cache: list[EquipmentTypeInfo] | None = None
        self._lock = asyncio.Lock()

    async def all(self) -> list[EquipmentTypeInfo]:
        """Получить все типы оборудования, отсортированные по коду.

        Результат кешируется при первом вызове.
        """
        async with self._lock:
            if self._cache is None:
                async with self._sessionmaker() as session:
                    stmt = select(EquipmentType).order_by(EquipmentType.code)
                    result = await session.execute(stmt)
                    equipment_types = result.scalars().all()
                    self._cache = [
                        EquipmentTypeInfo(
                            id=eq.id,
                            code=eq.code,
                            title=eq.title,
                            synonyms=tuple(eq.synonyms),
                            is_coarse=eq.is_coarse,
                        )
                        for eq in equipment_types
                    ]
            return self._cache

    async def by_id(self, id: uuid.UUID) -> EquipmentTypeInfo | None:
        """Найти тип оборудования по ID.

        Использует закешированный список.
        """
        items = await self.all()
        for item in items:
            if item.id == id:
                return item
        return None

    async def by_code(self, code: str) -> EquipmentTypeInfo | None:
        """Найти тип оборудования по коду.

        Использует закешированный список.
        """
        items = await self.all()
        for item in items:
            if item.code == code:
                return item
        return None

    def invalidate(self) -> None:
        """Инвалидировать кеш (сбросить закешированные данные)."""
        self._cache = None
