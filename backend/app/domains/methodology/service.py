"""Бизнес-логика методологии проверки оборудования на объекте строительства."""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.methodology.defaults import DefaultRuleSet
from app.domains.methodology.models import (
    EquipmentRequirement,
    EquipmentSet,
    MethodologyRule,
    Obligation,
)
from app.domains.methodology.recalculator import StatusRecalculator
from app.domains.methodology.repository import MethodologyRepository
from app.domains.methodology.schemas import (
    RequirementRead,
    RuleRead,
    RuleUpdate,
    SetRead,
    SetWrite,
)
from app.domains.schedule.repository import ScheduleRepository
from app.domains.site.guard import SiteAccessGuard
from app.plugins.exceptions import AppError


class MethodologyService:
    """Бизнес-логика методологии проверки оборудования."""

    def __init__(
        self,
        repository: MethodologyRepository,
        session: AsyncSession,
        guard: SiteAccessGuard,
        schedule_repository: ScheduleRepository,
        catalog: EquipmentCatalog,
        defaults: DefaultRuleSet,
        recalculator: StatusRecalculator,
    ) -> None:
        self._repository = repository
        self._session = session
        self._guard = guard
        self._schedule_repository = schedule_repository
        self._catalog = catalog
        self._defaults = defaults
        self._recalculator = recalculator

    async def list_equipment_types(self):
        """Получить все типы оборудования из каталога."""
        return await self._catalog.all()

    async def list_rules(self, site_id: uuid.UUID) -> list[RuleRead]:
        """Получить правила с ленивой материализацией по умолчанию.

        Для каждого этапа, не имеющего правила, создаёт правило:
        - Если совпадает со строкой по умолчанию: создаёт наборы и требования
        - Если нет: создаёт с is_verifiable=False и причиной

        Args:
            site_id: ID сайта

        Returns:
            Список RuleRead, упорядочены по position этапа

        Raises:
            AppError(404) если сайт не принадлежит текущему пользователю
            AppError(404) если график не загружен
            AppError(500) если справочник техники не содержит код из defaults
        """
        # Проверка доступа
        await self._guard.require(site_id)

        # Получаем график
        schedule = await self._schedule_repository.get_by_site(site_id)
        if schedule is None:
            raise AppError("График не загружен", status_code=404)

        # Получаем этапы графика
        stages = await self._schedule_repository.list_stages(schedule.id)

        # Получаем существующие правила для сайта
        existing_rules = await self._repository.list_rules_by_site(site_id)
        existing_stage_ids = {rule.stage_id for rule in existing_rules}

        # Проверяем, есть ли новые этапы, требующие материализации
        need_commit = False

        for stage in stages:
            if stage.id not in existing_stage_ids:
                # Найти совпадение со строкой по умолчанию
                default_rule = self._defaults.match_stage(stage.name)

                if default_rule is not None:
                    # Создать правило с наборами и требованиями
                    rule = MethodologyRule(
                        site_id=site_id,
                        stage_id=stage.id,
                        stage_key=default_rule.stage_key,
                        is_verifiable=True,
                    )
                    await self._repository.add(rule)

                    # Добавить наборы и требования
                    for set_idx, default_set in enumerate(default_rule.sets, start=1):
                        equipment_set = await self._repository.add_set(rule.id, set_idx)

                        # Разрешить коды оборудования в ID
                        requirements = []
                        for default_req in default_set:
                            # Найти оборудование по коду
                            equipment_type = await self._catalog.by_code(default_req.equipment_code)
                            if equipment_type is None:
                                raise AppError(
                                    f"Справочник техники не содержит {default_req.equipment_code}",
                                    status_code=500,
                                )

                            req = EquipmentRequirement(
                                set_id=equipment_set.id,
                                equipment_type_id=equipment_type.id,
                                min_count=default_req.min_count,
                                obligation=default_req.obligation,
                                gesn_code=default_req.gesn_code,
                                source_note=default_req.source_note,
                            )
                            requirements.append(req)

                        await self._repository.add_requirements(equipment_set.id, requirements)

                    need_commit = True
                else:
                    # Создать правило без наборов (не проверяется)
                    rule = MethodologyRule(
                        site_id=site_id,
                        stage_id=stage.id,
                        is_verifiable=False,
                        unverifiable_reason="Нет правила в базовом наборе — задайте комплект",
                    )
                    await self._repository.add(rule)
                    need_commit = True

        # Коммитим, если создали что-то новое
        if need_commit:
            await self._session.commit()

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

        # Преобразуем в схемы
        result: list[RuleRead] = []
        for rule in rules:
            # Найти этап
            found_stage = next((s for s in stages if s.id == rule.stage_id), None)
            stage_name: str | None = found_stage.name if found_stage else None

            # Собрать наборы
            rule_sets = sets_by_rule.get(rule.id, [])
            sets_read = []
            for s in rule_sets:
                reqs = requirements_by_set.get(s.id, [])
                req_reads = []
                for req in reqs:
                    # Загрузить тип оборудования
                    equipment_type = await self._catalog.by_id(req.equipment_type_id)
                    if equipment_type:
                        req_read = RequirementRead(
                            id=req.id,
                            equipment_type=equipment_type,
                            min_count=req.min_count,
                            obligation=Obligation(req.obligation),
                            gesn_code=req.gesn_code,
                            source_note=req.source_note,
                        )
                        req_reads.append(req_read)

                set_read = SetRead(
                    id=s.id,
                    position=s.position,
                    requirements=req_reads,
                )
                sets_read.append(set_read)

            # Сортируем наборы по позиции
            sets_read.sort(key=lambda s: s.position)

            rule_read = RuleRead(
                id=rule.id,
                stage_id=rule.stage_id,
                stage_name=stage_name,
                is_verifiable=rule.is_verifiable,
                unverifiable_reason=rule.unverifiable_reason,
                updated_at=rule.updated_at,
                sets=sets_read,
            )
            result.append(rule_read)

        # Сортируем по position этапов
        result.sort(key=lambda r: next((s.position for s in stages if s.id == r.stage_id), 999))

        return result

    async def update_rule(
        self, site_id: uuid.UUID, rule_id: uuid.UUID, data: RuleUpdate
    ) -> RuleRead:
        """Обновить правило.

        Args:
            site_id: ID сайта
            rule_id: ID правила
            data: RuleUpdate со значениями

        Returns:
            RuleRead

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

        # Возвращаем RuleRead
        rules = await self.list_rules(site_id)
        return next(r for r in rules if r.id == rule_id)

    async def create_set(self, site_id: uuid.UUID, rule_id: uuid.UUID, data: SetWrite) -> SetRead:
        """Создать набор требований.

        Args:
            site_id: ID сайта
            rule_id: ID правила
            data: SetWrite с требованиями

        Returns:
            SetRead

        Raises:
            AppError(404) если правило не принадлежит сайту
            AppError(422) если валидация требований не прошла
        """
        # Получить правило
        rule = await self._get_site_rule(site_id, rule_id)

        # Валидировать требования
        self._validate_requirements(data)

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

        # Возвращаем SetRead
        rules = await self.list_rules(site_id)
        rule_read = next(r for r in rules if r.id == rule_id)
        return next(s for s in rule_read.sets if s.id == equipment_set.id)

    async def replace_set(self, site_id: uuid.UUID, set_id: uuid.UUID, data: SetWrite) -> SetRead:
        """Заменить требования набора.

        Args:
            site_id: ID сайта
            set_id: ID набора
            data: SetWrite с новыми требованиями

        Returns:
            SetRead

        Raises:
            AppError(404) если набор не принадлежит сайту
            AppError(422) если валидация требований не прошла
        """
        # Получить набор
        equipment_set = await self._get_site_set(site_id, set_id)

        # Валидировать требования
        self._validate_requirements(data)

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

        # Возвращаем SetRead
        rules = await self.list_rules(site_id)
        rule_read = next(r for r in rules if r.id == equipment_set.rule_id)
        return next(s for s in rule_read.sets if s.id == set_id)

    async def delete_set(self, site_id: uuid.UUID, set_id: uuid.UUID) -> None:
        """Удалить набор.

        Args:
            site_id: ID сайта
            set_id: ID набора

        Raises:
            AppError(404) если набор не принадлежит сайту
        """
        # Получить набор
        equipment_set = await self._get_site_set(site_id, set_id)

        # Удалить набор (репо удалит требования)
        rule_id = equipment_set.rule_id
        await self._repository.delete_set(equipment_set)

        # Обновить updated_at правила
        rule = await self._session.get(MethodologyRule, rule_id)
        if rule:
            rule.updated_at = datetime.now(UTC)

        # Коммитим
        await self._session.commit()

        # Пересчитываем
        await self._recalculator.recalculate(site_id)

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
