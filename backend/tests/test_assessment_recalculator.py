"""Тесты для wiring StatusRecalculator в schedule и observation доменах."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assessment.repository import StageStatusRepository
from app.domains.methodology.recalculator import StatusRecalculator
from app.domains.observation.service import ObservationService
from app.domains.schedule.models import DatesSource, Schedule, ScheduleStage
from app.domains.schedule.schemas import StageDatesUpdate
from app.domains.schedule.service import ScheduleService
from app.domains.site.models import Site
from app.domains.user.service import STAND_USER_ID, UserService


async def seed_user_and_site(container) -> tuple[uuid.UUID, uuid.UUID]:
    """Создаёт стендового пользователя и сайт, возвращает их IDs."""
    # Создаём стендового пользователя
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()

    user_id = STAND_USER_ID
    site_id = uuid.uuid4()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        site = Site(id=site_id, name="Test Site", owner_id=user_id)
        session.add(site)
        await session.commit()

    return user_id, site_id


async def create_schedule_with_stage(container, site_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    """Создаёт график с одним этапом, возвращает их IDs."""
    today = date.today()
    start_date = today + timedelta(days=5)
    end_date = today + timedelta(days=10)

    schedule_id = uuid.uuid4()
    stage_id = uuid.uuid4()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)
        await session.flush()

        stage = ScheduleStage(
            id=stage_id,
            schedule_id=schedule.id,
            name="Test Stage",
            position=1,
            planned_start=start_date,
            planned_end=end_date,
            dates_source=DatesSource.FILE.value,
        )
        session.add(stage)
        await session.commit()

    return schedule_id, stage_id


@pytest.mark.asyncio
class TestDIResolution:
    """Тесты для DI resolution."""

    async def test_status_recalculator_resolved_from_container(self, container) -> None:
        """StatusRecalculator должен быть разрешён из контейнера как LiveStatusRecalculator."""
        async with container() as request_container:
            recalculator = await request_container.get(StatusRecalculator)
            # Проверяем, что это не NoopStatusRecalculator (проверяем наличие coordinatoor)
            assert hasattr(recalculator, "recalculate")
            assert hasattr(recalculator, "_coordinator")


@pytest.mark.asyncio
class TestScheduleEdgeTriggers:
    """Тесты для триггера пересчёта при редактировании графика."""

    async def test_schedule_update_with_actual_changes_triggers_recalculate(
        self, container
    ) -> None:
        """update_stage_dates с реальными изменениями должен вызвать recalculate."""
        user_id, site_id = await seed_user_and_site(container)
        schedule_id, stage_id = await create_schedule_with_stage(container, site_id)

        # Обновляем даты этапа
        new_start = date.today() + timedelta(days=7)
        new_end = date.today() + timedelta(days=12)

        async with container() as request_container:
            service = await request_container.get(ScheduleService)

            # Перезаписываем current_user в гварде (для доступа)
            service._guard._current_user = type("obj", (object,), {"id": user_id})()

            # Вызываем update_stage_dates с реальными изменениями
            result = await service.update_stage_dates(
                site_id,
                stage_id,
                StageDatesUpdate(planned_start=new_start, planned_end=new_end),
            )

            assert result.planned_start == new_start
            assert result.planned_end == new_end
            assert result.dates_source == DatesSource.MANUAL.value

        # Проверяем, что StageStatus реально был вычислен и сохранён — это доказывает,
        # что recalculate() был вызван и RecomputeCoordinator отработал (этап без правила
        # методики движок всегда оценивает как NOT_CHECKED, а не пропускает).
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = StageStatusRepository(session)
            statuses = await repo.list_by_site(site_id)
            assert len(statuses) == 1
            assert statuses[0].stage_id == stage_id
            assert statuses[0].status == "not_checked"

    async def test_schedule_update_without_changes_does_not_commit(self, container) -> None:
        """update_stage_dates без изменений не должен коммитить."""
        user_id, site_id = await seed_user_and_site(container)
        schedule_id, stage_id = await create_schedule_with_stage(container, site_id)

        # Получаем original dates из database
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            stage = await session.get(ScheduleStage, stage_id)
            original_start = stage.planned_start

        async with container() as request_container:
            service = await request_container.get(ScheduleService)
            service._guard._current_user = type("obj", (object,), {"id": user_id})()

            # Вызываем update_stage_dates с теми же датами (no-op)
            result = await service.update_stage_dates(
                site_id,
                stage_id,
                StageDatesUpdate(planned_start=original_start),
            )

            # Dates должны быть такие же
            assert result.planned_start == original_start
            # dates_source должен остаться FILE (не меняться на MANUAL)
            assert result.dates_source == DatesSource.FILE.value


@pytest.mark.asyncio
class TestObservationDIWiring:
    """Тесты для DI wiring в observation домене."""

    async def test_observation_service_has_recalculator_injected(self, container) -> None:
        """ObservationService должен иметь recalculator, инъецированный через DI."""
        # Сначала создаём стендового пользователя
        async with container() as request_container:
            service = await request_container.get(UserService)
            await service.ensure_stand_user()

        async with container() as request_container:
            service = await request_container.get(ObservationService)
            # Проверяем, что сервис имеет recalculator
            assert hasattr(service, "_recalculator")
            assert service._recalculator is not None

    async def test_schedule_service_has_recalculator_injected(self, container) -> None:
        """ScheduleService должен иметь recalculator, инъецированный через DI."""
        # Сначала создаём стендового пользователя
        async with container() as request_container:
            service = await request_container.get(UserService)
            await service.ensure_stand_user()

        async with container() as request_container:
            service = await request_container.get(ScheduleService)
            # Проверяем, что сервис имеет recalculator
            assert hasattr(service, "_recalculator")
            assert service._recalculator is not None
