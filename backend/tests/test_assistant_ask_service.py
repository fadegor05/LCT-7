"""AssistantService: оркестрация вопроса с проверками, лимитом и маппингом ошибок."""

import logging
import uuid
from unittest.mock import MagicMock

import pytest

from app.adapters.ml.assistant import (
    AssistantAnswer,
    AssistantBadRequest,
    AssistantTimeout,
    AssistantUnavailable,
)
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.settings import AssistantSettings, Settings
from app.domains.assistant.ask_service import AssistantService, referenced_stages
from app.domains.assistant.report import BuiltReport
from app.domains.assistant.schemas import AskRequest
from app.plugins.exceptions import AppError
from tests.fakes import FakeAssistantClient


class FakeReportService:
    """Stub для AssistantReportService."""

    def __init__(self, report: dict | None = None):
        self.report = report or {
            "meta": {"sites": 1},
            "sites": [{"site_id": "p1", "stages": []}],
        }
        self.stage_ids = {
            1: uuid.uuid4(),
            2: uuid.uuid4(),
            3: uuid.uuid4(),
            4: uuid.uuid4(),
            30: uuid.uuid4(),
        }
        self.calls = []

    async def build(self, site_id: uuid.UUID) -> BuiltReport:
        """Вернуть фиксированный отчёт, записать вызов."""
        self.calls.append(site_id)
        return BuiltReport(report=self.report, stage_ids=self.stage_ids)


class FakeGuard:
    """Stub для SiteAccessGuard."""

    def __init__(self, owner_id: uuid.UUID | None = None, error: Exception | None = None):
        self.owner_id = owner_id or uuid.uuid4()
        self.error = error
        self.calls = []

    async def require(self, site_id: uuid.UUID):
        """Вернуть объект с owner_id или выбросить ошибку."""
        self.calls.append(site_id)
        if self.error:
            raise self.error
        site = MagicMock()
        site.owner_id = self.owner_id
        return site


class FakeClock:
    """Fake часы для управления временем в тестах."""

    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        """Продвинуть время на N секунд."""
        self.now += seconds


# Tests for referenced_stages


def test_referenced_stages_успех_собирает_ссылки_на_этапы() -> None:
    """Успешно парсит этап N и возвращает уникальные ссылки в порядке первого появления."""
    answer = "Этап 3 «Устройство свай» отстаёт. Этапа 3 и этап №4, этап 99."
    stage_ids = {3: uuid.uuid4(), 4: uuid.uuid4()}

    result = referenced_stages(answer, stage_ids)

    assert len(result) == 2
    assert result[0].ref == "этап 3"
    assert result[0].stage_id == stage_ids[3]
    assert result[1].ref == "этап 4"
    assert result[1].stage_id == stage_ids[4]


def test_referenced_stages_регистры_и_дубли() -> None:
    """Парсит разные регистры и убирает дубли."""
    answer = "Этап 3, этапа 3, этап №3, ЭТАП 3 — все одно."
    stage_ids = {3: uuid.uuid4()}

    result = referenced_stages(answer, stage_ids)

    assert len(result) == 1
    assert result[0].ref == "этап 3"


def test_referenced_stages_этап_99_не_в_stage_ids() -> None:
    """Этапы, отсутствующие в stage_ids, не включаются."""
    answer = "Этап 3 и этап 99."
    stage_ids = {3: uuid.uuid4()}

    result = referenced_stages(answer, stage_ids)

    assert len(result) == 1
    assert result[0].ref == "этап 3"


def test_referenced_stages_этап_30_не_читается_как_3() -> None:
    """Этап 30 не парсится как 3."""
    answer = "Этап 30 — это большой, не маленький."
    stage_ids = {3: uuid.uuid4(), 30: uuid.uuid4()}

    result = referenced_stages(answer, stage_ids)

    assert len(result) == 1
    assert result[0].ref == "этап 30"


# Tests for AssistantService


