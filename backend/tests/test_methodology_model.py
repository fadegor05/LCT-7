"""Модели методологии проверки: оборудование, правила, наборы и требования."""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domains.methodology.models import (
    EquipmentRequirement,
    EquipmentSet,
    EquipmentType,
    MethodologyRule,
    Obligation,
)
from app.domains.methodology.seed import EQUIPMENT_SEED
from app.domains.schedule.models import Schedule, ScheduleStage
from app.domains.site.models import Site
from app.domains.user.models import User


@pytest.mark.asyncio
async def test_equipment_seed_has_25_items() -> None:
    """EQUIPMENT_SEED содержит ровно 25 элементов (20 обычных + 5 coarse)."""
    assert len(EQUIPMENT_SEED) == 25


@pytest.mark.asyncio
async def test_equipment_seed_codes_are_unique() -> None:
    """Все коды в EQUIPMENT_SEED уникальны."""
    codes = [item["code"] for item in EQUIPMENT_SEED]
    assert len(codes) == len(set(codes)) == 25


@pytest.mark.asyncio
async def test_equipment_seed_codes_are_snake_case() -> None:
    """Все коды в EQUIPMENT_SEED в формате snake_case."""
    for item in EQUIPMENT_SEED:
        code = item["code"]
        # snake_case: только буквы, цифры и подчёркивания, начиная с буквы
        assert code.islower(), f"{code} не в нижнем регистре"
        assert code[0].isalpha(), f"{code} не начинается с буквы"
        assert all(c.isalnum() or c == "_" for c in code), f"{code} содержит недопустимые символы"
        assert "__" not in code, f"{code} содержит двойные подчёркивания"


@pytest.mark.asyncio
async def test_equipment_type_table_exists(engine: AsyncEngine) -> None:
    """Таблица equipment_types создана в схеме."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='equipment_types'"
            )
        )
        assert result.scalar() == "equipment_types"


@pytest.mark.asyncio
async def test_methodology_rule_table_exists(engine: AsyncEngine) -> None:
    """Таблица methodology_rules создана в схеме."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='methodology_rules'"
            )
        )
        assert result.scalar() == "methodology_rules"


@pytest.mark.asyncio
async def test_equipment_set_table_exists(engine: AsyncEngine) -> None:
    """Таблица equipment_sets создана в схеме."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='equipment_sets'"
            )
        )
        assert result.scalar() == "equipment_sets"


@pytest.mark.asyncio
async def test_equipment_requirement_table_exists(engine: AsyncEngine) -> None:
    """Таблица equipment_requirements создана в схеме."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='equipment_requirements'"
            )
        )
        assert result.scalar() == "equipment_requirements"


@pytest.mark.asyncio
async def test_obligation_enum_has_three_values() -> None:
    """Enum Obligation содержит normative, logical, auxiliary."""
    assert Obligation.NORMATIVE == "normative"
    assert Obligation.LOGICAL == "logical"
    assert Obligation.AUXILIARY == "auxiliary"


@pytest.mark.asyncio
async def test_equipment_type_persists(engine: AsyncEngine, container) -> None:
    """EquipmentType сохраняется и читается обратно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        eq_type = EquipmentType(
            id=uuid.uuid4(),
            code="excavator_crawler",
            title="Гусеничный экскаватор",
            synonyms=["экскаватор", "excavator"],
        )
        session.add(eq_type)
        await session.commit()

        fetched = await session.get(EquipmentType, eq_type.id)
        assert fetched is not None
        assert fetched.code == "excavator_crawler"
        assert fetched.title == "Гусеничный экскаватор"
        assert fetched.synonyms == ["экскаватор", "excavator"]


@pytest.mark.asyncio
async def test_methodology_rule_with_site_and_stage_persists(
    engine: AsyncEngine, container
) -> None:
    """MethodologyRule с site_id и stage_id сохраняется и читается обратно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Создаём инфраструктуру: пользователь, сайт, график, этап
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Construction Site", owner_id=owner_id)
        session.add(site)

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        stage_id = uuid.uuid4()
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Foundation", position=1)
        session.add(stage)

        # Создаём правило
        rule = MethodologyRule(
            id=uuid.uuid4(),
            site_id=site_id,
            stage_id=stage_id,
            is_verifiable=True,
        )
        session.add(rule)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(MethodologyRule, rule.id)
        assert fetched is not None
        assert fetched.site_id == site_id
        assert fetched.stage_id == stage_id
        assert fetched.is_verifiable is True
        assert fetched.unverifiable_reason is None
        assert fetched.created_at is not None
        assert fetched.updated_at is not None


