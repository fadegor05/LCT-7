"""Бизнес-логика методологии проверки оборудования на объекте строительства."""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.methodology.catalog import EquipmentCatalog, EquipmentTypeInfo
from app.domains.methodology.defaults import DefaultRuleSet
from app.domains.methodology.materializer import NO_KIT_REASON, RuleMaterializer
from app.domains.methodology.models import (
    EquipmentRequirement,
    EquipmentSet,
    MethodologyRule,
    Obligation,
)
from app.domains.methodology.recalculator import StatusRecalculator
from app.domains.methodology.repository import MethodologyRepository
from app.domains.methodology.schemas import (
    RuleUpdate,
    SetWrite,
)
from app.domains.schedule.models import ScheduleStage
from app.domains.schedule.repository import ScheduleRepository
from app.domains.site.guard import SiteAccessGuard
from app.plugins.exceptions import AppError


@dataclass
class RequirementView:
    """View для требования по оборудованию (без Pydantic)."""

    requirement: EquipmentRequirement
    equipment_type: EquipmentTypeInfo


@dataclass
class SetView:
    """View для набора требований (без Pydantic)."""

    equipment_set: EquipmentSet
    requirements: list[RequirementView]


@dataclass
class RuleView:
    """View для правила методологии (без Pydantic)."""

    rule: MethodologyRule
    stage_name: str | None
    sets: list[SetView]


@dataclass
class ApplyDefaultsResult:
    """Результат применения правил по умолчанию."""

    applied: int
    eligible: int
    unmatched: int


