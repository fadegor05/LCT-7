"""RecomputeCoordinator и LiveStatusRecalculator тесты."""

import logging
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ml.base import DetectorClient
from app.core.settings import AsOfMode
from app.domains.assessment.coordinator import AsOfConfig, RecomputeCoordinator
from app.domains.assessment.engine import EngineConfig, RuleEngine
from app.domains.assessment.models import DeviationType, StageStatusValue
from app.domains.assessment.recalculator import LiveStatusRecalculator
from app.domains.assessment.repository import (
    DeviationEvidenceRepository,
    DeviationRepository,
    StageStatusRepository,
    StatusBasisRepository,
)
from app.domains.methodology.models import (
    EquipmentRequirement,
    EquipmentSet,
    EquipmentType,
    MethodologyRule,
    Obligation,
)
from app.domains.methodology.repository import MethodologyRepository
from app.domains.observation.models import Observation, ObservedEquipment
from app.domains.observation.repository import (
    ObservationRepository,
    ObservedEquipmentRepository,
)
from app.domains.photo.models import Photo, ProcessingStatus
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.schedule.models import Schedule, ScheduleStage
from app.domains.schedule.repository import ScheduleRepository
from app.domains.site.models import Site
from app.domains.user.models import User


async def seed_user(container) -> User:
    """Создаёт и возвращает стендового пользователя."""
    user_id = uuid.uuid4()
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        user = User(id=user_id, full_name="Test User")
        session.add(user)
        await session.commit()
    return user


async def create_coordinator(
    container: object, engine_config: EngineConfig, as_of_config: AsOfConfig | None = None
) -> RecomputeCoordinator:
    """Создать RecomputeCoordinator из контейнера."""
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        stage_status_repo = StageStatusRepository(session)
        deviation_repo = DeviationRepository(session)
        deviation_evidence_repo = DeviationEvidenceRepository(session)
        status_basis_repo = StatusBasisRepository(session)
        schedule_repo = ScheduleRepository(session)
        methodology_repo = MethodologyRepository(session)
        observation_repo = ObservationRepository(session)
        observed_equipment_repo = ObservedEquipmentRepository(session)
        photo_repo = PhotoRepository(session)
        detection_repo = DetectionRepository(session)

        engine = RuleEngine(engine_config)
        # as_of_config is Optional here only as a test-helper convenience;
        # RecomputeCoordinator's own param is a concrete AsOfConfig (its own
        # default), so we only forward the kwarg when the caller passed one —
        # никогда не передаём буквальный None.
        kwargs = {} if as_of_config is None else {"as_of_config": as_of_config}
        coordinator = RecomputeCoordinator(
            engine=engine,
            stage_status_repo=stage_status_repo,
            deviation_repo=deviation_repo,
            deviation_evidence_repo=deviation_evidence_repo,
            status_basis_repo=status_basis_repo,
            schedule_repo=schedule_repo,
            methodology_repo=methodology_repo,
            observation_repo=observation_repo,
            observed_equipment_repo=observed_equipment_repo,
            photo_repo=photo_repo,
            detection_repo=detection_repo,
            session=session,
            **kwargs,
        )
        return coordinator


