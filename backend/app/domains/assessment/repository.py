"""Доступ к данным расчётных статусов этапов и отклонений от плана."""

import uuid
from collections.abc import Sequence

from sqlalchemy import case, delete, desc, select

from app.core.repository import BaseRepository
from app.domains.assessment.models import (
    Deviation,
    DeviationEvidence,
    HypothesisDecision,
    Severity,
    SiteSummary,
    StageStatus,
    StatusBasis,
)
from app.domains.schedule.models import Schedule, ScheduleStage


class SiteSummaryRepository(BaseRepository[SiteSummary]):
    """Итог по объекту из последнего пересчёта (ключ — site_id)."""

    model = SiteSummary


class StageStatusRepository(BaseRepository[StageStatus]):
    """Репозиторий рассчитанных статусов этапов."""

    model = StageStatus

    async def get_by_stage(self, stage_id: uuid.UUID) -> StageStatus | None:
        """Получить статус по ID этапа.

        Args:
            stage_id: ID этапа (уникальный по таблице stage_statuses).

        Returns:
            StageStatus если существует, иначе None.
        """
        result = await self._session.execute(
            select(self.model).where(self.model.stage_id == stage_id)
        )
        return result.scalar_one_or_none()

    async def list_by_site(self, site_id: uuid.UUID) -> Sequence[StageStatus]:
        """Получить все статусы этапов для сайта, упорядочены по позиции этапа.

        Проходит через ScheduleStage -> Schedule -> site_id для поиска.

        Args:
            site_id: ID стройки.

        Returns:
            Список статусов, упорядочен по ScheduleStage.position.
        """
        result = await self._session.execute(
            select(StageStatus)
            .join(ScheduleStage, StageStatus.stage_id == ScheduleStage.id)
            .join(Schedule, ScheduleStage.schedule_id == Schedule.id)
            .where(Schedule.site_id == site_id)
            .order_by(ScheduleStage.position)
        )
        return result.scalars().all()

    async def delete_missing(self, site_id: uuid.UUID, keep_stage_ids: Sequence[uuid.UUID]) -> None:
        """Удалить статусы этапов, не указанные в keep_stage_ids.

        Используется для удаления статусов этапов, которые больше не начались.
        (Этап, который не начался, не должен иметь никакой записи в таблице.)

        Args:
            site_id: ID стройки.
            keep_stage_ids: Список stage_id, которые оставить (не удалять).
        """
        if not keep_stage_ids:
            return

        # Получить все stage_ids для этого сайта
        result = await self._session.execute(
            select(StageStatus.stage_id)
            .join(ScheduleStage, StageStatus.stage_id == ScheduleStage.id)
            .join(Schedule, ScheduleStage.schedule_id == Schedule.id)
            .where(Schedule.site_id == site_id)
        )
        all_stage_ids_with_status = set(result.scalars().all())

        # Найти те, которые нужно удалить (в базе, но не в keep_stage_ids)
        stage_ids_to_delete = all_stage_ids_with_status - set(keep_stage_ids)

        if stage_ids_to_delete:
            await self._session.execute(
                delete(StageStatus).where(StageStatus.stage_id.in_(stage_ids_to_delete))
            )
            await self._session.flush()


class DeviationRepository(BaseRepository[Deviation]):
    """Репозиторий отклонений от плана."""

    model = Deviation

    async def list_by_site(self, site_id: uuid.UUID) -> Sequence[Deviation]:
        """Получить все отклонения для сайта.

        Упорядочены по severity (critical перед attention), потом по created_at (убыв.).

        Args:
            site_id: ID стройки.

        Returns:
            Список отклонений в требуемом порядке.
        """
        result = await self._session.execute(
            select(self.model)
            .where(self.model.site_id == site_id)
            .order_by(
                case(
                    (self.model.severity == Severity.CRITICAL.value, 0),
                    (self.model.severity == Severity.ATTENTION.value, 1),
                    else_=2,
                ),
                desc(self.model.created_at),
            )
        )
        return result.scalars().all()

    async def delete_by_site(self, site_id: uuid.UUID) -> None:
        """Удалить все отклонения для сайта.

        Сначала удаляет доказательства, затем отклонения
        (bulk delete не срабатывает с CASCADE FK).

        Args:
            site_id: ID стройки.
        """
        # Сначала удалить доказательства для всех отклонений этого сайта
        await self._session.execute(
            delete(DeviationEvidence).where(
                DeviationEvidence.deviation_id.in_(
                    select(Deviation.id).where(Deviation.site_id == site_id)
                )
            )
        )
        # Затем удалить сами отклонения
        await self._session.execute(delete(self.model).where(self.model.site_id == site_id))
        await self._session.flush()


class DeviationEvidenceRepository(BaseRepository[DeviationEvidence]):
    """Репозиторий доказательств отклонений."""

    model = DeviationEvidence

    async def list_by_deviation(self, deviation_id: uuid.UUID) -> Sequence[DeviationEvidence]:
        """Получить все доказательства для отклонения.

        Args:
            deviation_id: ID отклонения.

        Returns:
            Список доказательств.
        """
        result = await self._session.execute(
            select(self.model).where(self.model.deviation_id == deviation_id)
        )
        return result.scalars().all()

    async def add_many(self, rows: Sequence[DeviationEvidence]) -> None:
        """Добавить несколько доказательств и флашить.

        Args:
            rows: Список доказательств для добавления.
        """
        self._session.add_all(rows)
        await self._session.flush()


class StatusBasisRepository(BaseRepository[StatusBasis]):
    """Репозиторий оснований для статусов этапов."""

    model = StatusBasis

    async def list_by_status(self, status_id: uuid.UUID) -> Sequence[StatusBasis]:
        """Получить все наблюдения, составляющие основу статуса этапа.

        Args:
            status_id: ID статуса этапа.

        Returns:
            Список оснований.
        """
        result = await self._session.execute(
            select(self.model).where(self.model.status_id == status_id)
        )
        return result.scalars().all()

    async def add_many(self, rows: Sequence[StatusBasis]) -> None:
        """Добавить несколько оснований и флашить.

        Args:
            rows: Список оснований для добавления.
        """
        self._session.add_all(rows)
        await self._session.flush()

    async def delete_by_status(self, status_id: uuid.UUID) -> None:
        """Удалить все основания для статуса этапа.

        Args:
            status_id: ID статуса этапа.
        """
        await self._session.execute(delete(self.model).where(self.model.status_id == status_id))
        await self._session.flush()


class HypothesisDecisionRepository(BaseRepository[HypothesisDecision]):
    """Решения инженера по гипотезам: по объекту и устойчивому ключу отклонения."""

    model = HypothesisDecision

    async def by_site(self, site_id: uuid.UUID) -> dict[str, HypothesisDecision]:
        result = await self._session.execute(
            select(self.model).where(self.model.site_id == site_id)
        )
        return {d.deviation_key: d for d in result.scalars().all()}

    async def find(self, site_id: uuid.UUID, key: str) -> HypothesisDecision | None:
        return await self._session.get(self.model, (site_id, key))
