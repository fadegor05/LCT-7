"""Тесты для репозиториев assessment домена."""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assessment.models import (
    Deviation,
    DeviationEvidence,
    StageStatus,
    StatusBasis,
)
from app.domains.assessment.repository import (
    DeviationEvidenceRepository,
    DeviationRepository,
    StageStatusRepository,
    StatusBasisRepository,
)
from app.domains.observation.models import Observation
from app.domains.photo.models import Photo
from app.domains.schedule.models import Schedule, ScheduleStage
from app.domains.site.models import Site
from app.domains.user.models import User


async def create_site_with_schedule_and_stage(
    session: AsyncSession, site_id: uuid.UUID, user_id: uuid.UUID, stage_name: str
) -> tuple[uuid.UUID, uuid.UUID]:
    """Создать сайт со стандартной структурой: Schedule + ScheduleStage.

    Returns:
        (schedule_id, stage_id)
    """
    user = User(id=user_id, full_name="Test User")
    session.add(user)

    site = Site(id=site_id, name="Test Site", owner_id=user_id)
    session.add(site)

    schedule_id = uuid.uuid4()
    schedule = Schedule(id=schedule_id, site_id=site_id)
    session.add(schedule)

    stage_id = uuid.uuid4()
    stage = ScheduleStage(
        id=stage_id,
        schedule_id=schedule_id,
        name=stage_name,
        position=1,
        planned_start=date(2025, 1, 1),
        planned_end=date(2025, 1, 31),
    )
    session.add(stage)

    await session.flush()
    return schedule_id, stage_id


