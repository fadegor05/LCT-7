"""Модели assessment: таблицы stage_statuses, deviations, deviation_evidence, status_basis."""

import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domains.assessment.models import Deviation, DeviationEvidence, StageStatus, StatusBasis
from app.domains.methodology.models import EquipmentType
from app.domains.observation.models import Observation
from app.domains.photo.models import Detection, Photo
from app.domains.schedule.models import Schedule, ScheduleStage
from app.domains.site.models import Site
from app.domains.user.models import User


@pytest.mark.asyncio
async def test_stage_status_table_exists(engine: AsyncEngine) -> None:
    """Таблица stage_statuses создана в схеме."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='stage_statuses'")
        )
        assert result.scalar() == "stage_statuses"


@pytest.mark.asyncio
async def test_deviations_table_exists(engine: AsyncEngine) -> None:
    """Таблица deviations создана в схеме."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='deviations'")
        )
        assert result.scalar() == "deviations"


@pytest.mark.asyncio
async def test_deviation_evidence_table_exists(engine: AsyncEngine) -> None:
    """Таблица deviation_evidence создана в схеме."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='deviation_evidence'")
        )
        assert result.scalar() == "deviation_evidence"


@pytest.mark.asyncio
async def test_status_basis_table_exists(engine: AsyncEngine) -> None:
    """Таблица status_basis создана в схеме."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='status_basis'")
        )
        assert result.scalar() == "status_basis"


