"""Доступ к данным графиков выполнения работ."""

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select

from app.core.repository import BaseRepository
from app.domains.methodology.models import EquipmentRequirement, EquipmentSet, MethodologyRule
from app.domains.schedule.models import Schedule, ScheduleImportIssue, ScheduleStage


class ScheduleRepository(BaseRepository[Schedule]):
    """Репозиторий графиков выполнения работ."""

    model = Schedule

    async def get_by_site(self, site_id: uuid.UUID) -> Schedule | None:
        """Получить график по site_id."""
        result = await self._session.execute(
            select(self.model).where(self.model.site_id == site_id)
        )
        return result.scalar_one_or_none()

    async def delete_by_site(self, site_id: uuid.UUID) -> None:
        """Удалить график и связанные данные по site_id.

        Явно удаляет issues, stages, затем schedule и флашит.
        """
        schedule = await self.get_by_site(site_id)
        if schedule is None:
            return

        # Удалить issues
        await self._session.execute(
            delete(ScheduleImportIssue).where(ScheduleImportIssue.schedule_id == schedule.id)
        )

        # Удалить stages
        await self._session.execute(
            delete(ScheduleStage).where(ScheduleStage.schedule_id == schedule.id)
        )

        # Удалить schedule
        await self._session.execute(delete(self.model).where(self.model.id == schedule.id))

        await self._session.flush()

    async def add_stages(self, stages: list[ScheduleStage]) -> None:
        """Добавить этапы и флашить."""
        self._session.add_all(stages)
        await self._session.flush()

    async def add_issues(self, issues: list[ScheduleImportIssue]) -> None:
        """Добавить ошибки импорта и флашить."""
        self._session.add_all(issues)
        await self._session.flush()

    async def list_stages(self, schedule_id: uuid.UUID) -> Sequence[ScheduleStage]:
        """Получить этапы графика, упорядочены по position."""
        result = await self._session.execute(
            select(ScheduleStage)
            .where(ScheduleStage.schedule_id == schedule_id)
            .order_by(ScheduleStage.position)
        )
        return result.scalars().all()

    async def get_stage(self, schedule_id: uuid.UUID, stage_id: uuid.UUID) -> ScheduleStage | None:
        """Получить этап по schedule_id и stage_id."""
        result = await self._session.execute(
            select(ScheduleStage).where(
                (ScheduleStage.schedule_id == schedule_id) & (ScheduleStage.id == stage_id)
            )
        )
        return result.scalar_one_or_none()

    async def list_issues(self, schedule_id: uuid.UUID) -> Sequence[ScheduleImportIssue]:
        """Получить ошибки импорта, упорядочены по row_number."""
        result = await self._session.execute(
            select(ScheduleImportIssue)
            .where(ScheduleImportIssue.schedule_id == schedule_id)
            .order_by(ScheduleImportIssue.row_number)
        )
        return result.scalars().all()

    async def add_rule(self, rule: MethodologyRule) -> MethodologyRule:
        """Добавить правило методики и флашить."""
        self._session.add(rule)
        await self._session.flush()
        return rule

    async def list_rules_of_stages(
        self, stage_ids: Sequence[uuid.UUID]
    ) -> Sequence[MethodologyRule]:
        """Правила методики этапов (этапы без правила не попадают в список)."""
        if not stage_ids:
            return []
        result = await self._session.execute(
            select(MethodologyRule).where(MethodologyRule.stage_id.in_(stage_ids))
        )
        return result.scalars().all()

    async def list_sets_of_rules(self, rule_ids: Sequence[uuid.UUID]) -> Sequence[EquipmentSet]:
        """Наборы техники правил, упорядочены по rule_id и position."""
        if not rule_ids:
            return []
        result = await self._session.execute(
            select(EquipmentSet)
            .where(EquipmentSet.rule_id.in_(rule_ids))
            .order_by(EquipmentSet.rule_id, EquipmentSet.position)
        )
        return result.scalars().all()

    async def list_requirements_of_sets(
        self, set_ids: Sequence[uuid.UUID]
    ) -> Sequence[EquipmentRequirement]:
        """Требования наборов техники."""
        if not set_ids:
            return []
        result = await self._session.execute(
            select(EquipmentRequirement).where(EquipmentRequirement.set_id.in_(set_ids))
        )
        return result.scalars().all()

    async def delete_rules(self, rule_ids: Sequence[uuid.UUID]) -> None:
        """Удалить правила вместе с их наборами и требованиями (явно: SQLite без FK-каскада)."""
        if not rule_ids:
            return
        set_ids = select(EquipmentSet.id).where(EquipmentSet.rule_id.in_(rule_ids))
        await self._session.execute(
            delete(EquipmentRequirement).where(EquipmentRequirement.set_id.in_(set_ids))
        )
        await self._session.execute(delete(EquipmentSet).where(EquipmentSet.rule_id.in_(rule_ids)))
        await self._session.execute(delete(MethodologyRule).where(MethodologyRule.id.in_(rule_ids)))
        await self._session.flush()