async def create_observation_and_photo(
    session: AsyncSession, site_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    """Создать наблюдение и фотографию для тестов доказательств.

    Returns:
        (observation_id, photo_id)
    """
    obs_id = uuid.uuid4()
    observation = Observation(
        id=obs_id,
        site_id=site_id,
        observed_on=date(2025, 1, 15),
        photo_count=1,
        observability="high",
        observability_notes=None,
        recomputed_at=datetime.now(UTC),
    )
    session.add(observation)

    photo_id = uuid.uuid4()
    photo = Photo(
        id=photo_id,
        site_id=site_id,
        storage_key="test/photo.jpg",
        original_name="photo.jpg",
        width=800,
        height=600,
        uploaded_at=datetime.now(UTC),
    )
    session.add(photo)

    await session.flush()
    return obs_id, photo_id


class TestStageStatusRepository:
    """Тесты StageStatusRepository."""

    @pytest.mark.asyncio
    async def test_get_by_stage_returns_status(self, container) -> None:
        """get_by_stage() возвращает статус по stage_id."""
        user_id = uuid.uuid4()
        site_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            _, stage_id = await create_site_with_schedule_and_stage(
                session, site_id, user_id, "Foundation"
            )

            # Добавляем статус
            status_id = uuid.uuid4()
            status = StageStatus(
                id=status_id,
                stage_id=stage_id,
                status="on_track",
                delay_days=0,
                confidence="high",
                confidence_reason="All observations align",
                computed_at=datetime.now(UTC),
            )
            session.add(status)
            await session.commit()

        # Читаем обратно
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = StageStatusRepository(session)
            result = await repo.get_by_stage(stage_id)

        assert result is not None
        assert result.id == status_id
        assert result.stage_id == stage_id
        assert result.status == "on_track"
        assert result.delay_days == 0
        assert result.confidence == "high"

    @pytest.mark.asyncio
    async def test_get_by_stage_returns_none_for_nonexistent_stage(self, container) -> None:
        """get_by_stage() возвращает None для несуществующего этапа."""
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = StageStatusRepository(session)
            result = await repo.get_by_stage(uuid.uuid4())

        assert result is None

    @pytest.mark.asyncio
    async def test_list_by_site_returns_statuses_ordered_by_position(self, container) -> None:
        """list_by_site() возвращает статусы, упорядочены по position этапа."""
        user_id = uuid.uuid4()
        site_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            # Создаём сайт с графиком
            user = User(id=user_id, full_name="Test User")
            session.add(user)
            site = Site(id=site_id, name="Test Site", owner_id=user_id)
            session.add(site)

            schedule_id = uuid.uuid4()
            schedule = Schedule(id=schedule_id, site_id=site_id)
            session.add(schedule)

            # Создаём три этапа с разными position
            stages_and_statuses = []
            for pos in [1, 3, 2]:  # Добавляем в неупорядоченном порядке
                stage_id = uuid.uuid4()
                stage = ScheduleStage(
                    id=stage_id,
                    schedule_id=schedule_id,
                    name=f"Stage {pos}",
                    position=pos,
                )
                session.add(stage)

                status_id = uuid.uuid4()
                status = StageStatus(
                    id=status_id,
                    stage_id=stage_id,
                    status="on_track",
                    confidence="high",
                    computed_at=datetime.now(UTC),
                )
                session.add(status)
                stages_and_statuses.append((stage_id, pos))

            await session.commit()

        # Читаем обратно и проверяем порядок
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = StageStatusRepository(session)
            results = await repo.list_by_site(site_id)

        assert len(results) == 3
        actual_stage_ids = []
        for result in results:
            assert result.stage_id in [s for s, _ in stages_and_statuses]
            actual_stage_ids.append(result.stage_id)

        # Проверяем, что они упорядочены по position (восходящий)
        # Найти соответствие между stage_id и position
        stage_to_pos = {s: p for s, p in stages_and_statuses}
        actual_positions = [stage_to_pos[sid] for sid in actual_stage_ids]
        assert actual_positions == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_list_by_site_excludes_other_sites(self, container) -> None:
        """list_by_site() исключает статусы из других сайтов."""
        user_id = uuid.uuid4()
        site1_id = uuid.uuid4()
        site2_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            # Создаём двух пользователей и два сайта
            user = User(id=user_id, full_name="Test User")
            session.add(user)

            site1 = Site(id=site1_id, name="Site 1", owner_id=user_id)
            session.add(site1)

            site2 = Site(id=site2_id, name="Site 2", owner_id=user_id)
            session.add(site2)

            # Графики для обоих сайтов
            sched1_id = uuid.uuid4()
            sched1 = Schedule(id=sched1_id, site_id=site1_id)
            session.add(sched1)

            sched2_id = uuid.uuid4()
            sched2 = Schedule(id=sched2_id, site_id=site2_id)
            session.add(sched2)

            # Этапы и статусы для обоих сайтов
            stage1_id = uuid.uuid4()
            stage1 = ScheduleStage(
                id=stage1_id,
                schedule_id=sched1_id,
                name="Stage 1",
                position=1,
            )
            session.add(stage1)

            stage2_id = uuid.uuid4()
            stage2 = ScheduleStage(
                id=stage2_id,
                schedule_id=sched2_id,
                name="Stage 2",
                position=1,
            )
            session.add(stage2)

            status1 = StageStatus(
                id=uuid.uuid4(),
                stage_id=stage1_id,
                status="on_track",
                confidence="high",
                computed_at=datetime.now(UTC),
            )
            session.add(status1)

            status2 = StageStatus(
                id=uuid.uuid4(),
                stage_id=stage2_id,
                status="behind",
                confidence="medium",
                computed_at=datetime.now(UTC),
            )
            session.add(status2)

            await session.commit()

        # Читаем для site1
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = StageStatusRepository(session)
            results = await repo.list_by_site(site1_id)

        assert len(results) == 1
        assert results[0].stage_id == stage1_id

    @pytest.mark.asyncio
    async def test_delete_missing_removes_specified_statuses(self, container) -> None:
        """delete_missing() удаляет статусы, не в списке keep_stage_ids."""
        user_id = uuid.uuid4()
        site_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            schedule_id, _ = await create_site_with_schedule_and_stage(
                session, site_id, user_id, "Foundation"
            )

            # Создаём три этапа и три статуса
            stage_ids = []
            status_ids = []
            for i in range(3):
                stage_id = uuid.uuid4()
                stage = ScheduleStage(
                    id=stage_id,
                    schedule_id=schedule_id,
                    name=f"Stage {i}",
                    position=i,
                )
                session.add(stage)
                stage_ids.append(stage_id)

                status_id = uuid.uuid4()
                status = StageStatus(
                    id=status_id,
                    stage_id=stage_id,
                    status="on_track",
                    confidence="high",
                    computed_at=datetime.now(UTC),
                )
                session.add(status)
                status_ids.append(status_id)

            await session.commit()

        # Удаляем, оставляя только первый и третий
        keep_stage_ids = [stage_ids[0], stage_ids[2]]
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = StageStatusRepository(session)
            await repo.delete_missing(site_id, keep_stage_ids)
            await session.commit()

        # Проверяем результат
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = StageStatusRepository(session)
            results = await repo.list_by_site(site_id)

        assert len(results) == 2
        remaining_stage_ids = {r.stage_id for r in results}
        assert remaining_stage_ids == set(keep_stage_ids)


class TestDeviationRepository:
    """Тесты DeviationRepository."""

    @pytest.mark.asyncio
    async def test_list_by_site_orders_by_severity_then_created_at(self, container) -> None:
        """list_by_site() упорядочивает по severity (critical/attention), потом по created_at."""
        user_id = uuid.uuid4()
        site_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            user = User(id=user_id, full_name="Test User")
            session.add(user)
            site = Site(id=site_id, name="Test Site", owner_id=user_id)
            session.add(site)

            # Создаём отклонения с разными severity и created_at
            # Добавляем в неупорядоченном порядке для проверки сортировки
            deviations_data = [
                ("attention", datetime(2025, 1, 3, tzinfo=UTC)),  # attention, latest
                ("critical", datetime(2025, 1, 1, tzinfo=UTC)),  # critical, oldest
                ("critical", datetime(2025, 1, 2, tzinfo=UTC)),  # critical, middle
                ("attention", datetime(2025, 1, 1, tzinfo=UTC)),  # attention, oldest
            ]

            for severity, created_at in deviations_data:
                dev = Deviation(
                    id=uuid.uuid4(),
                    site_id=site_id,
                    stage_id=None,
                    type="missing_equipment",
                    is_hypothesis=False,
                    severity=severity,
                    confidence="high",
                    period_start=date(2025, 1, 1),
                    period_end=date(2025, 1, 31),
                    expected="Equipment X",
                    observed="Nothing",
                    limits_text="Must be present",
                    created_at=created_at,
                )
                session.add(dev)

            await session.commit()

        # Читаем и проверяем порядок
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = DeviationRepository(session)
            results = await repo.list_by_site(site_id)

        assert len(results) == 4
        # Ожидаемый порядок:
        # 1. critical, 2025-01-02 (позже)
        # 2. critical, 2025-01-01 (раньше)
        # 3. attention, 2025-01-03 (позже)
        # 4. attention, 2025-01-01 (раньше)
        expected_order = [
            ("critical", datetime(2025, 1, 2, tzinfo=UTC)),
            ("critical", datetime(2025, 1, 1, tzinfo=UTC)),
            ("attention", datetime(2025, 1, 3, tzinfo=UTC)),
            ("attention", datetime(2025, 1, 1, tzinfo=UTC)),
        ]

        for actual, (expected_sev, expected_time) in zip(results, expected_order, strict=True):
            assert actual.severity == expected_sev
            # SQLite strips timezone info, so compare without it
            assert actual.created_at.replace(tzinfo=None) == expected_time.replace(tzinfo=None)

    @pytest.mark.asyncio
    async def test_delete_by_site_removes_deviations_and_evidence(self, container) -> None:
        """delete_by_site() удаляет отклонения и их доказательства через CASCADE."""
        user_id = uuid.uuid4()
        site_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            user = User(id=user_id, full_name="Test User")
            session.add(user)
            site = Site(id=site_id, name="Test Site", owner_id=user_id)
            session.add(site)

            # Создаём фотографию
            photo_id = uuid.uuid4()
            photo = Photo(
                id=photo_id,
                site_id=site_id,
                storage_key="test/test.jpg",
                original_name="test.jpg",
                width=800,
                height=600,
                uploaded_at=datetime.now(UTC),
            )
            session.add(photo)

            # Создаём два отклонения с доказательствами
            dev1_id = uuid.uuid4()
            dev1 = Deviation(
                id=dev1_id,
                site_id=site_id,
                stage_id=None,
                type="missing_equipment",
                is_hypothesis=False,
                severity="critical",
                confidence="high",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 1, 31),
                expected="Equipment X",
                observed="Nothing",
                limits_text="Must be present",
            )
            session.add(dev1)

            dev2_id = uuid.uuid4()
            dev2 = Deviation(
                id=dev2_id,
                site_id=site_id,
                stage_id=None,
                type="stale_data",
                is_hypothesis=True,
                severity="attention",
                confidence="medium",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 1, 31),
                expected="Recent data",
                observed="Old data",
                limits_text="Within 7 days",
            )
            session.add(dev2)

            await session.flush()

            # Добавляем доказательства
            evidence1 = DeviationEvidence(
                id=uuid.uuid4(),
                deviation_id=dev1_id,
                photo_id=photo_id,
                detection_id=None,
            )
            session.add(evidence1)

            evidence2 = DeviationEvidence(
                id=uuid.uuid4(),
                deviation_id=dev2_id,
                photo_id=photo_id,
                detection_id=None,
            )
            session.add(evidence2)

            await session.commit()

        # Подтверждаем, что всё создалось
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            dev_repo = DeviationRepository(session)
            dev_count = len(await dev_repo.list_by_site(site_id))
            evidence_repo = DeviationEvidenceRepository(session)
            ev_count = len(await evidence_repo.list_by_deviation(dev1_id))

        assert dev_count == 2
        assert ev_count == 1

        # Удаляем все отклонения сайта
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = DeviationRepository(session)
            await repo.delete_by_site(site_id)
            await session.commit()

        # Проверяем, что всё удалено (включая доказательства)
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            dev_repo = DeviationRepository(session)
            dev_count = len(await dev_repo.list_by_site(site_id))
            # Проверяем доказательства напрямую через запрос
            from sqlalchemy import select

            evidence_result = await session.execute(select(DeviationEvidence))
            all_evidence = evidence_result.scalars().all()

        assert dev_count == 0
        assert len(all_evidence) == 0