@pytest.mark.asyncio
async def test_успех_собирает_ответ_и_ссылки_на_этапы() -> None:
    """Успешный ask собирает ответ и добавляет ссылки на упомянутые этапы."""
    clock = FakeClock()
    report_service = FakeReportService()
    guard = FakeGuard()
    client = FakeAssistantClient(
        answer=AssistantAnswer(
            answer="Этап 3 «Устройство свай» отстаёт. Этапа 3 и этап №4, этап 99.",
            verified=True,
            numbers_not_in_report=[],
            numbers_of_other_site=[],
            limits="",
        ),
        enabled=True,
    )
    settings = Settings(
        assistant=AssistantSettings(
            timeout_s=130.0,
            connect_timeout_s=2.0,
            rate_limit_per_min=10,
            max_report_kb=512,
        )
    )
    limiter = SlidingWindowRateLimiter(limit=10, window_s=60.0, clock=clock)

    service = AssistantService(
        reports=report_service,
        client=client,
        limiter=limiter,
        guard=guard,
        settings=settings,
    )

    site_id = uuid.uuid4()
    result = await service.ask(site_id, "Как дела?")

    assert result.answer == "Этап 3 «Устройство свай» отстаёт. Этапа 3 и этап №4, этап 99."
    assert result.verified is True
    assert result.site_label == "p1"
    assert len(result.stages) == 2
    assert result.stages[0].ref == "этап 3"
    assert result.stages[1].ref == "этап 4"


@pytest.mark.asyncio
async def test_verified_false_и_списки_без_изменений() -> None:
    """verified=false и оба списка номеров проходят без изменений."""
    clock = FakeClock()
    report_service = FakeReportService()
    guard = FakeGuard()
    client = FakeAssistantClient(
        answer=AssistantAnswer(
            answer="Ответ.",
            verified=False,
            numbers_not_in_report=["999"],
            numbers_of_other_site=["p1: 5"],
            limits="max_tokens=100",
        ),
        enabled=True,
    )
    settings = Settings()
    limiter = SlidingWindowRateLimiter(limit=10, window_s=60.0, clock=clock)

    service = AssistantService(
        reports=report_service,
        client=client,
        limiter=limiter,
        guard=guard,
        settings=settings,
    )

    site_id = uuid.uuid4()
    result = await service.ask(site_id, "Вопрос")

    assert result.verified is False
    assert result.numbers_not_in_report == ["999"]
    assert result.numbers_of_other_site == ["p1: 5"]
    assert result.limits == "max_tokens=100"


@pytest.mark.asyncio
async def test_ml_не_настроен_503_и_отчёт_не_строится() -> None:
    """ML не доступен (available=False): 503, отчёт не построен, лимит не потрачен."""
    clock = FakeClock()
    report_service = FakeReportService()
    guard = FakeGuard()
    client = FakeAssistantClient(enabled=False)
    settings = Settings()
    limiter = SlidingWindowRateLimiter(limit=10, window_s=60.0, clock=clock)

    service = AssistantService(
        reports=report_service,
        client=client,
        limiter=limiter,
        guard=guard,
        settings=settings,
    )

    site_id = uuid.uuid4()

    with pytest.raises(AppError) as exc_info:
        await service.ask(site_id, "Вопрос")

    assert exc_info.value.status_code == 503
    assert exc_info.value.code == "assistant_unavailable"
    assert exc_info.value.message == "Ассистент недоступен"

    # Отчёт не был построен
    assert len(report_service.calls) == 0
    # Клиент не был вызван
    assert len(client.calls) == 0
    # Лимит не был потрачен
    assert limiter.hit(str(guard.owner_id)) is None
    # Второй запрос тоже пройдёт (лимит не потрачен на первом)
    assert limiter.hit(str(guard.owner_id)) is None


