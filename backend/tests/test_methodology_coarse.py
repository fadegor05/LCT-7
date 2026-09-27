"""Тесты для функциональности coarse equipment."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.methodology.models import EquipmentType
from app.domains.methodology.seed import EQUIPMENT_SEED


@pytest.fixture
async def coarse_sessionmaker():
    """Sessionmaker для тестов coarse equipment (in-memory SQLite)."""
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
class TestCoarseEquipment:
    """Тесты для coarse equipment."""

    async def test_coarse_equipment_in_seed(self):
        """EQUIPMENT_SEED содержит 5 coarse equipment с правильными кодами."""
        coarse_items = [item for item in EQUIPMENT_SEED if item.get("is_coarse", False)]
        assert len(coarse_items) == 5

        coarse_codes = {item["code"] for item in coarse_items}
        expected_codes = {
            "excavator_unknown",
            "crane_unknown",
            "drilling_unknown",
            "truck_unknown",
            "loader_unknown",
        }
        assert coarse_codes == expected_codes

    async def test_coarse_equipment_has_empty_synonyms(self):
        """Все coarse equipment имеют пустые synonyms."""
        coarse_items = [item for item in EQUIPMENT_SEED if item.get("is_coarse", False)]
        for item in coarse_items:
            assert item.get("synonyms", []) == []

    async def test_coarse_equipment_in_catalog(self, coarse_sessionmaker):
        """Каталог содержит coarse equipment с is_coarse=True."""
        catalog = EquipmentCatalog(coarse_sessionmaker)

        items = await catalog.all()
        coarse_items = [item for item in items if item.is_coarse]
        assert len(coarse_items) == 5

        coarse_codes = {item.code for item in coarse_items}
        expected_codes = {
            "excavator_unknown",
            "crane_unknown",
            "drilling_unknown",
            "truck_unknown",
            "loader_unknown",
        }
        assert coarse_codes == expected_codes

    async def test_regular_equipment_not_coarse(self, coarse_sessionmaker):
        """Обычное оборудование имеет is_coarse=False."""
        catalog = EquipmentCatalog(coarse_sessionmaker)

        excavator_crawler = await catalog.by_code("excavator_crawler")
        assert excavator_crawler is not None
        assert excavator_crawler.is_coarse is False

    async def test_by_code_coarse_equipment(self, coarse_sessionmaker):
        """by_code() возвращает coarse equipment с is_coarse=True."""
        catalog = EquipmentCatalog(coarse_sessionmaker)

        excavator_unknown = await catalog.by_code("excavator_unknown")
        assert excavator_unknown is not None
        assert excavator_unknown.is_coarse is True
        assert excavator_unknown.title == "Экскаватор (тип не определён)"

    async def test_total_equipment_count(self):
        """EQUIPMENT_SEED содержит 25 элементов (20 обычных + 5 coarse)."""
        assert len(EQUIPMENT_SEED) == 25
