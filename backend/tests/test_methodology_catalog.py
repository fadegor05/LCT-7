"""Тесты для catalog.py: EquipmentCatalog с кешированием."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.domains.methodology.catalog import EquipmentCatalog, EquipmentTypeInfo
from app.domains.methodology.models import EquipmentType
from app.domains.methodology.seed import EQUIPMENT_SEED


@pytest.fixture
async def catalog_sessionmaker():
    """Sessionmaker для EquipmentCatalog тестов (in-memory SQLite)."""
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    maker = async_sessionmaker(engine, expire_on_commit=False)

    # Вставляем EQUIPMENT_SEED в БД
    async with maker() as session:
        for seed_item in EQUIPMENT_SEED:
            eq_type = EquipmentType(
                id=uuid.uuid4(),
                code=seed_item["code"],
                title=seed_item["title"],
                synonyms=seed_item.get("synonyms", []),
                is_coarse=seed_item.get("is_coarse", False),
            )
            session.add(eq_type)
        await session.commit()

    yield maker
    await engine.dispose()


@pytest.mark.asyncio
class TestEquipmentCatalog:
    """Тесты для EquipmentCatalog."""

    async def test_all_returns_25_items_sorted_by_code(self, catalog_sessionmaker):
        """all() возвращает 25 элементов (20 обычных + 5 coarse), отсортированных по коду."""
        catalog = EquipmentCatalog(catalog_sessionmaker)

        items = await catalog.all()
        assert len(items) == 25
        assert all(isinstance(item, EquipmentTypeInfo) for item in items)

        # Проверяем сортировку по коду
        codes = [item.code for item in items]
        assert codes == sorted(codes)

    async def test_all_caches_result(self, catalog_sessionmaker):
        """all() кеширует результат — второй вызов не идёт в БД."""
        catalog = EquipmentCatalog(catalog_sessionmaker)

        first_call = await catalog.all()
        assert len(first_call) == 25

        # Добавляем новый элемент в БД напрямую
        async with catalog_sessionmaker() as session:
            new_eq_type = EquipmentType(
                id=uuid.uuid4(),
                code="new_equipment",
                title="New Equipment",
                synonyms=[],
            )
            session.add(new_eq_type)
            await session.commit()

        # Второй вызов all() возвращает закешированный результат (25 элементов)
        second_call = await catalog.all()
        assert len(second_call) == 25

    async def test_all_after_invalidate_reloads(self, catalog_sessionmaker):
        """После invalidate() вызов all() перезагружает данные из БД."""
        catalog = EquipmentCatalog(catalog_sessionmaker)

        first_call = await catalog.all()
        assert len(first_call) == 25

        # Добавляем новый элемент в БД
        async with catalog_sessionmaker() as session:
            new_eq_type = EquipmentType(
                id=uuid.uuid4(),
                code="new_equipment",
                title="New Equipment",
                synonyms=[],
            )
            session.add(new_eq_type)
            await session.commit()

        # Инвалидируем кеш
        catalog.invalidate()

        # Теперь all() загружает свежие данные (26 элементов)
        second_call = await catalog.all()
        assert len(second_call) == 26

    async def test_by_id_returns_equipment(self, catalog_sessionmaker):
        """by_id(id) возвращает EquipmentTypeRead или None."""
        catalog = EquipmentCatalog(catalog_sessionmaker)

        # Получаем первый элемент из БД
        async with catalog_sessionmaker() as session:
            stmt = __import__("sqlalchemy", fromlist=["select"]).select(EquipmentType).limit(1)
            first_eq = (await session.execute(stmt)).scalar_one()
            eq_id = first_eq.id
            eq_code = first_eq.code

        # Находим по ID через каталог
        found = await catalog.by_id(eq_id)
        assert found is not None
        assert found.id == eq_id
        assert found.code == eq_code

    async def test_by_id_unknown_returns_none(self, catalog_sessionmaker):
        """by_id(unknown_id) возвращает None."""
        catalog = EquipmentCatalog(catalog_sessionmaker)

        unknown_id = uuid.uuid4()
        found = await catalog.by_id(unknown_id)
        assert found is None

    async def test_by_code_returns_equipment(self, catalog_sessionmaker):
        """by_code(code) возвращает EquipmentTypeRead или None."""
        catalog = EquipmentCatalog(catalog_sessionmaker)

        found = await catalog.by_code("excavator_crawler")
        assert found is not None
        assert found.code == "excavator_crawler"
        assert found.title == "Гусеничный экскаватор"

    async def test_by_code_unknown_returns_none(self, catalog_sessionmaker):
        """by_code(unknown_code) возвращает None."""
        catalog = EquipmentCatalog(catalog_sessionmaker)

        found = await catalog.by_code("nonexistent_code")
        assert found is None

    async def test_by_id_and_by_code_use_cache(self, catalog_sessionmaker):
        """by_id() и by_code() используют кеш из all()."""
        catalog = EquipmentCatalog(catalog_sessionmaker)

        # Загружаем кеш
        await catalog.all()

        # Добавляем новый элемент в БД
        async with catalog_sessionmaker() as session:
            new_eq_type = EquipmentType(
                id=uuid.uuid4(),
                code="new_equipment",
                title="New Equipment",
                synonyms=[],
            )
            session.add(new_eq_type)
            await session.commit()

        # by_code() возвращает None для нового кода (кеш не обновлён)
        found = await catalog.by_code("new_equipment")
        assert found is None