class TestDeviationEvidenceRepository:
    """Тесты DeviationEvidenceRepository."""

    @pytest.mark.asyncio
    async def test_add_many_and_list_by_deviation(self, container) -> None:
        """add_many() добавляет доказательства, list_by_deviation() возвращает их."""
        user_id = uuid.uuid4()
        site_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            user = User(id=user_id, full_name="Test User")
            session.add(user)
            site = Site(id=site_id, name="Test Site", owner_id=user_id)
            session.add(site)

            # Создаём отклонение и три фотографии
            dev_id = uuid.uuid4()
            dev = Deviation(
                id=dev_id,
                site_id=site_id,
                stage_id=None,
                type="missing_equipment",
                is_hypothesis=False,
                severity="critical",
                confidence="high",
                period_start=date(2025, 1, 1),
                period_end=date(2025, 1, 31),
                expected="Equipment X",
                observed="Nothing",
                limits_text="Must be present",
            )
            session.add(dev)

            photo_ids = []
            for i in range(3):
                photo_id = uuid.uuid4()
                photo = Photo(
                    id=photo_id,
                    site_id=site_id,
                    storage_key=f"test/test_{i}.jpg",
                    original_name=f"test_{i}.jpg",
                    width=800,
                    height=600,
                    uploaded_at=datetime.now(UTC),
                )
                session.add(photo)
                photo_ids.append(photo_id)

            await session.flush()

            # Добавляем доказательства через add_many
            evidence_rows = [
                DeviationEvidence(
                    id=uuid.uuid4(),
                    deviation_id=dev_id,
                    photo_id=photo_ids[0],
                    detection_id=None,
                ),
                DeviationEvidence(
                    id=uuid.uuid4(),
                    deviation_id=dev_id,
                    photo_id=photo_ids[1],
                    detection_id=None,
                ),
                DeviationEvidence(
                    id=uuid.uuid4(),
                    deviation_id=dev_id,
                    photo_id=photo_ids[2],
                    detection_id=None,
                ),
            ]

            repo = DeviationEvidenceRepository(session)
            await repo.add_many(evidence_rows)
            await session.commit()

        # Читаем обратно
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = DeviationEvidenceRepository(session)
            results = await repo.list_by_deviation(dev_id)

        assert len(results) == 3
        result_photo_ids = {r.photo_id for r in results}
        assert result_photo_ids == set(photo_ids)


