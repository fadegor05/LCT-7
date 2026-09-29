"""Материализация правил методики для этапов графика."""

import uuid
from collections.abc import Sequence

from app.domains.methodology.models import MethodologyRule
from app.domains.methodology.repository import MethodologyRepository
from app.domains.schedule.models import ScheduleStage

NO_KIT_REASON = "Комплект не задан — добавьте технику для этапа"


class RuleMaterializer:
    """Создаёт недостающие правила методики для этапов графика.

    Комплект техники по умолчанию не подставляется: каждый этап получает пустое правило
    с is_verifiable=False, инженер сам включает проверку и задаёт комплект.

    Правила появляются лениво: при первом чтении методики (MethodologyService.list_rules)
    и при пересчёте статусов (RecomputeCoordinator). Без правил движок считает все этапы
    «не проверяемыми», поэтому пересчёт сразу после загрузки графика тоже их создаёт.

    Только добавляет строки в сессию; коммит и retry на IntegrityError — у вызывающего.
    """

    def __init__(self, repository: MethodologyRepository) -> None:
        self._repository = repository

    async def materialize(self, site_id: uuid.UUID, stages: Sequence[ScheduleStage]) -> bool:
        """Создать пустые непроверяемые правила для этапов, у которых их ещё нет.

        Args:
            site_id: ID сайта.
            stages: Этапы графика сайта.

        Returns:
            True, если что-то добавлено в сессию и нужен commit.
        """
        existing_rules = await self._repository.list_rules_by_site(site_id)
        existing_stage_ids = {rule.stage_id for rule in existing_rules}

        created = False
        for stage in stages:
            if stage.id in existing_stage_ids:
                continue
            await self._repository.add(
                MethodologyRule(
                    site_id=site_id,
                    stage_id=stage.id,
                    is_verifiable=False,
                    unverifiable_reason=NO_KIT_REASON,
                )
            )
            created = True

        return created
