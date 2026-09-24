"""HTTP-роуты методологии проверки оборудования на объекте строительства."""

import uuid

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from app.domains.methodology.models import Obligation
from app.domains.methodology.schemas import (
    EquipmentTypeRead,
    RequirementRead,
    RuleRead,
    RuleUpdate,
    SetRead,
    SetWrite,
)
from app.domains.methodology.service import (
    MethodologyService,
    RequirementView,
    RuleView,
    SetView,
)


# Mapper functions to convert views to schemas
def _requirement_view_to_read(view: RequirementView) -> RequirementRead:
    """Convert RequirementView to RequirementRead."""
    return RequirementRead(
        id=view.requirement.id,
        equipment_type=EquipmentTypeRead(
            id=view.equipment_type.id,
            code=view.equipment_type.code,
            title=view.equipment_type.title,
            synonyms=list(view.equipment_type.synonyms),
        ),
        min_count=view.requirement.min_count,
        obligation=Obligation(view.requirement.obligation),
        gesn_code=view.requirement.gesn_code,
        source_note=view.requirement.source_note,
    )


def _set_view_to_read(view: SetView) -> SetRead:
    """Convert SetView to SetRead."""
    return SetRead(
        id=view.equipment_set.id,
        position=view.equipment_set.position,
        requirements=[_requirement_view_to_read(r) for r in view.requirements],
    )


def _rule_view_to_read(view: RuleView) -> RuleRead:
    """Convert RuleView to RuleRead."""
    return RuleRead(
        id=view.rule.id,
        stage_id=view.rule.stage_id,
        stage_name=view.stage_name,
        is_verifiable=view.rule.is_verifiable,
        unverifiable_reason=view.rule.unverifiable_reason,
        updated_at=view.rule.updated_at,
        sets=[_set_view_to_read(s) for s in view.sets],
    )


# Основной роутер для методологии
router = APIRouter(tags=["methodology"])

# Роутер для оборудования (выделен отдельно, но можно включить в основной)
equipment_router = APIRouter(prefix="/equipment-types", tags=["equipment"])


@equipment_router.get("")
@inject
async def list_equipment_types(
    service: FromDishka[MethodologyService],
) -> list[EquipmentTypeRead]:
    """Получить все типы оборудования из каталога.

    Returns:
        list[EquipmentTypeRead]

    Raises:
        500: Внутренняя ошибка при загрузке каталога
    """
    equipment_infos = await service.list_equipment_types()
    return [
        EquipmentTypeRead(
            id=info.id,
            code=info.code,
            title=info.title,
            synonyms=list(info.synonyms),
        )
        for info in equipment_infos
    ]


@router.get("/sites/{site_id}/methodology")
@inject
async def list_methodology(
    site_id: uuid.UUID,
    service: FromDishka[MethodologyService],
) -> list[RuleRead]:
    """Получить правила методологии для сайта с ленивой материализацией.

    Args:
        site_id: ID сайта
        service: Сервис методологии

    Returns:
        list[RuleRead] упорядочены по position этапа

    Raises:
        404: Сайт не найден, не принадлежит текущему пользователю или график не загружен
    """
    rule_views = await service.list_rules(site_id)
    return [_rule_view_to_read(view) for view in rule_views]


@router.patch("/sites/{site_id}/methodology/rules/{rule_id}")
@inject
async def update_rule(
    site_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: RuleUpdate,
    service: FromDishka[MethodologyService],
) -> RuleRead:
    """Обновить правило методологии (проверяемость и причину).

    Args:
        site_id: ID сайта
        rule_id: ID правила
        data: RuleUpdate с is_verifiable и unverifiable_reason
        service: Сервис методологии

    Returns:
        RuleRead

    Raises:
        404: Сайт не найден, не принадлежит текущему пользователю или правило не найдено
        422: Ошибка валидации (unverifiable без reason, пустой reason)
    """
    rule_view = await service.update_rule(site_id, rule_id, data)
    return _rule_view_to_read(rule_view)


@router.post("/sites/{site_id}/methodology/rules/{rule_id}/sets", status_code=201)
@inject
async def create_set(
    site_id: uuid.UUID,
    rule_id: uuid.UUID,
    data: SetWrite,
    service: FromDishka[MethodologyService],
) -> SetRead:
    """Создать новый набор требований для правила.

    Args:
        site_id: ID сайта
        rule_id: ID правила
        data: SetWrite с требованиями (минимум одно нормативное требование)
        service: Сервис методологии

    Returns:
        SetRead

    Raises:
        404: Сайт не найден, не принадлежит текущему пользователю или правило не найдено
        422: Ошибка валидации:
            - Нет нормативных требований (только логические)
            - Неизвестный equipment_type_id
            - min_count < 1
            - Требование без gesn_code и source_note
            - Пустой список требований
    """
    set_view = await service.create_set(site_id, rule_id, data)
    return _set_view_to_read(set_view)


@router.put("/sites/{site_id}/methodology/sets/{set_id}")
@inject
async def replace_set(
    site_id: uuid.UUID,
    set_id: uuid.UUID,
    data: SetWrite,
    service: FromDishka[MethodologyService],
) -> SetRead:
    """Заменить требования набора.

    Args:
        site_id: ID сайта
        set_id: ID набора
        data: SetWrite с новыми требованиями
        service: Сервис методологии

    Returns:
        SetRead

    Raises:
        404: Сайт не найден, не принадлежит текущему пользователю или набор не найден
        422: Ошибка валидации (как в create_set)
    """
    set_view = await service.replace_set(site_id, set_id, data)
    return _set_view_to_read(set_view)


@router.delete("/sites/{site_id}/methodology/sets/{set_id}", status_code=204)
@inject
async def delete_set(
    site_id: uuid.UUID,
    set_id: uuid.UUID,
    service: FromDishka[MethodologyService],
) -> None:
    """Удалить набор требований.

    Args:
        site_id: ID сайта
        set_id: ID набора
        service: Сервис методологии

    Raises:
        404: Сайт не найден, не принадлежит текущему пользователю или набор не найден
    """
    await service.delete_set(site_id, set_id)
