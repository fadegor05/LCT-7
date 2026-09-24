"""Доступ к данным методологии проверки оборудования."""

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select

from app.core.repository import BaseRepository
from app.domains.methodology.models import EquipmentRequirement, EquipmentSet, MethodologyRule
from app.domains.schedule.models import ScheduleStage


class MethodologyRepository(BaseRepository[MethodologyRule]):
    """Репозиторий правил методологии проверки оборудования."""

    model = MethodologyRule

    async def list_rules_by_site(self, site_id: uuid.UUID) -> Sequence[MethodologyRule]:
        """Получить все правила для сайта, упорядочены по position этапов."""
        result = await self._session.execute(
            select(MethodologyRule)
            .join(ScheduleStage, MethodologyRule.stage_id == ScheduleStage.id)
            .where(MethodologyRule.site_id == site_id)
            .order_by(ScheduleStage.position)
        )
        return result.scalars().all()

    async def get_set(self, set_id: uuid.UUID) -> EquipmentSet | None:
        """Получить набор требований по ID."""
        return await self._session.get(EquipmentSet, set_id)

    async def list_sets(self, rule_ids: Sequence[uuid.UUID]) -> Sequence[EquipmentSet]:
        """Получить все наборы для правил, упорядочены по rule_id, position."""
        if not rule_ids:
            return []
        result = await self._session.execute(
            select(EquipmentSet)
            .where(EquipmentSet.rule_id.in_(rule_ids))
            .order_by(EquipmentSet.rule_id, EquipmentSet.position)
        )
        return result.scalars().all()

    async def list_requirements(
        self, set_ids: Sequence[uuid.UUID]
    ) -> Sequence[EquipmentRequirement]:
        """Получить все требования для наборов, упорядочены по set_id, id."""
        if not set_ids:
            return []
        result = await self._session.execute(
            select(EquipmentRequirement)
            .where(EquipmentRequirement.set_id.in_(set_ids))
            .order_by(EquipmentRequirement.set_id, EquipmentRequirement.id)
        )
        return result.scalars().all()

    async def add_set(self, rule_id: uuid.UUID, position: int) -> EquipmentSet:
        """Создать новый набор требований и флашить."""
        equipment_set = EquipmentSet(rule_id=rule_id, position=position)
        self._session.add(equipment_set)
        await self._session.flush()
        return equipment_set

    async def add_requirements(
        self, set_id: uuid.UUID, items: Sequence[EquipmentRequirement]
    ) -> None:
        """Добавить требования в набор и флашить."""
        for item in items:
            self._session.add(item)
        await self._session.flush()

    async def delete_requirements_of_set(self, set_id: uuid.UUID) -> None:
        """Удалить все требования набора и флашить."""
        await self._session.execute(
            delete(EquipmentRequirement).where(EquipmentRequirement.set_id == set_id)
        )
        await self._session.flush()

    async def delete_set(self, equipment_set: EquipmentSet) -> None:
        """Удалить набор (сначала удалить требования явно)."""
        # Delete requirements first
        await self.delete_requirements_of_set(equipment_set.id)
        # Then delete the set
        await self._session.delete(equipment_set)
        await self._session.flush()

    async def max_position(self, rule_id: uuid.UUID) -> int:
        """Получить максимальную позицию набора для правила (возвращает -1 если нет)."""
        result = await self._session.execute(
            select(EquipmentSet.position)
            .where(EquipmentSet.rule_id == rule_id)
            .order_by(EquipmentSet.position.desc())
            .limit(1)
        )
        position = result.scalar_one_or_none()
        return position if position is not None else -1
