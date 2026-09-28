"""Сервис сборки отчёта для ассистента из данных assessment."""

import uuid

from app.domains.assessment.service import AssessmentService
from app.domains.assistant.report import BuiltReport, ReportInput, build_report
from app.domains.observation.repository import ObservationRepository
from app.domains.schedule.repository import ScheduleRepository
from app.plugins.exceptions import AppError


class AssistantReportService:
    """Сервис для сборки отчёта из данных assessment, schedule и observations."""

    def __init__(
        self,
        assessment: AssessmentService,
        schedule_repo: ScheduleRepository,
        observation_repo: ObservationRepository,
    ) -> None:
        """Инициализировать AssistantReportService.

        Args:
            assessment: Сервис для получения статусов этапов и отклонений.
            schedule_repo: Репозиторий графиков.
            observation_repo: Репозиторий наблюдений.
        """
        self._assessment = assessment
        self._schedule_repo = schedule_repo
        self._observation_repo = observation_repo

    async def build(self, site_id: uuid.UUID) -> BuiltReport:
        """Построить отчёт для ассистента из данных площадки.

        Вызывает assessment.list_stage_statuses() ПЕРВЫМ для проверки доступа
        и наличия графика. Если возникает ошибка (AppError), она пробивается
        наружу без попытки собрать остальные данные.

        Args:
            site_id: ID площадки.

        Returns:
            BuiltReport с собранным отчётом.

        Raises:
            AppError(404) если площадка не найдена или график не загружен.
        """
        # Вызываем list_stage_statuses ПЕРВЫМ для проверки доступа и графика
        # Это выбросит AppError 404 если графика нет или площадка чужая
        statuses = await self._assessment.list_stage_statuses(site_id)

        # Получаем отклонения
        deviations = await self._assessment.list_deviations(site_id)

        # Получаем сводку
        summary = await self._assessment.get_summary(site_id)

        # Получаем график и этапы
        schedule = await self._schedule_repo.get_by_site(site_id)
        if schedule is None:
            raise AppError("График не загружен", status_code=404)
        stages = await self._schedule_repo.list_stages(schedule.id)

        # Получаем наблюдения
        observations = await self._observation_repo.list_by_site(site_id)

        # Собираем отчёт
        report_input = ReportInput(
            stages=stages,
            statuses=statuses,
            deviations=deviations,
            summary=summary,
            observations=observations,
        )

        return build_report(report_input)