@pytest.mark.asyncio
async def test_stage_status_persists(container) -> None:
    """StageStatus сохраняется с stage_id, status, confidence и читается обратно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
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
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Excavation", position=1)
        session.add(stage)

        # StageStatus
        status_id = uuid.uuid4()
        status = StageStatus(
            id=status_id,
            stage_id=stage_id,
            status="on_track",
            delay_days=None,
            confidence="high",
            confidence_reason="Based on 3 observations",
        )
        session.add(status)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(StageStatus, status_id)
        assert fetched is not None
        assert fetched.id == status_id
        assert fetched.stage_id == stage_id
        assert fetched.status == "on_track"
        assert fetched.delay_days is None
        assert fetched.confidence == "high"
        assert fetched.confidence_reason == "Based on 3 observations"
        assert fetched.computed_at is not None


@pytest.mark.asyncio
async def test_unique_constraint_stage_id(container) -> None:
    """UNIQUE(stage_id) на stage_statuses.

    Попытка вставить два статуса с одним stage_id вызывает IntegrityError.
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

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        stage_id = uuid.uuid4()
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Excavation", position=1)
        session.add(stage)
        await session.commit()

        # Первый статус
        status1 = StageStatus(
            id=uuid.uuid4(),
            stage_id=stage_id,
            status="on_track",
            confidence="high",
        )
        session.add(status1)
        await session.commit()

        # Второй статус с тем же stage_id
        status2 = StageStatus(
            id=uuid.uuid4(),
            stage_id=stage_id,
            status="behind",
            confidence="medium",
        )
        session.add(status2)

        # Должно вызвать IntegrityError
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_deviation_persists_with_site(container) -> None:
    """Deviation сохраняется с site_id, stage_id (опционально), type и читается обратно."""
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
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Excavation", position=1)
        session.add(stage)

        # Deviation
        dev_id = uuid.uuid4()
        deviation = Deviation(
            id=dev_id,
            site_id=site_id,
            stage_id=stage_id,
            type="missing_equipment",
            is_hypothesis=False,
            severity="critical",
            confidence="high",
            period_start=date(2026, 9, 20),
            period_end=date(2026, 9, 24),
            expected="2 excavators",
            observed="1 excavator",
            limits_text="GESN requires 2 excavators",
        )
        session.add(deviation)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(Deviation, dev_id)
        assert fetched is not None
        assert fetched.id == dev_id
        assert fetched.site_id == site_id
        assert fetched.stage_id == stage_id
        assert fetched.type == "missing_equipment"
        assert fetched.is_hypothesis is False
        assert fetched.severity == "critical"
        assert fetched.confidence == "high"
        assert fetched.period_start == date(2026, 9, 20)
        assert fetched.period_end == date(2026, 9, 24)
        assert fetched.expected == "2 excavators"
        assert fetched.observed == "1 excavator"
        assert fetched.limits_text == "GESN requires 2 excavators"
        assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_deviation_site_wide_stage_id_none(container) -> None:
    """Deviation с stage_id=None (site-wide) создаётся успешно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        # Deviation без stage_id (site-wide)
        dev_id = uuid.uuid4()
        deviation = Deviation(
            id=dev_id,
            site_id=site_id,
            stage_id=None,  # site-wide deviation (e.g., stale_data)
            type="stale_data",
            is_hypothesis=True,
            severity="attention",
            confidence="medium",
            period_start=date(2026, 9, 20),
            period_end=date(2026, 9, 24),
            expected="Fresh observations",
            observed="No recent photos",
            limits_text="Data older than 7 days",
        )
        session.add(deviation)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(Deviation, dev_id)
        assert fetched is not None
        assert fetched.stage_id is None
        assert fetched.type == "stale_data"


@pytest.mark.asyncio
async def test_deviation_evidence_persists(container) -> None:
    """DeviationEvidence сохраняется и читается обратно."""
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
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Excavation", position=1)
        session.add(stage)

        # Deviation
        dev_id = uuid.uuid4()
        deviation = Deviation(
            id=dev_id,
            site_id=site_id,
            stage_id=stage_id,
            type="missing_equipment",
            is_hypothesis=False,
            severity="critical",
            confidence="high",
            period_start=date(2026, 9, 20),
            period_end=date(2026, 9, 24),
            expected="2 excavators",
            observed="1 excavator",
            limits_text="GESN requires 2 excavators",
        )
        session.add(deviation)

        # Photo
        photo_id = uuid.uuid4()
        photo = Photo(
            id=photo_id,
            site_id=site_id,
            storage_key="photos/site1/photo1.jpg",
            original_name="photo1.jpg",
            width=1920,
            height=1080,
            captured_on=date(2026, 9, 24),
            date_source="metadata",
        )
        session.add(photo)

        # Equipment type (for detection)
        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(
            id=eq_type_id, code="excavator_crawler", title="Гусеничный экскаватор"
        )
        session.add(eq_type)

        # Detection
        detection_id = uuid.uuid4()
        detection = Detection(
            id=detection_id,
            photo_id=photo_id,
            equipment_type_id=eq_type_id,
            bbox=[0.1, 0.2, 0.5, 0.6],
            score=0.95,
            model_version="v1.0",
        )
        session.add(detection)
        await session.commit()

        # DeviationEvidence
        evidence_id = uuid.uuid4()
        evidence = DeviationEvidence(
            id=evidence_id,
            deviation_id=dev_id,
            photo_id=photo_id,
            detection_id=detection_id,
        )
        session.add(evidence)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(DeviationEvidence, evidence_id)
        assert fetched is not None
        assert fetched.id == evidence_id
        assert fetched.deviation_id == dev_id
        assert fetched.photo_id == photo_id
        assert fetched.detection_id == detection_id


@pytest.mark.asyncio
async def test_unique_constraint_deviation_evidence(container) -> None:
    """UNIQUE(deviation_id, photo_id, detection_id) на deviation_evidence.

    Попытка вставить две записи с одинаковыми значениями вызывает IntegrityError.
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

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        stage_id = uuid.uuid4()
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Excavation", position=1)
        session.add(stage)

        # Deviation
        dev_id = uuid.uuid4()
        deviation = Deviation(
            id=dev_id,
            site_id=site_id,
            stage_id=stage_id,
            type="missing_equipment",
            is_hypothesis=False,
            severity="critical",
            confidence="high",
            period_start=date(2026, 9, 20),
            period_end=date(2026, 9, 24),
            expected="2 excavators",
            observed="1 excavator",
            limits_text="GESN requires 2 excavators",
        )
        session.add(deviation)

        # Photo
        photo_id = uuid.uuid4()
        photo = Photo(
            id=photo_id,
            site_id=site_id,
            storage_key="photos/site1/photo1.jpg",
            original_name="photo1.jpg",
            width=1920,
            height=1080,
            captured_on=date(2026, 9, 24),
        )
        session.add(photo)

        # Equipment type
        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(
            id=eq_type_id, code="excavator_crawler", title="Гусеничный экскаватор"
        )
        session.add(eq_type)

        # Detection
        detection_id = uuid.uuid4()
        detection = Detection(
            id=detection_id,
            photo_id=photo_id,
            equipment_type_id=eq_type_id,
            bbox=[0.1, 0.2, 0.5, 0.6],
            score=0.95,
            model_version="v1.0",
        )
        session.add(detection)
        await session.commit()

        # Первая запись об evidence
        evidence1 = DeviationEvidence(
            id=uuid.uuid4(),
            deviation_id=dev_id,
            photo_id=photo_id,
            detection_id=detection_id,
        )
        session.add(evidence1)
        await session.commit()

        # Вторая запись с тем же (deviation_id, photo_id, detection_id)
        evidence2 = DeviationEvidence(
            id=uuid.uuid4(),
            deviation_id=dev_id,
            photo_id=photo_id,
            detection_id=detection_id,
        )
        session.add(evidence2)

        # Должно вызвать IntegrityError
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_status_basis_persists(container) -> None:
    """StatusBasis сохраняется и читается обратно."""
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
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Excavation", position=1)
        session.add(stage)

        # StageStatus
        status_id = uuid.uuid4()
        status = StageStatus(
            id=status_id,
            stage_id=stage_id,
            status="on_track",
            confidence="high",
        )
        session.add(status)

        # Observation
        obs_id = uuid.uuid4()
        observation = Observation(
            id=obs_id,
            site_id=site_id,
            observed_on=date(2026, 9, 24),
            photo_count=5,
            observability="high",
        )
        session.add(observation)
        await session.commit()

        # StatusBasis
        basis_id = uuid.uuid4()
        basis = StatusBasis(
            id=basis_id,
            status_id=status_id,
            observation_id=obs_id,
        )
        session.add(basis)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(StatusBasis, basis_id)
        assert fetched is not None
        assert fetched.id == basis_id
        assert fetched.status_id == status_id
        assert fetched.observation_id == obs_id


