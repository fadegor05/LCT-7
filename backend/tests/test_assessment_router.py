"""HTTP-контракт для домена assessment."""

import uuid
from datetime import date, timedelta

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assessment.models import Deviation, DeviationEvidence, Severity, StageStatus
from app.domains.schedule.models import DatesSource, Schedule, ScheduleStage
from app.domains.site.models import Site
from app.domains.user.service import STAND_USER_ID, UserService


async def seed_stand_user(container: AsyncContainer) -> None:
    """Создать стендового пользователя."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


async def create_site_with_schedule(
    container: AsyncContainer, site_id: uuid.UUID | None = None
) -> tuple[uuid.UUID, uuid.UUID, list[uuid.UUID]]:
    """Создаёт сайт и график с несколькими этапами.

    Returns:
        (site_id, schedule_id, [stage_id_1, stage_id_2])
    """
    if site_id is None:
        site_id = uuid.uuid4()

    schedule_id = uuid.uuid4()
    stage_id_1 = uuid.uuid4()
    stage_id_2 = uuid.uuid4()

    today = date.today()
    # Первый этап: уже начался (будет иметь StageStatus)
    start_1 = today - timedelta(days=2)
    end_1 = today + timedelta(days=3)
    # Второй этап: не начался (не будет иметь StageStatus)
    start_2 = today + timedelta(days=10)
    end_2 = today + timedelta(days=15)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        site = Site(id=site_id, name="Test Site", owner_id=STAND_USER_ID)
        session.add(site)
        await session.flush()

        schedule = Schedule(id=schedule_id, site_id=site_id)
        session.add(schedule)
        await session.flush()

        stage_1 = ScheduleStage(
            id=stage_id_1,
            schedule_id=schedule_id,
            name="Foundation",
            position=1,
            planned_start=start_1,
            planned_end=end_1,
            dates_source=DatesSource.FILE.value,
        )
        session.add(stage_1)

        stage_2 = ScheduleStage(
            id=stage_id_2,
            schedule_id=schedule_id,
            name="Framing",
            position=2,
            planned_start=start_2,
            planned_end=end_2,
            dates_source=DatesSource.FILE.value,
        )
        session.add(stage_2)

        await session.commit()

    return site_id, schedule_id, [stage_id_1, stage_id_2]


async def create_stage_status(
    container: AsyncContainer, stage_id: uuid.UUID, status: str, delay_days: int | None = None
) -> None:
    """Создаёт StageStatus для этапа."""
    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        stage_status = StageStatus(
            id=uuid.uuid4(),
            stage_id=stage_id,
            status=status,
            delay_days=delay_days,
            confidence="high",
            confidence_reason="Test reason",
        )
        session.add(stage_status)
        await session.commit()


async def create_deviation(
    container: AsyncContainer,
    site_id: uuid.UUID,
    severity: str,
    deviation_type: str = "stale_data",
    is_hypothesis: bool = False,
) -> uuid.UUID:
    """Создаёт отклонение для сайта."""
    deviation_id = uuid.uuid4()
    today = date.today()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        deviation = Deviation(
            id=deviation_id,
            site_id=site_id,
            stage_id=None,
            type=deviation_type,
            is_hypothesis=is_hypothesis,
            severity=severity,
            confidence="high",
            period_start=today,
            period_end=today,
            expected="Equipment present",
            observed="No equipment",
            limits_text="Tolerance: 1 day",
            rule_id=None,
        )
        session.add(deviation)
        await session.commit()

    return deviation_id


async def create_deviation_evidence(
    container: AsyncContainer, deviation_id: uuid.UUID, photo_id: uuid.UUID | None = None
) -> None:
    """Создаёт доказательство отклонения."""
    if photo_id is None:
        photo_id = uuid.uuid4()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        evidence = DeviationEvidence(
            id=uuid.uuid4(),
            deviation_id=deviation_id,
            photo_id=photo_id,
            detection_id=None,
        )
        session.add(evidence)
        await session.commit()


class TestAssessmentRouter:
    """Тесты HTTP маршрутов assessment."""

    @pytest.mark.asyncio
    async def test_list_stage_statuses_nonexistent_site_with_404(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/stages для несуществующего сайта возвращает 404."""
        await seed_stand_user(container)

        fake_site_id = uuid.uuid4()
        response = await client.get(f"/sites/{fake_site_id}/assessment/stages")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_stage_statuses_no_schedule_with_404(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/stages для сайта без графика возвращает 404."""
        await seed_stand_user(container)

        # Создаём сайт без графика
        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            site = Site(id=site_id, name="Test Site", owner_id=STAND_USER_ID)
            session.add(site)
            await session.commit()

        response = await client.get(f"/sites/{site_id}/assessment/stages")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_stage_statuses_with_stages_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/stages возвращает 200 со всеми этапами, включая не начавшиеся."""
        await seed_stand_user(container)

        site_id, schedule_id, stage_ids = await create_site_with_schedule(container)

        # Создаём StageStatus только для первого этапа (второй не начался)
        await create_stage_status(container, stage_ids[0], "on_track", delay_days=0)

        response = await client.get(f"/sites/{site_id}/assessment/stages")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2

        # Первый этап должен иметь статус
        assert data[0]["stage_id"] == str(stage_ids[0])
        assert data[0]["stage_name"] == "Foundation"
        assert data[0]["position"] == 1
        assert data[0]["status"] == "on_track"
        assert data[0]["delay_days"] == 0

        # Второй этап не должен иметь статус (нет строки в таблице)
        assert data[1]["stage_id"] == str(stage_ids[1])
        assert data[1]["stage_name"] == "Framing"
        assert data[1]["position"] == 2
        assert data[1]["status"] is None
        assert data[1]["delay_days"] is None

    @pytest.mark.asyncio
    async def test_list_deviations_nonexistent_site_with_404(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/deviations для несуществующего сайта возвращает 404."""
        await seed_stand_user(container)

        fake_site_id = uuid.uuid4()
        response = await client.get(f"/sites/{fake_site_id}/assessment/deviations")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_list_deviations_empty_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/deviations возвращает 200 и пустой список."""
        await seed_stand_user(container)

        site_id, _, _ = await create_site_with_schedule(container)

        response = await client.get(f"/sites/{site_id}/assessment/deviations")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_list_deviations_sorted_critical_first(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/deviations возвращает деviations отсортированные по severity."""
        await seed_stand_user(container)

        site_id, _, _ = await create_site_with_schedule(container)

        # Создаём отклонения в неправильном порядке
        await create_deviation(container, site_id, Severity.ATTENTION.value)
        await create_deviation(container, site_id, Severity.CRITICAL.value)
        await create_deviation(container, site_id, Severity.CRITICAL.value)
        await create_deviation(container, site_id, Severity.ATTENTION.value)

        response = await client.get(f"/sites/{site_id}/assessment/deviations")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 4

        # Все critical должны быть впереди
        assert all(d["severity"] == "critical" for d in data[:2])
        assert all(d["severity"] == "attention" for d in data[2:])

    @pytest.mark.asyncio
    async def test_get_deviation_nonexistent_site_with_404(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/deviations/{id} для несуществующего сайта возвращает 404."""
        await seed_stand_user(container)

        fake_site_id = uuid.uuid4()
        fake_deviation_id = uuid.uuid4()
        response = await client.get(
            f"/sites/{fake_site_id}/assessment/deviations/{fake_deviation_id}"
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_deviation_nonexistent_deviation_with_404(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/deviations/{id} для несуществующего отклонения возвращает 404."""
        await seed_stand_user(container)

        site_id, _, _ = await create_site_with_schedule(container)
        fake_deviation_id = uuid.uuid4()

        response = await client.get(f"/sites/{site_id}/assessment/deviations/{fake_deviation_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_deviation_with_evidence_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/deviations/{id} возвращает 200 с доказательствами."""
        await seed_stand_user(container)

        site_id, _, _ = await create_site_with_schedule(container)
        dev_id = await create_deviation(container, site_id, Severity.CRITICAL.value)

        # Добавляем два доказательства
        photo_id_1 = uuid.uuid4()
        photo_id_2 = uuid.uuid4()
        await create_deviation_evidence(container, dev_id, photo_id_1)
        await create_deviation_evidence(container, dev_id, photo_id_2)

        response = await client.get(f"/sites/{site_id}/assessment/deviations/{dev_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(dev_id)
        assert data["severity"] == "critical"
        assert "evidence" in data
        assert isinstance(data["evidence"], list)
        assert len(data["evidence"]) == 2
        assert data["evidence"][0]["photo_id"] == str(photo_id_1)
        assert data["evidence"][1]["photo_id"] == str(photo_id_2)

    @pytest.mark.asyncio
    async def test_get_summary_nonexistent_site_with_404(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/summary для несуществующего сайта возвращает 404."""
        await seed_stand_user(container)

        fake_site_id = uuid.uuid4()
        response = await client.get(f"/sites/{fake_site_id}/assessment/summary")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_summary_insufficient_data_no_schedule_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/summary возвращает insufficient_data когда нет графика."""
        await seed_stand_user(container)

        # Создаём сайт без графика
        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            site = Site(id=site_id, name="Test Site", owner_id=STAND_USER_ID)
            session.add(site)
            await session.commit()

        response = await client.get(f"/sites/{site_id}/assessment/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["verdict"] == "insufficient_data"
        assert data["delay_days_min"] is None
        assert data["delay_days_max"] is None
        assert data["critical_count"] == 0
        assert data["attention_count"] == 0

    @pytest.mark.asyncio
    async def test_get_summary_no_deviations_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/summary возвращает no_deviations если нет отклонений."""
        await seed_stand_user(container)

        site_id, _, stage_ids = await create_site_with_schedule(container)

        # Создаём statuses для этапов, но без behind
        await create_stage_status(container, stage_ids[0], "on_track", delay_days=0)
        await create_stage_status(container, stage_ids[1], "ahead", delay_days=-1)

        response = await client.get(f"/sites/{site_id}/assessment/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["verdict"] == "no_deviations"
        assert data["delay_days_min"] is None
        assert data["delay_days_max"] is None
        assert data["critical_count"] == 0
        assert data["attention_count"] == 0

    @pytest.mark.asyncio
    async def test_get_summary_behind_status_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/summary возвращает behind с интервалом дней отставания."""
        await seed_stand_user(container)

        site_id, _, stage_ids = await create_site_with_schedule(container)

        # Создаём statuses: один behind, один ahead
        await create_stage_status(container, stage_ids[0], "behind", delay_days=3)
        await create_stage_status(container, stage_ids[1], "behind", delay_days=5)

        response = await client.get(f"/sites/{site_id}/assessment/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["verdict"] == "behind"
        assert data["delay_days_min"] == 3
        assert data["delay_days_max"] == 5
        assert data["critical_count"] == 0
        assert data["attention_count"] == 0

    @pytest.mark.asyncio
    async def test_get_summary_with_deviations_and_behind_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /assessment/summary возвращает behind и считает отклонения."""
        await seed_stand_user(container)

        site_id, _, stage_ids = await create_site_with_schedule(container)

        # Создаём statuses with behind
        await create_stage_status(container, stage_ids[0], "behind", delay_days=2)

        # Создаём отклонения
        await create_deviation(container, site_id, Severity.CRITICAL.value)
        await create_deviation(container, site_id, Severity.CRITICAL.value)
        await create_deviation(container, site_id, Severity.ATTENTION.value)

        response = await client.get(f"/sites/{site_id}/assessment/summary")

        assert response.status_code == 200
        data = response.json()
        assert data["verdict"] == "behind"
        assert data["delay_days_min"] == 2
        assert data["delay_days_max"] == 2
        assert data["critical_count"] == 2
        assert data["attention_count"] == 1
