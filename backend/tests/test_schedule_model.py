"""Модели графика выполнения работ: таблицы schedules, schedule_stages, schedule_import_issues."""

import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domains.schedule.models import DatesSource, Schedule, ScheduleImportIssue, ScheduleStage
from app.domains.site.models import Site
from app.domains.user.models import User


@pytest.mark.asyncio
async def test_schedule_table_exists(engine: AsyncEngine) -> None:
    """Таблица schedules создана в схеме."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schedules'"
            )
        )
        assert result.scalar() == "schedules"


@pytest.mark.asyncio
async def test_schedule_stages_table_exists(engine: AsyncEngine) -> None:
    """Таблица schedule_stages создана в схеме."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schedule_stages'"
            )
        )
        assert result.scalar() == "schedule_stages"


@pytest.mark.asyncio
async def test_schedule_import_issues_table_exists(engine: AsyncEngine) -> None:
    """Таблица schedule_import_issues создана в схеме."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name='schedule_import_issues'"
            )
        )
        assert result.scalar() == "schedule_import_issues"


@pytest.mark.asyncio
async def test_schedule_columns(engine: AsyncEngine) -> None:
    """Колонки таблицы schedules соответствуют модели."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text("PRAGMA table_info(schedules)")
        )
        columns = {row[1] for row in result.all()}
        assert columns == {
            "id",
            "site_id",
            "source_filename",
            "imported_at",
            "rows_total",
            "rows_parsed",
            "parse_method",
        }


@pytest.mark.asyncio
async def test_schedule_stages_columns(engine: AsyncEngine) -> None:
    """Колонки таблицы schedule_stages соответствуют модели."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text("PRAGMA table_info(schedule_stages)")
        )
        columns = {row[1] for row in result.all()}
        assert columns == {
            "id",
            "schedule_id",
            "name",
            "position",
            "planned_start",
            "planned_end",
            "dates_source",
            "work_names",
        }


@pytest.mark.asyncio
async def test_schedule_import_issues_columns(engine: AsyncEngine) -> None:
    """Колонки таблицы schedule_import_issues соответствуют модели."""
    async with engine.connect() as conn:
        result = await conn.execute(
            __import__("sqlalchemy", fromlist=["text"]).text(
                "PRAGMA table_info(schedule_import_issues)"
            )
        )
        columns = {row[1] for row in result.all()}
        assert columns == {"id", "schedule_id", "row_number", "raw_row", "reason"}


@pytest.mark.asyncio
async def test_schedule_persists_with_site(engine: AsyncEngine, container) -> None:
    """Schedule сохраняется с site_id и читается обратно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Создаём пользователя и сайт
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Construction Site", owner_id=owner_id)
        session.add(site)

        # Создаём график
        schedule = Schedule(
            id=uuid.uuid4(),
            site_id=site_id,
            source_filename="schedule.xlsx",
            rows_total=100,
            rows_parsed=95,
        )
        session.add(schedule)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(Schedule, schedule.id)
        assert fetched is not None
        assert fetched.id == schedule.id
        assert fetched.site_id == site_id
        assert fetched.source_filename == "schedule.xlsx"
        assert fetched.rows_total == 100
        assert fetched.rows_parsed == 95
        assert fetched.imported_at is not None


@pytest.mark.asyncio
async def test_schedule_unique_site_id(engine: AsyncEngine, container) -> None:
    """Второй График для одного сайта вызывает IntegrityError."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Создаём пользователя и сайт
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="Jane Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Construction Site", owner_id=owner_id)
        session.add(site)

        # Создаём первый график
        schedule1 = Schedule(id=uuid.uuid4(), site_id=site_id, source_filename="schedule1.xlsx")
        session.add(schedule1)
        await session.commit()

        # Пытаемся создать второй график для того же сайта
        schedule2 = Schedule(id=uuid.uuid4(), site_id=site_id, source_filename="schedule2.xlsx")
        session.add(schedule2)

        with pytest.raises(IntegrityError):
            await session.commit()


@pytest.mark.asyncio
async def test_schedule_fk_cascade_delete(engine: AsyncEngine) -> None:
    """FK schedules.site_id -> sites.id имеет ondelete=CASCADE."""
    # На SQLite проверяем метаданные вместо реального cascade delete

    table = Schedule.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "site_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"


@pytest.mark.asyncio
async def test_schedule_stage_persists(engine: AsyncEngine, container) -> None:
    """ScheduleStage сохраняется и читается обратно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Создаём пользователя, сайт и график
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Construction Site", owner_id=owner_id)
        session.add(site)

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        # Создаём этап
        stage_id = uuid.uuid4()
        stage = ScheduleStage(
            id=stage_id,
            schedule_id=schedule_id,
            name="Foundation Work",
            position=1,
            planned_start=date(2026, 10, 1),
            planned_end=date(2026, 10, 31),
            dates_source=DatesSource.FILE.value,
        )
        session.add(stage)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(ScheduleStage, stage_id)
        assert fetched is not None
        assert fetched.id == stage_id
        assert fetched.schedule_id == schedule_id
        assert fetched.name == "Foundation Work"
        assert fetched.position == 1
        assert fetched.planned_start == date(2026, 10, 1)
        assert fetched.planned_end == date(2026, 10, 31)
        assert fetched.dates_source == DatesSource.FILE.value


@pytest.mark.asyncio
async def test_schedule_import_issue_persists(engine: AsyncEngine, container) -> None:
    """ScheduleImportIssue сохраняется и читается обратно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Создаём пользователя, сайт и график
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Construction Site", owner_id=owner_id)
        session.add(site)

        schedule_id = uuid.uuid4()
        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)

        # Создаём ошибку импорта
        issue_id = uuid.uuid4()
        issue = ScheduleImportIssue(
            id=issue_id,
            schedule_id=schedule_id,
            row_number=5,
            raw_row="Some raw data from row 5",
            reason="Invalid date format",
        )
        session.add(issue)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(ScheduleImportIssue, issue_id)
        assert fetched is not None
        assert fetched.id == issue_id
        assert fetched.schedule_id == schedule_id
        assert fetched.row_number == 5
        assert fetched.raw_row == "Some raw data from row 5"
        assert fetched.reason == "Invalid date format"


@pytest.mark.asyncio
async def test_schedule_stage_fk_cascade_delete(engine: AsyncEngine) -> None:
    """FK schedule_stages.schedule_id -> schedules.id имеет ondelete=CASCADE."""
    table = ScheduleStage.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "schedule_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"


@pytest.mark.asyncio
async def test_schedule_import_issue_fk_cascade_delete(engine: AsyncEngine) -> None:
    """FK schedule_import_issues.schedule_id -> schedules.id имеет ondelete=CASCADE."""
    table = ScheduleImportIssue.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "schedule_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"
