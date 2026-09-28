"""AssistantReportService: сборка отчёта из данных assessment."""

import uuid
from collections.abc import Sequence
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.domains.assessment.schemas import SiteSummaryRead, StageStatusRead
from app.domains.observation.models import Observation
from app.domains.schedule.models import ScheduleStage
from app.plugins.exceptions import AppError


class FakeScheduleRepository:
    """Stub для ScheduleRepository."""

    def __init__(self):
        self.schedule_to_return = None
        self.stages_to_return: list[ScheduleStage] = []

    async def get_by_site(self, site_id: uuid.UUID):
        return self.schedule_to_return

    async def list_stages(self, schedule_id: uuid.UUID) -> Sequence[ScheduleStage]:
        return self.stages_to_return


class FakeObservationRepository:
    """Stub для ObservationRepository."""

    def __init__(self):
        self.observations_to_return: list[Observation] = []

    async def list_by_site(self, site_id: uuid.UUID) -> Sequence[Observation]:
        return self.observations_to_return


@pytest.mark.asyncio
async def test_build_собирает_отчёт_из_сервисов() -> None:
    """build() собирает отчёт из данных сервисов и репозиториев."""
    # Инициализируем fake-сервис assessment
    assessment_service = AsyncMock()

    # Инициализируем fake-репозитории
    schedule_repo = FakeScheduleRepository()
    observation_repo = FakeObservationRepository()

    site_id = uuid.uuid4()

    # Подготавливаем данные для assessment
    stage1_id = uuid.uuid4()
    stage2_id = uuid.uuid4()

    status1 = StageStatusRead(
        stage_id=stage1_id,
        stage_name="Подготовка",
        position=1,
        status="on_schedule",
        delay_days=None,
        confidence="high",
        confidence_reason="Все идёт по плану",
        computed_at=None,
    )

    status2 = StageStatusRead(
        stage_id=stage2_id,
        stage_name="Основные работы",
        position=2,
        status="behind",
        delay_days=14,
        confidence="medium",
        confidence_reason="Задержка из-за погоды",
        computed_at=None,
    )

    assessment_service.list_stage_statuses.return_value = [status1, status2]
    assessment_service.list_deviations.return_value = []
    assessment_service.get_summary.return_value = SiteSummaryRead(
        verdict="behind",
        delay_days_min=14,
        delay_days_max=14,
        critical_count=0,
        attention_count=1,
    )

    # Подготавливаем stages
    schedule_obj = AsyncMock()
    schedule_obj.id = uuid.uuid4()
    schedule_repo.schedule_to_return = schedule_obj

    stage1 = AsyncMock()
    stage1.id = stage1_id
    stage1.position = 1
    stage1.name = "Подготовка"
    stage1.planned_start = date(2024, 1, 1)
    stage1.planned_end = date(2024, 1, 15)

    stage2 = AsyncMock()
    stage2.id = stage2_id
    stage2.position = 2
    stage2.name = "Основные работы"
    stage2.planned_start = date(2024, 1, 16)
    stage2.planned_end = date(2024, 3, 31)

    schedule_repo.stages_to_return = [stage1, stage2]

    # Подготавливаем observations
    obs = AsyncMock()
    obs.observed_on = date(2024, 1, 20)
    observation_repo.observations_to_return = [obs]

    # Импортируем сервис (который мы ещё не написали)
    from app.domains.assistant.service import AssistantReportService

    service = AssistantReportService(
        assessment=assessment_service,
        schedule_repo=schedule_repo,
        observation_repo=observation_repo,
    )

    built_report = await service.build(site_id)

    # Проверяем, что сервис был вызван в правильном порядке
    assessment_service.list_stage_statuses.assert_called_once_with(site_id)
    assessment_service.list_deviations.assert_called_once_with(site_id)
    assessment_service.get_summary.assert_called_once_with(site_id)

    # Проверяем структуру отчёта
    assert built_report.report is not None
    assert "sites" in built_report.report
    assert len(built_report.report["sites"]) == 1
    assert built_report.report["sites"][0]["site_id"] == "p1"

    # Проверяем stage_ids
    assert built_report.stage_ids[1] == stage1_id
    assert built_report.stage_ids[2] == stage2_id


