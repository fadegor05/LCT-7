"""Бизнес-логика чтения статусов этапов и отклонений."""

import uuid

from app.domains.assessment.repository import (
    DeviationEvidenceRepository,
    DeviationRepository,
    SiteSummaryRepository,
    StageStatusRepository,
)
from app.domains.assessment.schemas import (
    DeviationDetailRead,
    DeviationEvidenceRead,
    DeviationRead,
    SiteSummaryRead,
    StageStatusRead,
)
from app.domains.schedule.repository import ScheduleRepository
from app.domains.site.guard import SiteAccessGuard
from app.plugins.exceptions import AppError


class AssessmentService:
    """Чтение статусов этапов и отклонений."""

    def __init__(
        self,
        stage_status_repo: StageStatusRepository,
        deviation_repo: DeviationRepository,
        deviation_evidence_repo: DeviationEvidenceRepository,
        schedule_repo: ScheduleRepository,
        guard: SiteAccessGuard,
        summary_repo: SiteSummaryRepository,
    ) -> None:
        """Инициализировать AssessmentService.

        Args:
            stage_status_repo: StageStatusRepository для работы со статусами этапов.
            deviation_repo: DeviationRepository для работы с отклонениями.
            deviation_evidence_repo: DeviationEvidenceRepository для работы с доказательствами.
            schedule_repo: ScheduleRepository для работы с графиками.
            guard: SiteAccessGuard для проверки доступа.
            summary_repo: SiteSummaryRepository — итог из последнего пересчёта.
        """
        self._stage_status_repo = stage_status_repo
        self._deviation_repo = deviation_repo
        self._deviation_evidence_repo = deviation_evidence_repo
        self._schedule_repo = schedule_repo
        self._guard = guard
        self._summary_repo = summary_repo

    async def list_stage_statuses(self, site_id: uuid.UUID) -> list[StageStatusRead]:
        """Получить список статусов этапов для сайта.

        Включает все этапы из графика, даже те, у которых нет статуса (ещё не начались).

        Args:
            site_id: ID стройки.

        Returns:
            Список статусов этапов, упорядочены по position.

        Raises:
            AppError(404) если сайт не найден или график не загружен.
        """
        await self._guard.require(site_id)

        # Получить график
        schedule = await self._schedule_repo.get_by_site(site_id)
        if schedule is None:
            raise AppError("График не загружен", status_code=404)

        # Получить все этапы графика, упорядочены по position
        stages = await self._schedule_repo.list_stages(schedule.id)

        # Получить все статусы этапов для этого сайта, упорядочены по position
        statuses = await self._stage_status_repo.list_by_site(site_id)
        status_by_stage_id = {s.stage_id: s for s in statuses}

        # Собрать результат для каждого этапа
        result: list[StageStatusRead] = []
        for stage in stages:
            status = status_by_stage_id.get(stage.id)
            stage_status_read = StageStatusRead(
                stage_id=stage.id,
                stage_name=stage.name,
                position=stage.position,
                status=status.status if status else None,
                delay_days=status.delay_days if status else None,
                delay_open=status.delay_open if status else False,
                confidence=status.confidence if status else None,
                confidence_reason=status.confidence_reason if status else None,
                computed_at=status.computed_at if status else None,
            )
            result.append(stage_status_read)

        return result

    async def list_deviations(self, site_id: uuid.UUID) -> list[DeviationRead]:
        """Получить список отклонений для сайта.

        Отклонения отсортированы по severity (critical первыми) и по дате создания.

        Args:
            site_id: ID стройки.

        Returns:
            Список отклонений.

        Raises:
            AppError(404) если сайт не найден.
        """
        await self._guard.require(site_id)
        deviations = await self._deviation_repo.list_by_site(site_id)
        return [DeviationRead.model_validate(d) for d in deviations]

    async def get_deviation(
        self, site_id: uuid.UUID, deviation_id: uuid.UUID
    ) -> DeviationDetailRead:
        """Получить отклонение с доказательствами.

        Args:
            site_id: ID стройки.
            deviation_id: ID отклонения.

        Returns:
            Отклонение с доказательствами.

        Raises:
            AppError(404) если сайт не найден или отклонение не найдено.
        """
        await self._guard.require(site_id)

        # Получить отклонение
        deviation = await self._deviation_repo.get(deviation_id)
        if deviation is None or deviation.site_id != site_id:
            raise AppError("Отклонение не найдено", status_code=404)

        # Получить доказательства
        evidence_rows = await self._deviation_evidence_repo.list_by_deviation(deviation_id)
        evidence = [DeviationEvidenceRead.model_validate(e) for e in evidence_rows]

        # Собрать результат
        deviation_read = DeviationRead.model_validate(deviation)
        return DeviationDetailRead(
            **deviation_read.model_dump(),
            evidence=evidence,
        )

    async def get_summary(self, site_id: uuid.UUID) -> SiteSummaryRead:
        """Получить сводку статуса стройки.

        Args:
            site_id: ID стройки.

        Returns:
            Сводка статуса с вердиктом (behind/no_deviations/insufficient_data).

        Raises:
            AppError(404) если сайт не найден.
        """
        await self._guard.require(site_id)

        # Получить все отклонения
        deviations = await self._deviation_repo.list_by_site(site_id)

        # Считать отклонения по severity
        critical_count = sum(1 for d in deviations if d.severity == "critical")
        attention_count = sum(1 for d in deviations if d.severity == "attention")

        # Итог считает пересчёт по той же опорной дате, что статусы этапов (engine.summarize)
        schedule = await self._schedule_repo.get_by_site(site_id)
        summary = await self._summary_repo.get(site_id) if schedule else None
        if summary is None:
            return SiteSummaryRead(
                verdict="insufficient_data",
                delay_days_min=None,
                delay_days_max=None,
                critical_count=critical_count,
                attention_count=attention_count,
                reason=None if schedule else "График не загружен.",
            )
        return SiteSummaryRead(
            verdict=summary.verdict,
            delay_days_min=summary.delay_days_min,
            delay_days_max=summary.delay_days_max,
            critical_count=critical_count,
            attention_count=attention_count,
            reason=summary.reason,
            stage_id=summary.stage_id,
        )