class TestRecomputeCoordinator:
    """Тесты RecomputeCoordinator.recompute_site."""

    @pytest.mark.asyncio
    async def test_no_schedule_returns_early(self, container) -> None:
        """Если нет графика, возвращаем None без ошибок."""
        user = await seed_user(container)
        site_id = uuid.uuid4()

        # Создаём сайт без графика
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)
            await session.commit()

        # Вызываем recompute_site
        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=2,
        )
        async with container() as request_container:
            coordinator = await create_coordinator(container, engine_config)
            await coordinator.recompute_site(site_id)

        # Проверяем, что никаких статусов не создано
        async with container() as request_container:
            repo = StageStatusRepository(await request_container.get(AsyncSession))
            statuses = await repo.list_by_site(site_id)
            assert len(statuses) == 0

    @pytest.mark.asyncio
    async def test_end_to_end_on_track(self, container) -> None:
        """End-to-end: маркер наблюдается в запланированное время -> on_track."""
        user = await seed_user(container)
        site_id = uuid.uuid4()
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_set_id = uuid.uuid4()
        equipment_type_id = uuid.uuid4()
        today = date.today()
        obs_date = today - timedelta(days=5)

        # Создаём всю иерархию: сайт, график, этап, методику, оборудование, наблюдение
        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            # Сайт
            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)

            # График
            schedule = Schedule(id=uuid.uuid4(), site_id=site_id)
            session.add(schedule)
            await session.flush()

            # Этап: плановое окно за несколько дней до наблюдения
            stage = ScheduleStage(
                id=stage_id,
                schedule_id=schedule.id,
                name="Stage 1",
                position=1,
                planned_start=obs_date - timedelta(days=3),
                planned_end=obs_date + timedelta(days=3),
            )
            session.add(stage)

            # Тип оборудования
            eq_type = EquipmentType(id=equipment_type_id, code="crane", title="Crane", synonyms=[])
            session.add(eq_type)
            await session.flush()

            # Методика: правило -> набор -> требования
            rule = MethodologyRule(
                id=rule_id,
                site_id=site_id,
                stage_id=stage_id,
                is_verifiable=True,
                unverifiable_reason=None,
            )
            session.add(rule)
            await session.flush()

            equipment_set = EquipmentSet(id=equipment_set_id, rule_id=rule_id, position=1)
            session.add(equipment_set)
            await session.flush()

            requirement = EquipmentRequirement(
                id=uuid.uuid4(),
                set_id=equipment_set_id,
                equipment_type_id=equipment_type_id,
                min_count=1,
                obligation=Obligation.NORMATIVE.value,
                gesn_code="01.001",
            )
            session.add(requirement)

            # Наблюдение: маркер наблюдается в запланированное время
            observation = Observation(
                id=uuid.uuid4(),
                site_id=site_id,
                observed_on=obs_date,
                photo_count=1,
                observability="high",
            )
            session.add(observation)
            await session.flush()

            # Наблюдаемое оборудование
            observed_eq = ObservedEquipment(
                id=uuid.uuid4(),
                observation_id=observation.id,
                equipment_type_id=equipment_type_id,
                count_min=1,
                activity="works",
                confidence="high",
            )
            session.add(observed_eq)
            await session.commit()

        # Вызываем recompute_site
        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=1,  # Only 1 observation in test
        )
        async with container() as request_container:
            coordinator = await create_coordinator(container, engine_config)
            await coordinator.recompute_site(site_id)

        # Проверяем: создан StageStatus с статусом on_track
        async with container() as request_container:
            repo = StageStatusRepository(await request_container.get(AsyncSession))
            status = await repo.get_by_stage(stage_id)
            assert status is not None
            assert status.status == StageStatusValue.ON_TRACK.value
            assert status.delay_days is None
            assert status.confidence == "high"  # high with min_confirming_observations=1

            # Проверяем StatusBasis
            basis_repo = StatusBasisRepository(await request_container.get(AsyncSession))
            basis_rows = await basis_repo.list_by_status(status.id)
            assert len(basis_rows) == 1

    @pytest.mark.asyncio
    async def test_idempotency_same_data(self, container) -> None:
        """Calling recompute_site twice with same data -> same single row."""
        user = await seed_user(container)
        site_id = uuid.uuid4()
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_set_id = uuid.uuid4()
        equipment_type_id = uuid.uuid4()
        today = date.today()
        obs_date = today - timedelta(days=5)

        # Создаём сценарий
        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)

            schedule = Schedule(id=uuid.uuid4(), site_id=site_id)
            session.add(schedule)
            await session.flush()

            stage = ScheduleStage(
                id=stage_id,
                schedule_id=schedule.id,
                name="Stage 1",
                position=1,
                planned_start=date(2025, 1, 10),
                planned_end=date(2025, 1, 20),
            )
            session.add(stage)

            eq_type = EquipmentType(id=equipment_type_id, code="crane", title="Crane", synonyms=[])
            session.add(eq_type)
            await session.flush()

            rule = MethodologyRule(
                id=rule_id,
                site_id=site_id,
                stage_id=stage_id,
                is_verifiable=True,
                unverifiable_reason=None,
            )
            session.add(rule)
            await session.flush()

            equipment_set = EquipmentSet(id=equipment_set_id, rule_id=rule_id, position=1)
            session.add(equipment_set)
            await session.flush()

            requirement = EquipmentRequirement(
                id=uuid.uuid4(),
                set_id=equipment_set_id,
                equipment_type_id=equipment_type_id,
                min_count=1,
                obligation=Obligation.NORMATIVE.value,
                gesn_code="01.001",
            )
            session.add(requirement)

            observation = Observation(
                id=uuid.uuid4(),
                site_id=site_id,
                observed_on=obs_date,
                photo_count=1,
                observability="high",
            )
            session.add(observation)
            await session.flush()

            observed_eq = ObservedEquipment(
                id=uuid.uuid4(),
                observation_id=observation.id,
                equipment_type_id=equipment_type_id,
                count_min=1,
                activity="works",
                confidence="high",
            )
            session.add(observed_eq)
            await session.commit()

        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=2,
        )

        # Первый вызов
        async with container() as request_container:
            coordinator = await create_coordinator(container, engine_config)
            await coordinator.recompute_site(site_id)

        # Проверяем, что создана одна строка
        async with container() as request_container:
            repo = StageStatusRepository(await request_container.get(AsyncSession))
            statuses1 = await repo.list_by_site(site_id)
            assert len(statuses1) == 1
            first_id = statuses1[0].id

        # Второй вызов с теми же данными
        async with container() as request_container:
            coordinator = await create_coordinator(container, engine_config)
            await coordinator.recompute_site(site_id)

        # Проверяем, что всё ещё одна строка с тем же ID
        async with container() as request_container:
            repo = StageStatusRepository(await request_container.get(AsyncSession))
            statuses2 = await repo.list_by_site(site_id)
            assert len(statuses2) == 1
            assert statuses2[0].id == first_id

    @pytest.mark.asyncio
    async def test_window_not_started_no_status_row(self, container) -> None:
        """Этап, чьё окно ещё не началось, не создаёт StageStatus."""
        user = await seed_user(container)
        site_id = uuid.uuid4()
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_set_id = uuid.uuid4()
        equipment_type_id = uuid.uuid4()
        today = date.today()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)

            schedule = Schedule(id=uuid.uuid4(), site_id=site_id)
            session.add(schedule)
            await session.flush()

            # Окно: далеко в будущем от today
            stage = ScheduleStage(
                id=stage_id,
                schedule_id=schedule.id,
                name="Stage 1",
                position=1,
                planned_start=today + timedelta(days=30),
                planned_end=today + timedelta(days=45),
            )
            session.add(stage)

            eq_type = EquipmentType(id=equipment_type_id, code="crane", title="Crane", synonyms=[])
            session.add(eq_type)
            await session.flush()

            rule = MethodologyRule(
                id=rule_id,
                site_id=site_id,
                stage_id=stage_id,
                is_verifiable=True,
                unverifiable_reason=None,
            )
            session.add(rule)
            await session.flush()

            equipment_set = EquipmentSet(id=equipment_set_id, rule_id=rule_id, position=1)
            session.add(equipment_set)
            await session.flush()

            requirement = EquipmentRequirement(
                id=uuid.uuid4(),
                set_id=equipment_set_id,
                equipment_type_id=equipment_type_id,
                min_count=1,
                obligation=Obligation.NORMATIVE.value,
                gesn_code="01.001",
            )
            session.add(requirement)
            await session.commit()

        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=2,
        )
        async with container() as request_container:
            coordinator = await create_coordinator(container, engine_config)
            await coordinator.recompute_site(site_id)

        async with container() as request_container:
            repo = StageStatusRepository(await request_container.get(AsyncSession))
            statuses = await repo.list_by_site(site_id)
            assert len(statuses) == 0

    @pytest.mark.asyncio
    async def test_window_pushed_into_future_deletes_status(self, container) -> None:
        """Отодвинуть окно в будущее после recompute -> delete_missing удаляет статус."""
        user = await seed_user(container)
        site_id = uuid.uuid4()
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_set_id = uuid.uuid4()
        equipment_type_id = uuid.uuid4()
        today = date.today()
        obs_date = today - timedelta(days=5)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)

            schedule = Schedule(id=uuid.uuid4(), site_id=site_id)
            session.add(schedule)
            await session.flush()

            stage = ScheduleStage(
                id=stage_id,
                schedule_id=schedule.id,
                name="Stage 1",
                position=1,
                planned_start=date(2025, 1, 10),
                planned_end=date(2025, 1, 20),
            )
            session.add(stage)

            eq_type = EquipmentType(id=equipment_type_id, code="crane", title="Crane", synonyms=[])
            session.add(eq_type)
            await session.flush()

            rule = MethodologyRule(
                id=rule_id,
                site_id=site_id,
                stage_id=stage_id,
                is_verifiable=True,
                unverifiable_reason=None,
            )
            session.add(rule)
            await session.flush()

            equipment_set = EquipmentSet(id=equipment_set_id, rule_id=rule_id, position=1)
            session.add(equipment_set)
            await session.flush()

            requirement = EquipmentRequirement(
                id=uuid.uuid4(),
                set_id=equipment_set_id,
                equipment_type_id=equipment_type_id,
                min_count=1,
                obligation=Obligation.NORMATIVE.value,
                gesn_code="01.001",
            )
            session.add(requirement)

            observation = Observation(
                id=uuid.uuid4(),
                site_id=site_id,
                observed_on=obs_date,
                photo_count=1,
                observability="high",
            )
            session.add(observation)
            await session.flush()

            observed_eq = ObservedEquipment(
                id=uuid.uuid4(),
                observation_id=observation.id,
                equipment_type_id=equipment_type_id,
                count_min=1,
                activity="works",
                confidence="high",
            )
            session.add(observed_eq)
            await session.commit()

        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=1,
        )

        # Первый recompute -> создан статус
        async with container() as request_container:
            coordinator = await create_coordinator(container, engine_config)
            await coordinator.recompute_site(site_id)

        async with container() as request_container:
            repo = StageStatusRepository(await request_container.get(AsyncSession))
            statuses = await repo.list_by_site(site_id)
            assert len(statuses) == 1

        # Отодвинуть окно в будущее (далеко за today)
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            schedule_repo = ScheduleRepository(session)
            schedule = await schedule_repo.get_by_site(site_id)
            assert schedule is not None
            stage_to_update = await schedule_repo.get_stage(schedule.id, stage_id)
            if stage_to_update:
                stage_to_update.planned_start = today + timedelta(days=30)
                stage_to_update.planned_end = today + timedelta(days=45)
                await session.commit()

        # Второй recompute -> окно не начинается, статус удаляется
        async with container() as request_container:
            coordinator = await create_coordinator(container, engine_config)
            await coordinator.recompute_site(site_id)

        async with container() as request_container:
            repo = StageStatusRepository(await request_container.get(AsyncSession))
            statuses = await repo.list_by_site(site_id)
            assert len(statuses) == 0

    @pytest.mark.asyncio
    async def test_deviations_evidence_with_photos(self, container) -> None:
        """Девиация с матчинг фотографией -> создан DeviationEvidence."""
        user = await seed_user(container)
        site_id = uuid.uuid4()
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_set_id = uuid.uuid4()
        equipment_type_id = uuid.uuid4()
        today = date.today()
        obs_date = today - timedelta(days=5)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)

            schedule = Schedule(id=uuid.uuid4(), site_id=site_id)
            session.add(schedule)
            await session.flush()

            stage = ScheduleStage(
                id=stage_id,
                schedule_id=schedule.id,
                name="Stage 1",
                position=1,
                planned_start=obs_date - timedelta(days=3),
                planned_end=obs_date + timedelta(days=3),
            )
            session.add(stage)

            eq_type = EquipmentType(id=equipment_type_id, code="crane", title="Crane", synonyms=[])
            session.add(eq_type)
            await session.flush()

            rule = MethodologyRule(
                id=rule_id,
                site_id=site_id,
                stage_id=stage_id,
                is_verifiable=True,
                unverifiable_reason=None,
            )
            session.add(rule)
            await session.flush()

            equipment_set = EquipmentSet(id=equipment_set_id, rule_id=rule_id, position=1)
            session.add(equipment_set)
            await session.flush()

            requirement = EquipmentRequirement(
                id=uuid.uuid4(),
                set_id=equipment_set_id,
                equipment_type_id=equipment_type_id,
                min_count=1,
                obligation=Obligation.NORMATIVE.value,
                gesn_code="01.001",
            )
            session.add(requirement)

            # Наблюдение на другую дату (вызовет отклонение)
            obs_other_date = obs_date + timedelta(days=3)
            observation = Observation(
                id=uuid.uuid4(),
                site_id=site_id,
                observed_on=obs_other_date,
                photo_count=3,
                observability="high",
            )
            session.add(observation)
            await session.flush()

            # NO техника -> missing_equipment девиация
            await session.commit()

        # Добавляем фотографию для девиации
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            photo = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="test.jpg",
                original_name="test.jpg",
                width=100,
                height=100,
                captured_on=obs_other_date,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo)
            await session.commit()

        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=2,
        )
        async with container() as request_container:
            coordinator = await create_coordinator(container, engine_config)
            await coordinator.recompute_site(site_id)

        # Проверяем DevationEvidence
        async with container() as request_container:
            dev_repo = DeviationRepository(await request_container.get(AsyncSession))
            deviations = await dev_repo.list_by_site(site_id)
            assert len(deviations) > 0

            # Найдём missing_equipment девиацию
            missing_dev = next(
                (d for d in deviations if d.type == DeviationType.MISSING_EQUIPMENT.value),
                None,
            )
            assert missing_dev is not None

            evidence_repo = DeviationEvidenceRepository(await request_container.get(AsyncSession))
            evidence = await evidence_repo.list_by_deviation(missing_dev.id)
            assert len(evidence) > 0

    @pytest.mark.asyncio
    async def test_detector_never_called(self, container) -> None:
        """DoD: detector не вызывается coordinator."""
        user = await seed_user(container)
        site_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)
            await session.commit()

        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=2,
        )
        async with container() as request_container:
            coordinator = await create_coordinator(container, engine_config)
            await coordinator.recompute_site(site_id)

        # Проверяем, что detector никогда не вызывался
        async with container() as request_container:
            detector = await request_container.get(DetectorClient)
            assert detector.calls == []

    @pytest.mark.asyncio
    async def test_injected_today_is_passed_to_engine(self, container) -> None:
        """Verify that injected 'today' callable is used instead of date.today()."""
        from datetime import timedelta

        user = await seed_user(container)
        site_id = uuid.uuid4()
        stage_id = uuid.uuid4()
        today = date.today()
        injected_today = today - timedelta(days=30)

        # Create site, schedule, stage, methodology
        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)
            await session.flush()

            schedule = Schedule(id=uuid.uuid4(), site_id=site_id)
            session.add(schedule)
            await session.flush()

            stage = ScheduleStage(
                id=stage_id,
                schedule_id=schedule.id,
                name="Test Stage",
                position=1,
                planned_start=today - timedelta(days=40),
                planned_end=today - timedelta(days=20),  # ended before injected_today
            )
            session.add(stage)
            await session.commit()

        # Create coordinator with injected today
        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=2,
        )
        async with container() as request_container:
            # Build coordinator manually with injected today
            session = await request_container.get(AsyncSession)
            stage_status_repo = StageStatusRepository(session)
            deviation_repo = DeviationRepository(session)
            deviation_evidence_repo = DeviationEvidenceRepository(session)
            status_basis_repo = StatusBasisRepository(session)
            schedule_repo = ScheduleRepository(session)
            methodology_repo = MethodologyRepository(session)
            observation_repo = ObservationRepository(session)
            observed_equipment_repo = ObservedEquipmentRepository(session)
            photo_repo = PhotoRepository(session)
            detection_repo = DetectionRepository(session)

            engine = RuleEngine(engine_config)
            coordinator = RecomputeCoordinator(
                engine=engine,
                stage_status_repo=stage_status_repo,
                deviation_repo=deviation_repo,
                deviation_evidence_repo=deviation_evidence_repo,
                status_basis_repo=status_basis_repo,
                schedule_repo=schedule_repo,
                methodology_repo=methodology_repo,
                observation_repo=observation_repo,
                observed_equipment_repo=observed_equipment_repo,
                photo_repo=photo_repo,
                detection_repo=detection_repo,
                session=session,
                today=lambda: injected_today,  # Inject custom reference date
            )

            # Run recompute with injected today
            await coordinator.recompute_site(site_id)

            # Verify that stage status reflects the injected date
            # (stage ended before injected_today, so should have a status)
            status = await stage_status_repo.get_by_stage(stage_id)
            assert status is not None, "Stage should have status computed with injected date"