@pytest.mark.asyncio
async def test_чужая_площадка_404() -> None:
    """Если assessment.list_stage_statuses поднимает AppError(404),
    то schedule и observation репозитории не должны быть вызваны."""
    assessment_service = AsyncMock()
    assessment_service.list_stage_statuses.side_effect = AppError("Стройка не найдена", 404)

    schedule_repo = AsyncMock()
    observation_repo = AsyncMock()

    site_id = uuid.uuid4()

    from app.domains.assistant.service import AssistantReportService

    service = AssistantReportService(
        assessment=assessment_service,
        schedule_repo=schedule_repo,
        observation_repo=observation_repo,
    )

    # Должна поднять ошибку и не вызвать остальные методы
    with pytest.raises(AppError) as exc_info:
        await service.build(site_id)

    assert exc_info.value.status_code == 404
    # Репозитории не должны быть вызваны
    assert schedule_repo.get_by_site.call_count == 0
    assert observation_repo.list_by_site.call_count == 0


@pytest.mark.asyncio
async def test_нет_графика_404() -> None:
    """Если график не загружен, AssessmentService поднимает AppError('График не загружен', 404)."""
    assessment_service = AsyncMock()
    assessment_service.list_stage_statuses.side_effect = AppError("График не загружен", 404)

    schedule_repo = AsyncMock()
    observation_repo = AsyncMock()

    site_id = uuid.uuid4()

    from app.domains.assistant.service import AssistantReportService

    service = AssistantReportService(
        assessment=assessment_service,
        schedule_repo=schedule_repo,
        observation_repo=observation_repo,
    )

    with pytest.raises(AppError) as exc_info:
        await service.build(site_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.message == "График не загружен"


@pytest.mark.asyncio
async def test_график_исчез_между_вызовами_404() -> None:
    """Если assessment успешно вернул статусы, но schedule исчезнет перед read,
    то service поднимает AppError('График не загружен', 404)."""
    assessment_service = AsyncMock()

    stage_id = uuid.uuid4()
    status = StageStatusRead(
        stage_id=stage_id,
        stage_name="Этап 1",
        position=1,
        status="on_schedule",
        delay_days=None,
        confidence=None,
        confidence_reason=None,
        computed_at=None,
    )

    assessment_service.list_stage_statuses.return_value = [status]
    assessment_service.list_deviations.return_value = []
    assessment_service.get_summary.return_value = SiteSummaryRead(
        verdict="no_deviations",
        delay_days_min=None,
        delay_days_max=None,
        critical_count=0,
        attention_count=0,
    )

    schedule_repo = AsyncMock()
    schedule_repo.get_by_site.return_value = None  # График исчез между вызовами

    observation_repo = AsyncMock()

    site_id = uuid.uuid4()

    from app.domains.assistant.service import AssistantReportService

    service = AssistantReportService(
        assessment=assessment_service,
        schedule_repo=schedule_repo,
        observation_repo=observation_repo,
    )

    with pytest.raises(AppError) as exc_info:
        await service.build(site_id)

    assert exc_info.value.status_code == 404
    assert exc_info.value.message == "График не загружен"


@pytest.mark.asyncio
async def test_stage_ids_сопоставлены_с_отчётом() -> None:
    """stage_ids[3] содержит ID третьего этапа по position."""
    assessment_service = AsyncMock()

    schedule_repo = FakeScheduleRepository()
    observation_repo = FakeObservationRepository()

    site_id = uuid.uuid4()

    # Создаём этапы в неправильном порядке (stage_ids[3] != stages[2].id)
    # но repository вернёт их отсортированные по position
    stage3_id = uuid.uuid4()
    stage1_id = uuid.uuid4()
    stage2_id = uuid.uuid4()

    # Статусы в порядке position
    status1 = StageStatusRead(
        stage_id=stage1_id,
        stage_name="Этап 1",
        position=1,
        status="on_schedule",
        delay_days=None,
        confidence=None,
        confidence_reason=None,
        computed_at=None,
    )

    status2 = StageStatusRead(
        stage_id=stage2_id,
        stage_name="Этап 2",
        position=2,
        status="on_schedule",
        delay_days=None,
        confidence=None,
        confidence_reason=None,
        computed_at=None,
    )

    status3 = StageStatusRead(
        stage_id=stage3_id,
        stage_name="Этап 3",
        position=3,
        status="on_schedule",
        delay_days=None,
        confidence=None,
        confidence_reason=None,
        computed_at=None,
    )

    assessment_service.list_stage_statuses.return_value = [status1, status2, status3]
    assessment_service.list_deviations.return_value = []
    assessment_service.get_summary.return_value = SiteSummaryRead(
        verdict="no_deviations",
        delay_days_min=None,
        delay_days_max=None,
        critical_count=0,
        attention_count=0,
    )

    schedule_obj = AsyncMock()
    schedule_obj.id = uuid.uuid4()
    schedule_repo.schedule_to_return = schedule_obj

    # Stages отсортированы по position
    stage1 = AsyncMock()
    stage1.id = stage1_id
    stage1.position = 1
    stage1.name = "Этап 1"
    stage1.planned_start = None
    stage1.planned_end = None

    stage2 = AsyncMock()
    stage2.id = stage2_id
    stage2.position = 2
    stage2.name = "Этап 2"
    stage2.planned_start = None
    stage2.planned_end = None

    stage3 = AsyncMock()
    stage3.id = stage3_id
    stage3.position = 3
    stage3.name = "Этап 3"
    stage3.planned_start = None
    stage3.planned_end = None

    schedule_repo.stages_to_return = [stage1, stage2, stage3]
    observation_repo.observations_to_return = []

    from app.domains.assistant.service import AssistantReportService

    service = AssistantReportService(
        assessment=assessment_service,
        schedule_repo=schedule_repo,
        observation_repo=observation_repo,
    )

    built_report = await service.build(site_id)

    # stage_ids[3] должен быть ID третьего этапа (stage3_id)
    assert built_report.stage_ids[3] == stage3_id
    assert built_report.stage_ids[1] == stage1_id
    assert built_report.stage_ids[2] == stage2_id


def test_контейнер_собирается_с_провайдером_ассистента() -> None:
    """create_container() успешно собирается с AssistantProvider (граф зависимостей валиден)."""
    from app.plugins.di import create_container

    # Dishka проверяет граф при создании контейнера и выбросит исключение при ошибке
    container = create_container()

    assert container is not None


def test_провайдер_объявляет_сервис_в_request_скоупе() -> None:
    """AssistantProvider объявляет AssistantReportService в REQUEST scope."""
    from dishka import Scope

    from app.domains.assistant.provider import AssistantProvider
    from app.domains.assistant.service import AssistantReportService

    provider = AssistantProvider()

    # Проверяем, что провайдер имеет фабрику для AssistantReportService в REQUEST scope
    factory_found = False
    for factory in provider.factories:
        # В Dishka factory.provides содержит информацию о том, что эта фабрика производит
        # и factory.scope содержит scope (Scope.REQUEST, Scope.APP и т.д.)
        if (
            hasattr(factory.provides, "type_hint")
            and factory.provides.type_hint is AssistantReportService
            and factory.scope is Scope.REQUEST
        ):
            factory_found = True
            break

    assert factory_found, "AssistantReportService должна быть зарегистрирована в REQUEST scope"