@pytest.mark.asyncio
async def test_equipment_set_persists(engine: AsyncEngine, container) -> None:
    """EquipmentSet сохраняется и читается обратно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        stage_id = uuid.uuid4()
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Stage", position=1)
        session.add(stage)

        # Правило
        rule_id = uuid.uuid4()
        rule = MethodologyRule(id=rule_id, site_id=site_id, stage_id=stage_id)
        session.add(rule)

        # Набор оборудования
        eq_set = EquipmentSet(id=uuid.uuid4(), rule_id=rule_id, position=1)
        session.add(eq_set)
        await session.commit()

        fetched = await session.get(EquipmentSet, eq_set.id)
        assert fetched is not None
        assert fetched.rule_id == rule_id
        assert fetched.position == 1


@pytest.mark.asyncio
async def test_equipment_requirement_persists(engine: AsyncEngine, container) -> None:
    """EquipmentRequirement сохраняется с обязательными полями."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        stage_id = uuid.uuid4()
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Stage", position=1)
        session.add(stage)

        # Правило и набор
        rule_id = uuid.uuid4()
        rule = MethodologyRule(id=rule_id, site_id=site_id, stage_id=stage_id)
        session.add(rule)

        eq_set_id = uuid.uuid4()
        eq_set = EquipmentSet(id=eq_set_id, rule_id=rule_id, position=1)
        session.add(eq_set)

        # Тип оборудования
        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(id=eq_type_id, code="excavator", title="Экскаватор", synonyms=[])
        session.add(eq_type)

        # Требование
        req = EquipmentRequirement(
            id=uuid.uuid4(),
            set_id=eq_set_id,
            equipment_type_id=eq_type_id,
            min_count=2,
            obligation=Obligation.NORMATIVE.value,
            gesn_code="GESN001",
        )
        session.add(req)
        await session.commit()

        fetched = await session.get(EquipmentRequirement, req.id)
        assert fetched is not None
        assert fetched.set_id == eq_set_id
        assert fetched.equipment_type_id == eq_type_id
        assert fetched.min_count == 2
        assert fetched.obligation == Obligation.NORMATIVE.value


@pytest.mark.asyncio
async def test_rule_unverifiable_without_reason_fails(engine: AsyncEngine, container) -> None:
    """Rule с is_verifiable=False и без reason вызывает IntegrityError при flush."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        stage_id = uuid.uuid4()
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Stage", position=1)
        session.add(stage)

        rule = MethodologyRule(
            id=uuid.uuid4(), site_id=site_id, stage_id=stage_id, is_verifiable=False
        )
        session.add(rule)

        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.asyncio
async def test_requirement_min_count_zero_fails(engine: AsyncEngine, container) -> None:
    """EquipmentRequirement с min_count=0 вызывает IntegrityError."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        stage_id = uuid.uuid4()
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Stage", position=1)
        session.add(stage)

        rule_id = uuid.uuid4()
        rule = MethodologyRule(id=rule_id, site_id=site_id, stage_id=stage_id)
        session.add(rule)

        eq_set_id = uuid.uuid4()
        eq_set = EquipmentSet(id=eq_set_id, rule_id=rule_id, position=1)
        session.add(eq_set)

        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(id=eq_type_id, code="excavator", title="Экскаватор")
        session.add(eq_type)

        req = EquipmentRequirement(
            id=uuid.uuid4(),
            set_id=eq_set_id,
            equipment_type_id=eq_type_id,
            min_count=0,
            obligation=Obligation.NORMATIVE.value,
            gesn_code="GESN001",
        )
        session.add(req)

        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.asyncio