class TestRecomputeCoordinatorAsOfMode:
    """Тесты режима опорной даты (LCT-14)."""

    @pytest.mark.asyncio
    async def test_last_observation_mode_uses_site_own_last_date(self, container) -> None:
        """last_observation берёт дату последнего наблюдения НА ЭТОЙ площадке,
        а не реальное "сегодня"."""
        user = await seed_user(container)
        site_id = uuid.uuid4()
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_set_id = uuid.uuid4()
        equipment_type_id = uuid.uuid4()

        # Обе даты наблюдений — задолго до реального "сегодня" (2026):
        # если бы опорной датой было date.today(), stale_data сработал бы
        # (диапазон в годы, а stale_data_days всего 7).
        earlier_obs_date = date(2023, 1, 1)
        later_obs_date = date(2023, 6, 1)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)

            schedule = Schedule(id=uuid.uuid4(), site_id=site_id)
            session.add(schedule)
            await session.flush()

            # Плановое окно охватывает оба наблюдения.
            stage = ScheduleStage(
                id=stage_id,
                schedule_id=schedule.id,
                name="Stage 1",
                position=1,
                planned_start=earlier_obs_date - timedelta(days=3),
                planned_end=later_obs_date + timedelta(days=3),
            )
            session.add(stage)

            eq_type = EquipmentType(id=equipment_type_id, code="crane", title="Crane", synonyms=[])
            session.add(eq_type)
            await session.flush()

            rule = MethodologyRule(
                id=rule_id,
                site_id=site_id,
                stage_id=stage_id,
                is_verifiable=True,
                unverifiable_reason=None,
            )
            session.add(rule)
            await session.flush()

            equipment_set = EquipmentSet(id=equipment_set_id, rule_id=rule_id, position=1)
            session.add(equipment_set)
            await session.flush()

            requirement = EquipmentRequirement(
                id=uuid.uuid4(),
                set_id=equipment_set_id,
                equipment_type_id=equipment_type_id,
                min_count=1,
                obligation=Obligation.NORMATIVE.value,
                gesn_code="01.001",
            )
            session.add(requirement)

            # Два наблюдения площадки, оба с требуемой техникой.
            for obs_date in (earlier_obs_date, later_obs_date):
                observation = Observation(
                    id=uuid.uuid4(),
                    site_id=site_id,
                    observed_on=obs_date,
                    photo_count=1,
                    observability="high",
                )
                session.add(observation)
                await session.flush()

                observed_eq = ObservedEquipment(
                    id=uuid.uuid4(),
                    observation_id=observation.id,
                    equipment_type_id=equipment_type_id,
                    count_min=1,
                    activity="works",
                    confidence="high",
                )
                session.add(observed_eq)

            await session.commit()

        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=2,
        )

        # Базовая проверка: с обычным поведением (реальное date.today())
        # 2023-е наблюдения — это данные из прошлого на годы, stale_data
        # ДОЛЖЕН сработать. Подтверждает, что датасет реально "старый"
        # относительно реального "сегодня" и что as-of дата тут значима.
        coordinator = await create_coordinator(container, engine_config)
        await coordinator.recompute_site(site_id)

        async with container() as request_container:
            dev_repo = DeviationRepository(await request_container.get(AsyncSession))
            deviations = await dev_repo.list_by_site(site_id)
            assert any(d.type == DeviationType.STALE_DATA.value for d in deviations), (
                "expected stale_data with real date.today() as baseline "
                "(2023 observations are years old)"
            )

        # Теперь пересчитываем в режиме last_observation: опорной датой
        # должна стать дата ПОСЛЕДНЕГО наблюдения площадки (later_obs_date),
        # а не реальное date.today() -> stale_data больше не должен сработать.
        as_of_config = AsOfConfig(mode=AsOfMode.LAST_OBSERVATION, fixed_date=None)
        coordinator = await create_coordinator(container, engine_config, as_of_config)
        await coordinator.recompute_site(site_id)

        async with container() as request_container:
            dev_repo = DeviationRepository(await request_container.get(AsyncSession))
            deviations = await dev_repo.list_by_site(site_id)
            assert not any(d.type == DeviationType.STALE_DATA.value for d in deviations), (
                "stale_data should not fire when as-of is the site's own last observation"
            )

            status_repo = StageStatusRepository(await request_container.get(AsyncSession))
            status = await status_repo.get_by_stage(stage_id)
            assert status is not None
            assert status.status == StageStatusValue.ON_TRACK.value

    @pytest.mark.asyncio
    async def test_last_observation_mode_falls_back_to_today_without_observations(
        self, container
    ) -> None:
        """Площадка без наблюдений в режиме last_observation — fallback на
        обычное поведение (self._today()), без падения."""
        user = await seed_user(container)
        site_id = uuid.uuid4()
        # Отличается от реального date.today(), чтобы можно было отличить
        # "упало в fallback на self._today()" от "проигнорировало fallback".
        injected_today = date(2023, 6, 1)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)

            # График без этапов и без единого наблюдения на площадке.
            schedule = Schedule(id=uuid.uuid4(), site_id=site_id)
            session.add(schedule)
            await session.commit()

        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=2,
        )
        as_of_config = AsOfConfig(mode=AsOfMode.LAST_OBSERVATION, fixed_date=None)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            stage_status_repo = StageStatusRepository(session)
            deviation_repo = DeviationRepository(session)
            deviation_evidence_repo = DeviationEvidenceRepository(session)
            status_basis_repo = StatusBasisRepository(session)
            schedule_repo = ScheduleRepository(session)
            methodology_repo = MethodologyRepository(session)
            observation_repo = ObservationRepository(session)
            observed_equipment_repo = ObservedEquipmentRepository(session)
            photo_repo = PhotoRepository(session)
            detection_repo = DetectionRepository(session)

            engine = RuleEngine(engine_config)
            coordinator = RecomputeCoordinator(
                engine=engine,
                stage_status_repo=stage_status_repo,
                deviation_repo=deviation_repo,
                deviation_evidence_repo=deviation_evidence_repo,
                status_basis_repo=status_basis_repo,
                schedule_repo=schedule_repo,
                methodology_repo=methodology_repo,
                observation_repo=observation_repo,
                observed_equipment_repo=observed_equipment_repo,
                photo_repo=photo_repo,
                detection_repo=detection_repo,
                session=session,
                today=lambda: injected_today,
                as_of_config=as_of_config,
            )

            # Не должно падать, несмотря на отсутствие наблюдений.
            await coordinator.recompute_site(site_id)

        async with container() as request_container:
            dev_repo = DeviationRepository(await request_container.get(AsyncSession))
            deviations = await dev_repo.list_by_site(site_id)
            stale = next((d for d in deviations if d.type == DeviationType.STALE_DATA.value), None)
            # Без наблюдений stale_data всегда срабатывает (latest_obs_on is None).
            assert stale is not None
            # Опорная дата упала обратно именно на self._today() (инжектированный
            # Clock), а не на реальное date.today() — период отклонения
            # датирован ИМЕННО инжектированной датой.
            assert stale.period_start == injected_today
            assert stale.period_end == injected_today

    @pytest.mark.asyncio
    async def test_default_mode_is_today_unchanged(self, container) -> None:
        """Без as_of_config (или явно AsOfMode.TODAY) — поведение как раньше,
        date.today(), регресс не допускается."""
        user = await seed_user(container)
        site_id = uuid.uuid4()
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_set_id = uuid.uuid4()
        equipment_type_id = uuid.uuid4()
        today = date.today()
        obs_date = today - timedelta(days=5)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)

            schedule = Schedule(id=uuid.uuid4(), site_id=site_id)
            session.add(schedule)
            await session.flush()

            stage = ScheduleStage(
                id=stage_id,
                schedule_id=schedule.id,
                name="Stage 1",
                position=1,
                planned_start=obs_date - timedelta(days=3),
                planned_end=obs_date + timedelta(days=3),
            )
            session.add(stage)

            eq_type = EquipmentType(id=equipment_type_id, code="crane", title="Crane", synonyms=[])
            session.add(eq_type)
            await session.flush()

            rule = MethodologyRule(
                id=rule_id,
                site_id=site_id,
                stage_id=stage_id,
                is_verifiable=True,
                unverifiable_reason=None,
            )
            session.add(rule)
            await session.flush()

            equipment_set = EquipmentSet(id=equipment_set_id, rule_id=rule_id, position=1)
            session.add(equipment_set)
            await session.flush()

            requirement = EquipmentRequirement(
                id=uuid.uuid4(),
                set_id=equipment_set_id,
                equipment_type_id=equipment_type_id,
                min_count=1,
                obligation=Obligation.NORMATIVE.value,
                gesn_code="01.001",
            )
            session.add(requirement)

            observation = Observation(
                id=uuid.uuid4(),
                site_id=site_id,
                observed_on=obs_date,
                photo_count=1,
                observability="high",
            )
            session.add(observation)
            await session.flush()

            observed_eq = ObservedEquipment(
                id=uuid.uuid4(),
                observation_id=observation.id,
                equipment_type_id=equipment_type_id,
                count_min=1,
                activity="works",
                confidence="high",
            )
            session.add(observed_eq)
            await session.commit()

        engine_config = EngineConfig(
            tolerance_days=3,
            stale_data_days=7,
            no_progress_window_days=5,
            min_confirming_observations=1,
        )

        # Явно передаём as_of_config=None — дефолт (AsOfMode.TODAY) не должен
        # регрессировать по сравнению с поведением до LCT-14.
        async with container() as request_container:
            coordinator = await create_coordinator(container, engine_config, as_of_config=None)
            await coordinator.recompute_site(site_id)

        async with container() as request_container:
            repo = StageStatusRepository(await request_container.get(AsyncSession))
            status = await repo.get_by_stage(stage_id)
            assert status is not None
            assert status.status == StageStatusValue.ON_TRACK.value
            assert status.delay_days is None

            dev_repo = DeviationRepository(await request_container.get(AsyncSession))
            deviations = await dev_repo.list_by_site(site_id)
            assert not any(d.type == DeviationType.STALE_DATA.value for d in deviations)


class TestLiveStatusRecalculator:
    """Тесты LiveStatusRecalculator."""

    @pytest.mark.asyncio
    async def test_recalculate_swallows_exception(self, container, caplog) -> None:
        """recalculate swallows coordinator exception и логирует её."""
        user = await seed_user(container)
        site_id = uuid.uuid4()

        # Создаём сайт без графика
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            site = Site(id=site_id, name="Test Site", owner_id=user.id)
            session.add(site)
            await session.commit()

        # Создаём coordinator с mocked exception
        class BrokenCoordinator:
            async def recompute_site(self, site_id):
                raise ValueError("Test error")

        recalculator = LiveStatusRecalculator(BrokenCoordinator())

        # Вызываем recalculate и проверяем, что исключение поглощается
        with caplog.at_level(logging.ERROR):
            await recalculator.recalculate(site_id)

        # Проверяем, что логирована ошибка
        assert len(caplog.records) > 0
        assert "Assessment recompute failed" in caplog.text


# Import DetectorClient for the test
