"""Материализация правил методики по умолчанию для этапов графика."""

import uuid
from collections.abc import Sequence

from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.methodology.defaults import DefaultRuleSet
from app.domains.methodology.models import EquipmentRequirement, MethodologyRule
from app.domains.methodology.repository import MethodologyRepository
from app.domains.schedule.models import ScheduleStage
from app.plugins.exceptions import AppError


class RuleMaterializer:
    """Создаёт недостающие правила методики из базового набора.

    Правила появляются лениво: при первом чтении методики (MethodologyService.list_rules)
    и при пересчёте статусов (RecomputeCoordinator). Без правил движок считает все этапы
    «не проверяемыми», поэтому пересчёт сразу после загрузки графика тоже их создаёт.

    Только добавляет строки в сессию; коммит и retry на IntegrityError — у вызывающего.
    """

    def __init__(
        self,
        repository: MethodologyRepository,
        catalog: EquipmentCatalog,
        defaults: DefaultRuleSet,
    ) -> None:
        self._repository = repository
        self._catalog = catalog
        self._defaults = defaults

    async def materialize(self, site_id: uuid.UUID, stages: Sequence[ScheduleStage]) -> bool:
        """Создать правила для этапов, у которых их ещё нет.

        Для этапа, совпавшего со строкой базового набора, — правило с наборами и
        требованиями; для остальных — правило с is_verifiable=False и причиной.

        Args:
            site_id: ID сайта.
            stages: Этапы графика сайта.

        Returns:
            True, если что-то добавлено в сессию и нужен commit.

        Raises:
            AppError(500) если справочник техники не содержит код из defaults.
        """
        existing_rules = await self._repository.list_rules_by_site(site_id)
        existing_stage_ids = {rule.stage_id for rule in existing_rules}

        created = False
        for stage in stages:
            if stage.id in existing_stage_ids:
                continue

            default_rule = self._defaults.match_stage(stage.name)
            if default_rule is None:
                await self._repository.add(
                    MethodologyRule(
                        site_id=site_id,
                        stage_id=stage.id,
                        is_verifiable=False,
                        unverifiable_reason="Нет правила в базовом наборе — задайте комплект",
                    )
                )
                created = True
                continue

            rule = MethodologyRule(
                site_id=site_id,
                stage_id=stage.id,
                stage_key=default_rule.stage_key,
                is_verifiable=True,
            )
            await self._repository.add(rule)

            for set_idx, default_set in enumerate(default_rule.sets, start=1):
                equipment_set = await self._repository.add_set(rule.id, set_idx)

                requirements = []
                for default_req in default_set:
                    equipment_type = await self._catalog.by_code(default_req.equipment_code)
                    if equipment_type is None:
                        msg = f"Справочник техники не содержит {default_req.equipment_code}"
                        raise AppError(msg, status_code=500)

                    requirements.append(
                        EquipmentRequirement(
                            set_id=equipment_set.id,
                            equipment_type_id=equipment_type.id,
                            min_count=default_req.min_count,
                            obligation=default_req.obligation,
                            gesn_code=default_req.gesn_code,
                            source_note=default_req.source_note,
                        )
                    )

                await self._repository.add_requirements(equipment_set.id, requirements)

            created = True

        return created