@pytest.mark.asyncio
async def test_чужая_площадка_404_до_всего() -> None:
    """Чужая площадка: guard выбрасывает 404 до всего."""
    clock = FakeClock()
    report_service = FakeReportService()
    error = AppError("Стройка не найдена", 404)
    guard = FakeGuard(error=error)
    client = FakeAssistantClient()
    settings = Settings()
    limiter = SlidingWindowRateLimiter(limit=10, window_s=60.0, clock=clock)

    service = AssistantService(
        reports=report_service,
        client=client,
        limiter=limiter,
        guard=guard,
        settings=settings,
    )

    site_id = uuid.uuid4()

    with pytest.raises(AppError) as exc_info:
        await service.ask(site_id, "Вопрос")

    assert exc_info.value.status_code == 404

    # Отчёт не был построен
    assert len(report_service.calls) == 0
    # Клиент не был вызван
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_нет_графика_404() -> None:
    """Отчёт выбрасывает 404 (График не загружен), это пробивается наружу, клиент не вызывается."""
    clock = FakeClock()

    async def build_with_error(site_id):
        raise AppError("График не загружен", 404)

    report_service = FakeReportService()
    report_service.build = build_with_error

    guard = FakeGuard()
    client = FakeAssistantClient()
    settings = Settings()
    limiter = SlidingWindowRateLimiter(limit=10, window_s=60.0, clock=clock)

    service = AssistantService(
        reports=report_service,
        client=client,
        limiter=limiter,
        guard=guard,
        settings=settings,
    )

    site_id = uuid.uuid4()

    with pytest.raises(AppError) as exc_info:
        await service.ask(site_id, "Вопрос")

    assert exc_info.value.status_code == 404
    assert exc_info.value.message == "График не загружен"
    # Клиент не был вызван
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_лимит_частоты() -> None:
    """Лимит работает: 2 просят пройдут, 3-й выдаст 429, потом после 61с пройдёт."""
    clock = FakeClock()
    report_service = FakeReportService()
    guard = FakeGuard()
    client = FakeAssistantClient(
        answer=AssistantAnswer(
            answer="Ответ.",
            verified=True,
            numbers_not_in_report=[],
            numbers_of_other_site=[],
            limits="",
        ),
        enabled=True,
    )
    settings = Settings(assistant=AssistantSettings(rate_limit_per_min=2))
    limiter = SlidingWindowRateLimiter(limit=2, window_s=60.0, clock=clock)

    service = AssistantService(
        reports=report_service,
        client=client,
        limiter=limiter,
        guard=guard,
        settings=settings,
    )

    site_id = uuid.uuid4()

    # Первые два запроса пройдут
    await service.ask(site_id, "Вопрос 1")
    await service.ask(site_id, "Вопрос 2")
    assert len(client.calls) == 2

    # Третий выдаст 429
    with pytest.raises(AppError) as exc_info:
        await service.ask(site_id, "Вопрос 3")
    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "rate_limited"
    assert "Повторите через" in exc_info.value.message
    # Клиент всё ещё вызван только 2 раза
    assert len(client.calls) == 2

    # После продвижения времени на 61 секунду следующий запрос пройдёт
    clock.advance(61.0)
    await service.ask(site_id, "Вопрос 4")
    assert len(client.calls) == 3


@pytest.mark.asyncio
async def test_отчёт_слишком_велик_413() -> None:
    """Отчёт больше max_report_kb выдаёт 413."""
    clock = FakeClock()

    # Создаём большой отчёт (5 KB)
    large_report = {"data": "x" * 5000}

    report_service = FakeReportService(report=large_report)
    guard = FakeGuard()
    client = FakeAssistantClient(enabled=True)
    settings = Settings(assistant=AssistantSettings(max_report_kb=1))
    limiter = SlidingWindowRateLimiter(limit=10, window_s=60.0, clock=clock)

    service = AssistantService(
        reports=report_service,
        client=client,
        limiter=limiter,
        guard=guard,
        settings=settings,
    )

    site_id = uuid.uuid4()

    with pytest.raises(AppError) as exc_info:
        await service.ask(site_id, "Вопрос")

    assert exc_info.value.status_code == 413
    assert exc_info.value.code == "report_too_large"
    # Клиент не был вызван
    assert len(client.calls) == 0