@pytest.mark.asyncio
async def test_unique_constraint_status_basis(container) -> None:
    """UNIQUE(status_id, observation_id) на status_basis.

    Попытка вставить две записи с одинаковыми status_id и observation_id вызывает IntegrityError.
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

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        stage_id = uuid.uuid4()
        stage = ScheduleStage(id=stage_id, schedule_id=schedule_id, name="Excavation", position=1)
        session.add(stage)

        # StageStatus
        status_id = uuid.uuid4()
        status = StageStatus(
            id=status_id,
            stage_id=stage_id,
            status="on_track",
            confidence="high",
        )
        session.add(status)

        # Observation
        obs_id = uuid.uuid4()
        observation = Observation(
            id=obs_id,
            site_id=site_id,
            observed_on=date(2026, 9, 24),
            photo_count=5,
            observability="high",
        )
        session.add(observation)
        await session.commit()

        # Первая запись
        basis1 = StatusBasis(
            id=uuid.uuid4(),
            status_id=status_id,
            observation_id=obs_id,
        )
        session.add(basis1)
        await session.commit()

        # Вторая запись с тем же status_id и observation_id
        basis2 = StatusBasis(
            id=uuid.uuid4(),
            status_id=status_id,
            observation_id=obs_id,
        )
        session.add(basis2)

        # Должно вызвать IntegrityError
        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_stage_status_fk_stage_cascade_delete() -> None:
    """FK stage_statuses.stage_id -> schedule_stages.id имеет ondelete=CASCADE."""
    table = StageStatus.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "stage_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"


@pytest.mark.asyncio
async def test_deviation_fk_site_cascade_delete() -> None:
    """FK deviations.site_id -> sites.id имеет ondelete=CASCADE."""
    table = Deviation.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "site_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"


@pytest.mark.asyncio
async def test_deviation_fk_stage_cascade_delete() -> None:
    """FK deviations.stage_id -> schedule_stages.id имеет ondelete=CASCADE."""
    table = Deviation.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "stage_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"


@pytest.mark.asyncio
async def test_deviation_evidence_fk_deviation_cascade_delete() -> None:
    """FK deviation_evidence.deviation_id -> deviations.id имеет ondelete=CASCADE."""
    table = DeviationEvidence.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "deviation_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"


@pytest.mark.asyncio
async def test_status_basis_fk_status_cascade_delete() -> None:
    """FK status_basis.status_id -> stage_statuses.id имеет ondelete=CASCADE."""
    table = StatusBasis.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "status_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"
