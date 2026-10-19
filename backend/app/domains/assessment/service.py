"""Бизнес-логика чтения статусов этапов и отклонений."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assessment.models import (
    Decision,
    Deviation,
    HypothesisDecision,
    deviation_key,
)
from app.domains.assessment.repository import (
    DeviationEvidenceRepository,
    DeviationRepository,
    HypothesisDecisionRepository,
    SiteSummaryRepository,
    StageStatusRepository,
)
from app.domains.assessment.schemas import (
    DecisionIn,
    DecisionRead,
    DeviationDetailRead,
    DeviationEvidenceRead,
    DeviationRead,
    SiteSummaryRead,
    StageStatusRead,
)
from app.domains.schedule.repository import ScheduleRepository
from app.domains.site.guard import SiteAccessGuard
from app.domains.user.models import User
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
        decision_repo: HypothesisDecisionRepository,
        session: AsyncSession,
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
        self._decision_repo = decision_repo
        self._session = session

    def _read(self, d: Deviation, decisions: dict[str, HypothesisDecision]) -> DeviationRead:
        """Отклонение с устойчивым ключом и решением инженера (только у гипотез)."""
        read = DeviationRead.model_validate(d)
        read.key = deviation_key(d.type, d.stage_id, d.equipment_type_id)
        found = decisions.get(read.key) if d.is_hypothesis else None
        read.decision = DecisionRead.model_validate(found) if found else None
        return read

    async def _visible(self, site_id: uuid.UUID) -> list[DeviationRead]:
        """Отклонения объекта без отклонённых инженером гипотез — те в архиве."""
        decisions = await self._decision_repo.by_site(site_id)
        rows = [self._read(d, decisions) for d in await self._deviation_repo.list_by_site(site_id)]
        return [
            r for r in rows if r.decision is None or r.decision.decision != Decision.REJECTED.value
        ]

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
                delay_min=status.delay_min if status else None,
                delay_max=status.delay_max if status else None,
                start_fact=status.start_fact if status else None,
                marker_names=(status.marker_names or []) if status else [],
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
        return await self._visible(site_id)

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
        deviation_read = self._read(deviation, await self._decision_repo.by_site(site_id))
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

        # Отклонения без архива: отклонённая инженером гипотеза в счёт не идёт
        deviations = await self._visible(site_id)
        awaiting = sum(1 for d in deviations if d.is_hypothesis and d.decision is None)

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
                awaiting_decision=awaiting,
            )
        return SiteSummaryRead(
            verdict=summary.verdict,
            delay_days_min=summary.delay_days_min,
            delay_days_max=summary.delay_days_max,
            critical_count=critical_count,
            attention_count=attention_count,
            reason=summary.reason,
            stage_id=summary.stage_id,
            as_of=summary.as_of,
            awaiting_decision=awaiting,
        )

    async def decide(
        self, site_id: uuid.UUID, deviation_id: uuid.UUID, data: DecisionIn, user: User
    ) -> DeviationDetailRead:
        """Решение инженера по гипотезе (clean-mvp, §8.8). Пересчёт не нужен: итог объекта от
        решения не зависит, гипотезы и так не бывают критичными. `decision: None` — снять."""
        await self._guard.require(site_id)
        deviation = await self._deviation_repo.get(deviation_id)
        if deviation is None or deviation.site_id != site_id:
            raise AppError("Отклонение не найдено", status_code=404)
        if not deviation.is_hypothesis:
            raise AppError("Решение принимается только по гипотезе", status_code=422)
        key = deviation_key(deviation.type, deviation.stage_id, deviation.equipment_type_id)
        row = await self._decision_repo.find(site_id, key)
        if data.decision is None:
            if row is not None:
                await self._session.delete(row)
        else:
            if row is None:
                row = HypothesisDecision(site_id=site_id, deviation_key=key)
                self._session.add(row)
            row.decision = data.decision
            row.comment = data.comment or None
            row.decided_by = user.id
            row.decided_by_name = user.full_name
            row.decided_at = datetime.now(UTC)
        await self._session.commit()
        return await self.get_deviation(site_id, deviation_id)