class MethodologyService:
    """Бизнес-логика методологии проверки оборудования."""

    def __init__(
        self,
        repository: MethodologyRepository,
        session: AsyncSession,
        guard: SiteAccessGuard,
        schedule_repository: ScheduleRepository,
        catalog: EquipmentCatalog,
        recalculator: StatusRecalculator,
        default_rules: DefaultRuleSet,
    ) -> None:
        self._repository = repository
        self._session = session
        self._guard = guard
        self._schedule_repository = schedule_repository
        self._catalog = catalog
        self._recalculator = recalculator
        self._materializer = RuleMaterializer(repository)
        self._default_rules = default_rules

    async def list_equipment_types(self) -> list[EquipmentTypeInfo]:
        """Получить все типы оборудования из каталога."""
        return await self._catalog.all()

    async def list_rules(self, site_id: uuid.UUID) -> list[RuleView]:
        """Получить правила с ленивой материализацией по умолчанию.

        Для каждого этапа, не имеющего правила, создаёт правило:
        - Если совпадает со строкой по умолчанию: создаёт наборы и требования
        - Если нет: создаёт с is_verifiable=False и причиной

        Args:
            site_id: ID сайта

        Returns:
            Список RuleView, упорядочены по position этапа

        Raises:
            AppError(404) если сайт не принадлежит текущему пользователю
            AppError(404) если график не загружен
        """
        # Проверка доступа
        await self._guard.require(site_id)

        # Получаем график
        schedule = await self._schedule_repository.get_by_site(site_id)
        if schedule is None:
            raise AppError("График не загружен", status_code=404)

        # Получаем этапы графика (id берём заранее: после rollback ORM-объекты протухают)
        schedule_id = schedule.id
        stages = await self._schedule_repository.list_stages(schedule_id)

        # Материализация с retry на IntegrityError (race condition protection)
        stages = await self._materialize_with_retry(site_id, schedule_id, stages)

        # Загружаем все правила с этапами
        rules = await self._repository.list_rules_by_site(site_id)

        # Собираем наборы и требования
        rule_ids = [rule.id for rule in rules]
        sets_by_rule: dict[uuid.UUID, list[EquipmentSet]] = {}
        if rule_ids:
            all_sets = await self._repository.list_sets(rule_ids)
            for s in all_sets:
                if s.rule_id not in sets_by_rule:
                    sets_by_rule[s.rule_id] = []
                sets_by_rule[s.rule_id].append(s)

        set_ids = [s.id for s in sum(sets_by_rule.values(), [])]
        requirements_by_set: dict[uuid.UUID, list[EquipmentRequirement]] = {}
        if set_ids:
            all_requirements = await self._repository.list_requirements(set_ids)
            for req in all_requirements:
                if req.set_id not in requirements_by_set:
                    requirements_by_set[req.set_id] = []
                requirements_by_set[req.set_id].append(req)

        # Преобразуем в views (без построения схем)
        result: list[RuleView] = []
        for rule in rules:
            # Найти этап
            found_stage = next((s for s in stages if s.id == rule.stage_id), None)
            stage_name: str | None = found_stage.name if found_stage else None

            # Собрать наборы
            rule_sets = sets_by_rule.get(rule.id, [])
            set_views = []
            for s in rule_sets:
                reqs = requirements_by_set.get(s.id, [])
                req_views = []
                for req in reqs:
                    # Загрузить тип оборудования
                    equipment_type = await self._catalog.by_id(req.equipment_type_id)
                    if equipment_type:
                        req_view = RequirementView(
                            requirement=req,
                            equipment_type=equipment_type,
                        )
                        req_views.append(req_view)

                set_view = SetView(
                    equipment_set=s,
                    requirements=req_views,
                )
                set_views.append(set_view)

            # Сортируем наборы по позиции
            set_views.sort(key=lambda s: s.equipment_set.position)

            rule_view = RuleView(
                rule=rule,
                stage_name=stage_name,
                sets=set_views,
            )
            result.append(rule_view)

        # Сортируем по position этапов
        result.sort(
            key=lambda r: next((s.position for s in stages if s.id == r.rule.stage_id), 999)
        )

        return result

    async def update_rule(
        self, site_id: uuid.UUID, rule_id: uuid.UUID, data: RuleUpdate
    ) -> RuleView:
        """Обновить правило.

        Args:
            site_id: ID сайта
            rule_id: ID правила
            data: RuleUpdate со значениями

        Returns:
            RuleView

        Raises:
            AppError(404) если правило не принадлежит сайту или не найдено
        """
        rule = await self._get_site_rule(site_id, rule_id)

        # Обновить поля
        rule.is_verifiable = data.is_verifiable
        rule.unverifiable_reason = data.unverifiable_reason
        rule.updated_at = datetime.now(UTC)

        # Коммитим
        await self._session.commit()

        # Пересчитываем
        await self._recalculator.recalculate(site_id)

        # Возвращаем RuleView
        rules = await self.list_rules(site_id)
        return next(r for r in rules if r.rule.id == rule_id)

    async def create_set(self, site_id: uuid.UUID, rule_id: uuid.UUID, data: SetWrite) -> SetView:
        """Создать набор требований.

        Args:
            site_id: ID сайта
            rule_id: ID правила
            data: SetWrite с требованиями

        Returns:
            SetView

        Raises:
            AppError(404) если правило не принадлежит сайту
            AppError(422) если валидация требований не прошла
        """
        # Получить правило
        rule = await self._get_site_rule(site_id, rule_id)

        # Валидировать требования
        self._validate_requirements(data)

        # Валидировать, что нет coarse equipment
        await self._validate_no_coarse_equipment(data)

        # Получить правило с блокировкой FOR UPDATE для предотвращения race condition
        locked_rule = await self._repository.get_rule_for_update(rule_id)
        if locked_rule is None or locked_rule.site_id != site_id:
            raise AppError("Правило не найдено", status_code=404)

        # Добавить набор
        max_pos = await self._repository.max_position(rule_id)
        equipment_set = await self._repository.add_set(rule_id, max_pos + 1)

        # Добавить требования
        requirements = []
        for req_in in data.requirements:
            # Проверить, что equipment_type_id существует в каталоге
            equipment_type = await self._catalog.by_id(req_in.equipment_type_id)
            if equipment_type is None:
                raise AppError(
                    f"Неизвестный тип техники: {req_in.equipment_type_id}",
                    status_code=422,
                )

            req = EquipmentRequirement(
                set_id=equipment_set.id,
                equipment_type_id=req_in.equipment_type_id,
                min_count=req_in.min_count,
                obligation=req_in.obligation,
                gesn_code=req_in.gesn_code,
                source_note=req_in.source_note,
            )
            requirements.append(req)

        await self._repository.add_requirements(equipment_set.id, requirements)

        # Обновить updated_at правила
        rule.updated_at = datetime.now(UTC)

        # Коммитим
        await self._session.commit()

        # Пересчитываем
        await self._recalculator.recalculate(site_id)

        # Возвращаем SetView
        rules = await self.list_rules(site_id)
        rule_view = next(r for r in rules if r.rule.id == rule_id)
        return next(s for s in rule_view.sets if s.equipment_set.id == equipment_set.id)

    async def replace_set(self, site_id: uuid.UUID, set_id: uuid.UUID, data: SetWrite) -> SetView:
        """Заменить требования набора.

        Args:
            site_id: ID сайта
            set_id: ID набора
            data: SetWrite с новыми требованиями

        Returns:
            SetView

        Raises:
            AppError(404) если набор не принадлежит сайту
            AppError(422) если валидация требований не прошла
        """
        # Получить набор
        equipment_set = await self._get_site_set(site_id, set_id)

        # Валидировать требования
        self._validate_requirements(data)

        # Валидировать, что нет coarse equipment
        await self._validate_no_coarse_equipment(data)

        # Проверить все equipment_type_id ДО удаления старых требований
        for req_in in data.requirements:
            equipment_type = await self._catalog.by_id(req_in.equipment_type_id)
            if equipment_type is None:
                raise AppError(
                    f"Неизвестный тип техники: {req_in.equipment_type_id}",
                    status_code=422,
                )

        # Удалить старые требования
        await self._repository.delete_requirements_of_set(equipment_set.id)

        # Добавить новые требования
        requirements = []
        for req_in in data.requirements:
            req = EquipmentRequirement(
                set_id=equipment_set.id,
                equipment_type_id=req_in.equipment_type_id,
                min_count=req_in.min_count,
                obligation=req_in.obligation,
                gesn_code=req_in.gesn_code,
                source_note=req_in.source_note,
            )
            requirements.append(req)

        await self._repository.add_requirements(equipment_set.id, requirements)

        # Получить правило и обновить updated_at
        rule = await self._session.get(MethodologyRule, equipment_set.rule_id)
        if rule:
            rule.updated_at = datetime.now(UTC)

        # Коммитим
        await self._session.commit()

        # Пересчитываем
        await self._recalculator.recalculate(site_id)

        # Возвращаем SetView
        rules = await self.list_rules(site_id)
        rule_view = next(r for r in rules if r.rule.id == equipment_set.rule_id)
        return next(s for s in rule_view.sets if s.equipment_set.id == set_id)

    async def delete_set(self, site_id: uuid.UUID, set_id: uuid.UUID) -> None:
        """Удалить набор.

        Args:
            site_id: ID сайта
            set_id: ID набора

        Raises:
            AppError(404) если набор не принадлежит сайту
            AppError(422) если это последний набор проверяемого этапа
        """
        # Получить набор
        equipment_set = await self._get_site_set(site_id, set_id)

        # Получить правило
        rule = await self._session.get(MethodologyRule, equipment_set.rule_id)
        if rule is None:
            raise AppError("Правило не найдено", status_code=404)

        # Проверить, что это не последний набор проверяемого этапа
        if rule.is_verifiable:
            all_sets = await self._repository.list_sets([rule.id])
            if len(all_sets) == 1:
                raise AppError(
                    "Нельзя удалить последний комплект проверяемого этапа: "
                    "добавьте другой комплект или пометьте этап непроверяемым",
                    status_code=422,
                )

        # Удалить набор (репо удалит требования)
        await self._repository.delete_set(equipment_set)

        # Обновить updated_at правила
        rule.updated_at = datetime.now(UTC)

        # Коммитим
        await self._session.commit()

        # Пересчитываем
        await self._recalculator.recalculate(site_id)

    async def apply_defaults(self, site_id: uuid.UUID) -> ApplyDefaultsResult:
        """Применить правила по умолчанию к пустым правилам.

        Заполняет пустые правила наборами из DefaultRuleSet.
        Правило пусто, если: is_verifiable=False, unverifiable_reason=NO_KIT_REASON и нет наборов.

        Args:
            site_id: ID сайта

        Returns:
            ApplyDefaultsResult с количеством применённых, подходящих и несовпадающих правил

        Raises:
            AppError(404) если сайт не принадлежит текущему пользователю
            AppError(404) если график не загружен
            AppError(500) если неизвестный код оборудования в defaults
        """
        # Проверка доступа
        await self._guard.require(site_id)

        # Получаем график
        schedule = await self._schedule_repository.get_by_site(site_id)
        if schedule is None:
            raise AppError("График не загружен", status_code=404)

        # Получаем этапы графика
        schedule_id = schedule.id
        stages = await self._schedule_repository.list_stages(schedule_id)

        # Материализация с retry на IntegrityError (race condition protection)
        stages = await self._materialize_with_retry(site_id, schedule_id, stages)

        # Загружаем все правила
        rules = await self._repository.list_rules_by_site(site_id)

        # Собираем наборы по правилам
        rule_ids = [rule.id for rule in rules]
        sets_by_rule: dict[uuid.UUID, list[EquipmentSet]] = {}
        if rule_ids:
            all_sets = await self._repository.list_sets(rule_ids)
            for s in all_sets:
                if s.rule_id not in sets_by_rule:
                    sets_by_rule[s.rule_id] = []
                sets_by_rule[s.rule_id].append(s)

        # Находим пустые правила (is_verifiable=False, reason=NO_KIT_REASON, нет наборов)
        eligible_rules = []
        for rule in rules:
            if (
                rule.is_verifiable is False
                and rule.unverifiable_reason == NO_KIT_REASON
                and rule.id not in sets_by_rule
            ):
                eligible_rules.append(rule)

        eligible = len(eligible_rules)
        applied = 0

        # Для каждого пустого правила пытаемся применить defaults
        for rule in eligible_rules:
            # Найти stage
            found_stage = next((s for s in stages if s.id == rule.stage_id), None)
            if found_stage is None:
                continue

            # Попытаться найти совпадение по имени stage
            default_rule = self._default_rules.match_stage_or_works(
                found_stage.name, found_stage.work_names
            )
            if default_rule is None:
                # Совпадения нет — оставляем правило как есть
                continue

            # Есть совпадение — заполняем правило
            # Заблокировать правило для предотвращения race condition
            locked_rule = await self._repository.get_rule_for_update(rule.id)
            if locked_rule is None or locked_rule.site_id != site_id:
                continue

            # Переповторяем проверку (может измениться между чтением и блокировкой)
            if (
                locked_rule.is_verifiable is True
                or locked_rule.unverifiable_reason != NO_KIT_REASON
            ):
                # Rule was changed by someone else
                continue

            # Проверить, что правило всё ещё пусто
            rule_sets = await self._repository.list_sets([locked_rule.id])
            if len(rule_sets) > 0:
                # Rule already has sets
                continue

            # Семейство, которое по технике не проверяется (кровля, фасад): причина вместо
            # наборов — этап честно «не проверяется», а не «комплект не задан»
            if default_rule.unchecked_reason:
                locked_rule.unverifiable_reason = default_rule.unchecked_reason
                locked_rule.updated_at = datetime.now(UTC)
                applied += 1
                continue

            # Создаём наборы в порядке из default_rule.sets
            max_pos = await self._repository.max_position(locked_rule.id)
            for set_idx, default_set in enumerate(default_rule.sets):
                equipment_set = await self._repository.add_set(
                    locked_rule.id, max_pos + set_idx + 1
                )

                # Добавляем требования
                requirements = []
                for default_req in default_set:
                    # Получить equipment_type по коду
                    equipment_type = await self._catalog.by_code(default_req.equipment_code)
                    if equipment_type is None:
                        raise AppError(
                            f"Неизвестный код оборудования в defaults: "
                            f"{default_req.equipment_code}",
                            status_code=500,
                        )

                    # Каждое requirement помечено "базовая методика"
                    # (с опциональной доп. информацией из default)
                    if default_req.source_note:
                        source_note = f"базовая методика: {default_req.source_note}"
                    else:
                        source_note = "базовая методика"

                    req = EquipmentRequirement(
                        set_id=equipment_set.id,
                        equipment_type_id=equipment_type.id,
                        min_count=default_req.min_count,
                        obligation=default_req.obligation,
                        gesn_code=default_req.gesn_code,
                        source_note=source_note,
                        group_code=default_req.group_code,
                    )
                    requirements.append(req)

                await self._repository.add_requirements(equipment_set.id, requirements)

            # Обновляем правило
            locked_rule.is_verifiable = True
            locked_rule.unverifiable_reason = None
            locked_rule.updated_at = datetime.now(UTC)

            applied += 1

        # Коммитим, если что-то изменилось
        if applied > 0:
            await self._session.commit()
            # Пересчитываем только если применили что-то
            await self._recalculator.recalculate(site_id)

        unmatched = eligible - applied

        return ApplyDefaultsResult(
            applied=applied,
            eligible=eligible,
            unmatched=unmatched,
        )

    async def _materialize_with_retry(
        self, site_id: uuid.UUID, schedule_id: uuid.UUID, stages: Sequence[ScheduleStage]
    ) -> Sequence[ScheduleStage]:
        """Материализировать правила с retry на IntegrityError.

        Args:
            site_id: ID сайта
            schedule_id: ID графика
            stages: Этапы графика

        Returns:
            Этапы графика (возможно перечитанные после rollback)

        Raises:
            IntegrityError если после двух попыток всё ещё конфликт
        """
        max_retries = 2
        current_stages = stages
        for attempt in range(max_retries):
            try:
                need_commit = await self._materializer.materialize(site_id, current_stages)

                # Коммитим, если создали что-то новое
                if need_commit:
                    await self._session.commit()

                # Success - exit retry loop
                break
            except IntegrityError as e:
                # Rollback and retry once
                await self._session.rollback()
                if attempt < max_retries - 1:
                    # После rollback ORM-объекты expired — перечитываем этапы
                    current_stages = await self._schedule_repository.list_stages(schedule_id)
                    continue
                else:
                    # Re-raise on second attempt
                    raise e

        return current_stages

    async def _get_site_rule(self, site_id: uuid.UUID, rule_id: uuid.UUID) -> MethodologyRule:
        """Получить правило, проверив владение сайтом.

        Args:
            site_id: ID сайта
            rule_id: ID правила

        Returns:
            MethodologyRule

        Raises:
            AppError(404) если сайт не принадлежит пользователю
            AppError(404) если правило не найдено или не принадлежит сайту
        """
        # Проверить доступ к сайту
        await self._guard.require(site_id)

        # Получить правило
        rule = await self._repository.get(rule_id)
        if rule is None or rule.site_id != site_id:
            raise AppError("Правило не найдено", status_code=404)

        return rule

    async def _get_site_set(self, site_id: uuid.UUID, set_id: uuid.UUID) -> EquipmentSet:
        """Получить набор, проверив владение сайтом.

        Args:
            site_id: ID сайта
            set_id: ID набора

        Returns:
            EquipmentSet

        Raises:
            AppError(404) если сайт не принадлежит пользователю
            AppError(404) если набор не найдено или не принадлежит сайту
        """
        # Проверить доступ к сайту
        await self._guard.require(site_id)

        # Получить набор
        equipment_set = await self._repository.get_set(set_id)
        if equipment_set is None:
            raise AppError("Комплект не найден", status_code=404)

        # Проверить, что набор принадлежит правилу сайта
        rule = await self._repository.get(equipment_set.rule_id)
        if rule is None or rule.site_id != site_id:
            raise AppError("Комплект не найден", status_code=404)

        return equipment_set

    def _validate_requirements(self, data: SetWrite) -> None:
        """Валидировать требования.

        Args:
            data: SetWrite с требованиями

        Raises:
            AppError(422) если валидация не прошла
        """
        # Проверить, что есть хотя бы одно normative требование
        has_normative = any(req.obligation == Obligation.NORMATIVE for req in data.requirements)

        if not has_normative:
            raise AppError(
                "Логическое требование не может быть единственным доказательством этапа: "
                "добавьте нормативное требование",
                status_code=422,
            )

    async def _validate_no_coarse_equipment(self, data: SetWrite) -> None:
        """Валидировать, что нет coarse equipment в требованиях.

        Args:
            data: SetWrite с требованиями

        Raises:
            AppError(422) если обнаружен coarse equipment
        """
        for req_in in data.requirements:
            equipment_type = await self._catalog.by_id(req_in.equipment_type_id)
            if equipment_type and equipment_type.is_coarse:
                raise AppError(
                    f"Недопустимо использовать грубый класс '{equipment_type.code}' в требованиях: "
                    f"'{equipment_type.title}'",
                    status_code=422,
                )