class TestStatusBasisRepository:
    """Тесты StatusBasisRepository."""

    @pytest.mark.asyncio
    async def test_add_many_list_and_delete_by_status(self, container) -> None:
        """add_many() добавляет основания, list_by_status() и delete_by_status() работают."""
        user_id = uuid.uuid4()
        site_id = uuid.uuid4()

        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            user = User(id=user_id, full_name="Test User")
            session.add(user)
            site = Site(id=site_id, name="Test Site", owner_id=user_id)
            session.add(site)

            # Создаём статус этапа
            schedule_id = uuid.uuid4()
            schedule = Schedule(id=schedule_id, site_id=site_id)
            session.add(schedule)

            stage_id = uuid.uuid4()
            stage = ScheduleStage(
                id=stage_id,
                schedule_id=schedule_id,
                name="Test Stage",
                position=1,
            )
            session.add(stage)

            status_id = uuid.uuid4()
            status = StageStatus(
                id=status_id,
                stage_id=stage_id,
                status="on_track",
                confidence="high",
                computed_at=datetime.now(UTC),
            )
            session.add(status)

            # Создаём три наблюдения
            obs_ids = []
            for i in range(3):
                obs_id = uuid.uuid4()
                obs = Observation(
                    id=obs_id,
                    site_id=site_id,
                    observed_on=date(2025, 1, i + 1),
                    photo_count=1,
                    observability="high",
                    observability_notes=None,
                    recomputed_at=datetime.now(UTC),
                )
                session.add(obs)
                obs_ids.append(obs_id)

            await session.flush()

            # Добавляем основания через add_many
            basis_rows = [
                StatusBasis(
                    id=uuid.uuid4(),
                    status_id=status_id,
                    observation_id=obs_ids[0],
                ),
                StatusBasis(
                    id=uuid.uuid4(),
                    status_id=status_id,
                    observation_id=obs_ids[1],
                ),
                StatusBasis(
                    id=uuid.uuid4(),
                    status_id=status_id,
                    observation_id=obs_ids[2],
                ),
            ]

            repo = StatusBasisRepository(session)
            await repo.add_many(basis_rows)
            await session.commit()

        # Читаем и проверяем
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = StatusBasisRepository(session)
            results = await repo.list_by_status(status_id)

        assert len(results) == 3
        result_obs_ids = {r.observation_id for r in results}
        assert result_obs_ids == set(obs_ids)

        # Удаляем основания для статуса
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = StatusBasisRepository(session)
            await repo.delete_by_status(status_id)
            await session.commit()

        # Проверяем, что всё удалено
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            repo = StatusBasisRepository(session)
            results = await repo.list_by_status(status_id)

        assert len(results) == 0