async def test_requirement_without_source_fails(engine: AsyncEngine, container) -> None:
    """EquipmentRequirement без gesn_code и source_note вызывает IntegrityError."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        stage_id = uuid.uuid4()
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Stage", position=1)
        session.add(stage)

        rule_id = uuid.uuid4()
        rule = MethodologyRule(id=rule_id, site_id=site_id, stage_id=stage_id)
        session.add(rule)

        eq_set_id = uuid.uuid4()
        eq_set = EquipmentSet(id=eq_set_id, rule_id=rule_id, position=1)
        session.add(eq_set)

        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(id=eq_type_id, code="excavator", title="Экскаватор")
        session.add(eq_type)

        req = EquipmentRequirement(
            id=uuid.uuid4(),
            set_id=eq_set_id,
            equipment_type_id=eq_type_id,
            min_count=1,
            obligation=Obligation.NORMATIVE.value,
        )
        session.add(req)

        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.asyncio
async def test_rule_unique_site_stage_constraint(engine: AsyncEngine, container) -> None:
    """Два правила для одного site+stage вызывают IntegrityError."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        stage_id = uuid.uuid4()
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Stage", position=1)
        session.add(stage)

        # Первое правило
        rule1 = MethodologyRule(
            id=uuid.uuid4(), site_id=site_id, stage_id=stage_id, is_verifiable=True
        )
        session.add(rule1)
        await session.commit()

        # Второе правило для того же site+stage
        rule2 = MethodologyRule(
            id=uuid.uuid4(), site_id=site_id, stage_id=stage_id, is_verifiable=True
        )
        session.add(rule2)

        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_base_rule_with_stage_key_persists(engine: AsyncEngine, container) -> None:
    """Base rule (site_id=None, stage_key='piles', stage_id=None) сохраняется."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        rule = MethodologyRule(
            id=uuid.uuid4(),
            site_id=None,
            stage_id=None,
            stage_key="piles",
            is_verifiable=True,
        )
        session.add(rule)
        await session.commit()

        fetched = await session.get(MethodologyRule, rule.id)
        assert fetched is not None
        assert fetched.site_id is None
        assert fetched.stage_id is None
        assert fetched.stage_key == "piles"


@pytest.mark.asyncio
async def test_base_rule_without_stage_key_fails(engine: AsyncEngine, container) -> None:
    """Base rule без stage_key вызывает IntegrityError."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        rule = MethodologyRule(id=uuid.uuid4(), site_id=None, stage_id=None, is_verifiable=True)
        session.add(rule)

        with pytest.raises(IntegrityError):
            await session.flush()


@pytest.mark.asyncio
async def test_equipment_set_unique_rule_position_constraint(
    engine: AsyncEngine, container
) -> None:
    """Два набора с одинаковыми rule_id и position вызывают IntegrityError."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        stage_id = uuid.uuid4()
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Stage", position=1)
        session.add(stage)

        # Правило
        rule_id = uuid.uuid4()
        rule = MethodologyRule(id=rule_id, site_id=site_id, stage_id=stage_id)
        session.add(rule)
        await session.flush()

        # Первый набор
        set1 = EquipmentSet(id=uuid.uuid4(), rule_id=rule_id, position=1)
        session.add(set1)
        await session.commit()

        # Второй набор с тем же rule_id и position
        set2 = EquipmentSet(id=uuid.uuid4(), rule_id=rule_id, position=1)
        session.add(set2)

        with pytest.raises(IntegrityError):
            await session.commit()