@pytest.mark.asyncio
async def test_ошибки_клиента_маппятся_в_app_error() -> None:
    """AssistantError маппятся в AppError с теми же status_code и code."""
    clock = FakeClock()

    # Test cases: (error, expected_status, expected_code)
    test_cases = [
        (
            AssistantUnavailable(),
            503,
            "assistant_unavailable",
        ),
        (
            AssistantTimeout(),
            504,
            "assistant_timeout",
        ),
        (
            AssistantBadRequest(status_code=422, code="out_of_scope", message="Только по отчёту"),
            422,
            "out_of_scope",
        ),
        (
            AssistantBadRequest(),
            400,
            "assistant_bad_request",
        ),
    ]

    for error, expected_status, expected_code in test_cases:
        report_service = FakeReportService()
        guard = FakeGuard()
        client = FakeAssistantClient(error=error, enabled=True)
        settings = Settings()
        limiter = SlidingWindowRateLimiter(limit=10, window_s=60.0, clock=clock)

        service = AssistantService(
            reports=report_service,
            client=client,
            limiter=limiter,
            guard=guard,
            settings=settings,
        )

        site_id = uuid.uuid4()

        with pytest.raises(AppError) as exc_info:
            await service.ask(site_id, "Вопрос")

        assert exc_info.value.status_code == expected_status
        assert exc_info.value.code == expected_code
        assert exc_info.value.message == error.message


@pytest.mark.asyncio
async def test_в_логах_нет_текста_ответа_и_вопроса(caplog) -> None:
    """Вопрос и ответ не логируются, только длины и статус."""
    caplog.set_level(logging.INFO)

    clock = FakeClock()
    report_service = FakeReportService()
    guard = FakeGuard()
    client = FakeAssistantClient(
        answer=AssistantAnswer(
            answer="Секретный ответ p1",
            verified=True,
            numbers_not_in_report=[],
            numbers_of_other_site=[],
            limits="",
        ),
        enabled=True,
    )
    settings = Settings()
    limiter = SlidingWindowRateLimiter(limit=10, window_s=60.0, clock=clock)

    service = AssistantService(
        reports=report_service,
        client=client,
        limiter=limiter,
        guard=guard,
        settings=settings,
    )

    site_id = uuid.uuid4()
    await service.ask(site_id, "Секретный вопрос")

    # Проверяем, что текст вопроса и ответа не в логах
    assert "Секретный вопрос" not in caplog.text
    assert "Секретный ответ p1" not in caplog.text
    # Проверяем, что есть логирование с длинами и статусом
    assert "assistant.ask" in caplog.text
    assert "verified=True" in caplog.text


@pytest.mark.asyncio
async def test_status() -> None:
    """status() возвращает enabled значение из client.available()."""
    clock = FakeClock()

    # Test with enabled=True
    client_enabled = FakeAssistantClient(enabled=True)
    report_service = FakeReportService()
    guard = FakeGuard()
    settings = Settings()
    limiter = SlidingWindowRateLimiter(limit=10, window_s=60.0, clock=clock)

    service = AssistantService(
        reports=report_service,
        client=client_enabled,
        limiter=limiter,
        guard=guard,
        settings=settings,
    )

    status_result = await service.status()
    assert status_result.enabled is True

    # Test with enabled=False
    client_disabled = FakeAssistantClient(enabled=False)
    service2 = AssistantService(
        reports=report_service,
        client=client_disabled,
        limiter=limiter,
        guard=guard,
        settings=settings,
    )

    status_result2 = await service2.status()
    assert status_result2.enabled is False


@pytest.mark.asyncio
async def test_askrequest_границы() -> None:
    """AskRequest валидирует границы: 3-500 символов, обрезает whitespace."""
    # "  ab  " (2 символа после обрезки) -> должен упасть
    with pytest.raises(ValueError):
        AskRequest(question="  ab  ")

    # "abc" (3 символа) -> должен пройти
    req = AskRequest(question="abc")
    assert req.question == "abc"

    # 500 символов -> должен пройти
    req = AskRequest(question="а" * 500)
    assert len(req.question) == 500

    # 501 символ -> должен упасть
    with pytest.raises(ValueError):
        AskRequest(question="а" * 501)

    # Whitespace обрезается
    req = AskRequest(question="   тест   ")
    assert req.question == "тест"
