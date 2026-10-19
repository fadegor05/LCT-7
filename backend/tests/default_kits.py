"""Тестовая подстановка стартовых комплектов из DEFAULT_RULES.

В проде комплекты не подставляются (пользователь задаёт их сам), но часть тестов
проверяет расчёт статусов и правку методики на готовых комплектах.
"""

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.domains.methodology.defaults import DefaultRuleSet
from app.domains.methodology.materializer import NO_KIT_REASON
from app.domains.methodology.models import EquipmentRequirement, EquipmentType, MethodologyRule
from app.domains.methodology.repository import MethodologyRepository
from app.domains.schedule.models import ScheduleStage


async def materialize_with_default_kits(
    self, site_id: uuid.UUID, stages: Sequence[ScheduleStage]
) -> bool:
    """Замена RuleMaterializer.materialize: правила со стартовыми комплектами."""
    repository: MethodologyRepository = self._repository
    session = repository._session  # noqa: SLF001
    defaults = DefaultRuleSet()
    existing = {rule.stage_id for rule in await repository.list_rules_by_site(site_id)}

    created = False
    for stage in stages:
        if stage.id in existing:
            continue
        default_rule = defaults.match_stage(stage.name)
        if default_rule is None:
            await repository.add(
                MethodologyRule(
                    site_id=site_id,
                    stage_id=stage.id,
                    is_verifiable=False,
                    unverifiable_reason=NO_KIT_REASON,
                )
            )
            created = True
            continue

        rule = MethodologyRule(
            site_id=site_id,
            stage_id=stage.id,
            stage_key=default_rule.stage_key,
            is_verifiable=default_rule.unchecked_reason is None,
            unverifiable_reason=default_rule.unchecked_reason,
        )
        await repository.add(rule)
        for idx, default_set in enumerate(default_rule.sets, start=1):
            equipment_set = await repository.add_set(rule.id, idx)
            requirements = []
            for req in default_set:
                type_id = (
                    await session.execute(
                        select(EquipmentType.id).where(EquipmentType.code == req.equipment_code)
                    )
                ).scalar_one()
                requirements.append(
                    EquipmentRequirement(
                        set_id=equipment_set.id,
                        equipment_type_id=type_id,
                        min_count=req.min_count,
                        obligation=req.obligation,
                        gesn_code=req.gesn_code,
                        source_note=req.source_note,
                    )
                )
            await repository.add_requirements(equipment_set.id, requirements)
        created = True
    return created
