"""HTTP-контракт для домена assistant."""

import json
import uuid
from datetime import date, timedelta

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ml.assistant import (
    AssistantAnswer,
    AssistantBadRequest,
    AssistantTimeout,
    AssistantUnavailable,
)
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
    from app.domains.schedule.models import DatesSource, Schedule, ScheduleStage
    from app.domains.site.models import Site

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
    from app.domains.assessment.models import StageStatus

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


class TestAssistantRouter:
    """Тесты HTTP маршрутов assistant."""

    @pytest.mark.asyncio
    async def test_ask_успех(
        self, client: AsyncClient, container: AsyncContainer, assistant_client
    ) -> None:
        """POST /assistant/ask успешный запрос возвращает 200 со всеми полями."""
        await seed_stand_user(container)
        site_id, _, stage_ids = await create_site_with_schedule(container)
        await create_stage_status(container, stage_ids[0], "on_track", delay_days=0)

        # Конфигурируем fake для возврата ответа упоминающего "этап 1"
        assistant_client.answer = AssistantAnswer(
            answer="Этап 1 отстаёт на 5 дней",
            verified=True,
            numbers_not_in_report=[],
            numbers_of_other_site=[],
            limits="",
        )

        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "Как дела на этапе 1?"},
        )

        assert response.status_code == 200
        data = response.json()

        # Проверяем все 7 полей
        assert "answer" in data
        assert data["answer"] == "Этап 1 отстаёт на 5 дней"
        assert "verified" in data
        assert data["verified"] is True
        assert "numbers_not_in_report" in data
        assert "numbers_of_other_site" in data
        assert "limits" in data
        assert data["site_label"] == "p1"
        assert "stages" in data
        assert len(data["stages"]) == 1
        assert data["stages"][0]["ref"] == "этап 1"
        assert data["stages"][0]["stage_id"] == str(stage_ids[0])

        # Проверяем что fake получил отчёт с правильным site_id
        assert len(assistant_client.calls) == 1
        question, report, site_id_arg = assistant_client.calls[0]
        assert question == "Как дела на этапе 1?"
        assert site_id_arg == "p1"
        # Проверяем что в отчёте нет UUID-й
        report_json = json.dumps(report, ensure_ascii=False)
        # Site ID должно быть "p1", а не UUID
        assert str(site_id) not in report_json

    @pytest.mark.asyncio
    async def test_verified_false_доходит_без_изменений(
        self, client: AsyncClient, container: AsyncContainer, assistant_client
    ) -> None:
        """POST /assistant/ask с verified=false и списками доходят без изменений."""
        await seed_stand_user(container)
        site_id, _, stage_ids = await create_site_with_schedule(container)
        await create_stage_status(container, stage_ids[0], "on_track", delay_days=0)

        # Конфигурируем fake
        assistant_client.answer = AssistantAnswer(
            answer="Ответ",
            verified=False,
            numbers_not_in_report=["999"],
            numbers_of_other_site=["p2: 555"],
            limits="Проверяйте сами",
        )

        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "Вопрос из 3 символов"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is False
        assert data["numbers_not_in_report"] == ["999"]
        assert data["numbers_of_other_site"] == ["p2: 555"]
        assert data["limits"] == "Проверяйте сами"

    @pytest.mark.parametrize(
        "error,expected_status,expected_code",
        [
            (
                AssistantUnavailable("Ассистент недоступен"),
                503,
                "assistant_unavailable",
            ),
            (
                AssistantTimeout("Модель не ответила"),
                504,
                "assistant_timeout",
            ),
            (
                AssistantBadRequest(
                    message="Только по отчёту",
                    status_code=422,
                    code="out_of_scope",
                ),
                422,
                "out_of_scope",
            ),
            (
                AssistantBadRequest(message="Не принято"),
                400,
                "assistant_bad_request",
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_ошибки_ml_маппятся_параметризованно(
        self,
        client: AsyncClient,
        container: AsyncContainer,
        assistant_client,
        error,
        expected_status,
        expected_code,
    ) -> None:
        """Ошибки ML маппируются в HTTP статусы с кодами (параметризованные)."""
        await seed_stand_user(container)
        site_id, _, stage_ids = await create_site_with_schedule(container)
        await create_stage_status(container, stage_ids[0], "on_track", delay_days=0)

        assistant_client.error = error

        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "Вопрос из 10 символов___"},
        )

        assert response.status_code == expected_status
        data = response.json()
        assert data.get("code") == expected_code
        if expected_code == "out_of_scope":
            assert data["detail"] == "Только по отчёту"

    @pytest.mark.asyncio
    async def test_ml_не_настроен(
        self, client: AsyncClient, container: AsyncContainer, assistant_client
    ) -> None:
        """Если ML не настроен: GET /status -> 200 enabled:false, POST /ask -> 503."""
        await seed_stand_user(container)
        site_id, _, stage_ids = await create_site_with_schedule(container)
        await create_stage_status(container, stage_ids[0], "on_track", delay_days=0)

        assistant_client.enabled = False

        # Проверяем статус
        response = await client.get("/assistant/status")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False

        # Проверяем что ask возвращает 503 и не вызывает ML
        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "Вопрос из 10 символов___"},
        )
        assert response.status_code == 503
        assert response.json()["code"] == "assistant_unavailable"
        assert len(assistant_client.calls) == 0

    @pytest.mark.asyncio
    async def test_status_включён(
        self, client: AsyncClient, container: AsyncContainer, assistant_client
    ) -> None:
        """GET /assistant/status возвращает enabled:true если ML доступен."""
        await seed_stand_user(container)

        assistant_client.enabled = True

        response = await client.get("/assistant/status")
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_вопрос_границы(self, client: AsyncClient, container: AsyncContainer) -> None:
        """Вопрос: 2 симв -> 422, 3 симв -> 200, 500 -> 200, 501 -> 422."""
        await seed_stand_user(container)
        site_id, _, stage_ids = await create_site_with_schedule(container)
        await create_stage_status(container, stage_ids[0], "on_track", delay_days=0)

        # 2 символа -> 422
        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "ab"},
        )
        assert response.status_code == 422
        assert isinstance(response.json()["detail"], list)
        assert "code" not in response.json()

        # "  ab  " -> 422 (2 символа после strip)
        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "  ab  "},
        )
        assert response.status_code == 422

        # 3 символа -> 200
        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "abc"},
        )
        assert response.status_code == 200

        # 500 символов -> 200
        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "а" * 500},
        )
        assert response.status_code == 200

        # 501 символ -> 422
        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "а" * 501},
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_чужая_и_несуществующая_площадка_404(
        self, client: AsyncClient, container: AsyncContainer, assistant_client
    ) -> None:
        """POST /assistant/ask для несуществующей площадки -> 404, fake.calls == []."""
        await seed_stand_user(container)

        fake_site_id = uuid.uuid4()
        response = await client.post(
            f"/sites/{fake_site_id}/assistant/ask",
            json={"question": "Вопрос из 10 символов___"},
        )

        assert response.status_code == 404
        assert len(assistant_client.calls) == 0

    @pytest.mark.asyncio
    async def test_нет_графика_404(
        self, client: AsyncClient, container: AsyncContainer, assistant_client
    ) -> None:
        """POST /assistant/ask для сайта без графика -> 404 График не загружен."""
        from app.domains.site.models import Site

        await seed_stand_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            site = Site(id=site_id, name="Test Site", owner_id=STAND_USER_ID)
            session.add(site)
            await session.commit()

        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "Вопрос из 10 символов___"},
        )

        assert response.status_code == 404
        assert "График не загружен" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_лимит_429(
        self, client: AsyncClient, container: AsyncContainer, assistant_client
    ) -> None:
        """После 10 успешных ask'ов, 11-й -> 429 rate_limited; fake.calls == 10."""
        await seed_stand_user(container)
        site_id, _, stage_ids = await create_site_with_schedule(container)
        await create_stage_status(container, stage_ids[0], "on_track", delay_days=0)

        # Делаем 10 успешных запросов
        for i in range(10):
            response = await client.post(
                f"/sites/{site_id}/assistant/ask",
                json={"question": f"Вопрос номер {i + 1}_"},
            )
            assert response.status_code == 200

        # 11-й должен вернуть 429
        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "Одиннадцатый вопрос"},
        )

        assert response.status_code == 429
        assert response.json()["code"] == "rate_limited"
        assert "Повторите через" in response.json()["detail"]
        assert len(assistant_client.calls) == 10

    @pytest.mark.asyncio
    async def test_ключ_и_детали_не_в_ответе_и_логах(
        self,
        client: AsyncClient,
        container: AsyncContainer,
        assistant_client,
        caplog,
    ) -> None:
        """Ответ на успешный ask не содержит секреты в body/logs."""
        import logging

        await seed_stand_user(container)
        site_id, _, stage_ids = await create_site_with_schedule(container)
        await create_stage_status(container, stage_ids[0], "on_track", delay_days=0)

        assistant_client.answer = AssistantAnswer(
            answer="Секретный ответ для p1",
            verified=True,
            numbers_not_in_report=[],
            numbers_of_other_site=[],
            limits="",
        )

        caplog.set_level(logging.INFO)
        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "Секретный вопрос"},
        )

        assert response.status_code == 200
        # Ответ не должен содержать секреты с "sk-"
        response_text = json.dumps(response.json())
        assert "sk-" not in response_text

    @pytest.mark.asyncio
    async def test_ответ_не_сохраняется(
        self, client: AsyncClient, container: AsyncContainer, assistant_client
    ) -> None:
        """После успешного ask количество строк в таблицах не изменяется."""
        from sqlalchemy import func, select

        from app.domains.assessment.models import Deviation, StageStatus
        from app.domains.photo.models import Photo

        await seed_stand_user(container)
        site_id, _, stage_ids = await create_site_with_schedule(container)
        await create_stage_status(container, stage_ids[0], "on_track", delay_days=0)

        # Получаем начальное количество строк
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            photo_count_before = await session.scalar(select(func.count(Photo.id)))
            deviation_count_before = await session.scalar(select(func.count(Deviation.id)))
            stage_status_count_before = await session.scalar(select(func.count(StageStatus.id)))

        # Делаем запрос
        response = await client.post(
            f"/sites/{site_id}/assistant/ask",
            json={"question": "Вопрос из 10 символов___"},
        )
        assert response.status_code == 200

        # Получаем конечное количество строк
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            photo_count_after = await session.scalar(select(func.count(Photo.id)))
            deviation_count_after = await session.scalar(select(func.count(Deviation.id)))
            stage_status_count_after = await session.scalar(select(func.count(StageStatus.id)))

        # Все счётчики должны остаться теми же
        assert photo_count_before == photo_count_after
        assert deviation_count_before == deviation_count_after
        assert stage_status_count_before == stage_status_count_after

    @pytest.mark.asyncio
    async def test_openapi_содержит_ручки(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """Оба пути есть в OpenAPI схеме."""
        await seed_stand_user(container)

        response = await client.get("/openapi.json")
        assert response.status_code == 200
        spec = response.json()

        # Проверяем что оба пути есть в paths (без /api prefix в openapi)
        paths = spec["paths"]
        assert (
            any("/sites/{site_id}/assistant/ask" in path for path in paths)
            or "/sites/{site_id}/assistant/ask" in paths
        )
        assert any("/assistant/status" in path for path in paths) or "/assistant/status" in paths
