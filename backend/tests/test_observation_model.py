"""Модели наблюдений: таблицы observations, observed_equipment."""

import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domains.methodology.models import EquipmentType
from app.domains.observation.models import Observation, ObservedEquipment
from app.domains.site.models import Site
from app.domains.user.models import User


@pytest.mark.asyncio
async def test_observation_table_exists(engine: AsyncEngine) -> None:
    """Таблица observations создана в схеме."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='observations'")
        )
        assert result.scalar() == "observations"


@pytest.mark.asyncio
async def test_observed_equipment_table_exists(engine: AsyncEngine) -> None:
    """Таблица observed_equipment создана в схеме."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='observed_equipment'")
        )
        assert result.scalar() == "observed_equipment"


@pytest.mark.asyncio
async def test_observation_columns(engine: AsyncEngine) -> None:
    """Колонки таблицы observations соответствуют модели."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA table_info(observations)"))
        columns = {row[1] for row in result.all()}
        assert columns == {
            "id",
            "site_id",
            "observed_on",
            "photo_count",
            "observability",
            "observability_notes",
            "recomputed_at",
        }


@pytest.mark.asyncio
async def test_observed_equipment_columns(engine: AsyncEngine) -> None:
    """Колонки таблицы observed_equipment соответствуют модели."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA table_info(observed_equipment)"))
        columns = {row[1] for row in result.all()}
        assert columns == {
            "id",
            "observation_id",
            "equipment_type_id",
            "count_min",
            "activity",
            "confidence",
        }


@pytest.mark.asyncio
async def test_observation_persists_with_site(engine: AsyncEngine, container) -> None:
    """Observation сохраняется с site_id и observed_on, читается обратно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Создаём пользователя и сайт
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Construction Site", owner_id=owner_id)
        session.add(site)

        # Создаём наблюдение
        obs_id = uuid.uuid4()
        observation = Observation(
            id=obs_id,
            site_id=site_id,
            observed_on=date(2026, 9, 24),
            photo_count=5,
            observability="high",
            observability_notes=None,
        )
        session.add(observation)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(Observation, obs_id)
        assert fetched is not None
        assert fetched.id == obs_id
        assert fetched.site_id == site_id
        assert fetched.observed_on == date(2026, 9, 24)
        assert fetched.photo_count == 5
        assert fetched.observability == "high"
        assert fetched.observability_notes is None
        assert fetched.recomputed_at is not None


@pytest.mark.asyncio
async def test_unique_constraint_site_id_observed_on(container) -> None:
    """UNIQUE(site_id, observed_on) на observations.

    Попытка вставить два наблюдения с одним site_id и observed_on вызывает IntegrityError.
    """
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)
        await session.commit()

        # Первое наблюдение
        obs1 = Observation(
            id=uuid.uuid4(),
            site_id=site_id,
            observed_on=date(2026, 9, 24),
            photo_count=5,
            observability="high",
        )
        session.add(obs1)
        await session.commit()

        # Второе наблюдение с тем же site_id и observed_on
        obs2 = Observation(
            id=uuid.uuid4(),
            site_id=site_id,
            observed_on=date(2026, 9, 24),
            photo_count=3,
            observability="medium",
        )
        session.add(obs2)

        # Должно вызвать IntegrityError
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_observed_equipment_persists(container) -> None:
    """ObservedEquipment сохраняется и читается обратно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        obs_id = uuid.uuid4()
        observation = Observation(
            id=obs_id,
            site_id=site_id,
            observed_on=date(2026, 9, 24),
            photo_count=5,
            observability="high",
        )
        session.add(observation)

        # Тип оборудования
        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(
            id=eq_type_id, code="excavator_crawler", title="Гусеничный экскаватор"
        )
        session.add(eq_type)

        # ObservedEquipment
        eq_id = uuid.uuid4()
        equipment = ObservedEquipment(
            id=eq_id,
            observation_id=obs_id,
            equipment_type_id=eq_type_id,
            count_min=2,
            activity="works",
            confidence="high",
        )
        session.add(equipment)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(ObservedEquipment, eq_id)
        assert fetched is not None
        assert fetched.id == eq_id
        assert fetched.observation_id == obs_id
        assert fetched.equipment_type_id == eq_type_id
        assert fetched.count_min == 2
        assert fetched.activity == "works"
        assert fetched.confidence == "high"


@pytest.mark.asyncio
async def test_unique_constraint_observation_id_equipment_type_id(container) -> None:
    """UNIQUE(observation_id, equipment_type_id) на observed_equipment.

    Попытка вставить два оборудования с одним observation_id и equipment_type_id
    вызывает IntegrityError.
    """
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        obs_id = uuid.uuid4()
        observation = Observation(
            id=obs_id,
            site_id=site_id,
            observed_on=date(2026, 9, 24),
            photo_count=5,
            observability="high",
        )
        session.add(observation)

        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(
            id=eq_type_id, code="excavator_crawler", title="Гусеничный экскаватор"
        )
        session.add(eq_type)
        await session.commit()

        # Первое оборудование
        eq1 = ObservedEquipment(
            id=uuid.uuid4(),
            observation_id=obs_id,
            equipment_type_id=eq_type_id,
            count_min=2,
            activity="works",
            confidence="high",
        )
        session.add(eq1)
        await session.commit()

        # Второе оборудование с тем же observation_id и equipment_type_id
        eq2 = ObservedEquipment(
            id=uuid.uuid4(),
            observation_id=obs_id,
            equipment_type_id=eq_type_id,
            count_min=3,
            activity="idle",
            confidence="medium",
        )
        session.add(eq2)

        # Должно вызвать IntegrityError
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_check_constraint_count_min_gte_1(container) -> None:
    """CheckConstraint("count_min >= 1") на observed_equipment.

    Попытка вставить count_min < 1 вызывает IntegrityError.
    """
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        obs_id = uuid.uuid4()
        observation = Observation(
            id=obs_id,
            site_id=site_id,
            observed_on=date(2026, 9, 24),
            photo_count=5,
            observability="high",
        )
        session.add(observation)

        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(
            id=eq_type_id, code="excavator_crawler", title="Гусеничный экскаватор"
        )
        session.add(eq_type)
        await session.commit()

        # Попытка создать оборудование с count_min = 0
        equipment = ObservedEquipment(
            id=uuid.uuid4(),
            observation_id=obs_id,
            equipment_type_id=eq_type_id,
            count_min=0,
            activity="works",
            confidence="high",
        )
        session.add(equipment)

        # Должно вызвать IntegrityError
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_observation_fk_site_cascade_delete() -> None:
    """FK observations.site_id -> sites.id имеет ondelete=CASCADE."""
    table = Observation.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "site_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"


@pytest.mark.asyncio
async def test_observed_equipment_fk_observation_cascade_delete() -> None:
    """FK observed_equipment.observation_id -> observations.id имеет ondelete=CASCADE."""
    table = ObservedEquipment.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "observation_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"


@pytest.mark.asyncio
async def test_observed_equipment_fk_equipment_type_no_cascade() -> None:
    """FK observed_equipment.equipment_type_id -> equipment_types.id НЕ имеет CASCADE."""
    table = ObservedEquipment.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "equipment_type_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    # Проверяем, что нет CASCADE
    assert fk_constraints[0].ondelete is None or fk_constraints[0].ondelete == "RESTRICT"
