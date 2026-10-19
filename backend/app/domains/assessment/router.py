"""HTTP-роуты для чтения статусов этапов и отклонений."""

import uuid

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from app.domains.assessment.schemas import (
    DecisionIn,
    DeviationDetailRead,
    DeviationRead,
    SiteSummaryRead,
    StageStatusRead,
)
from app.domains.assessment.service import AssessmentService
from app.domains.user.provider import CurrentUser

router = APIRouter(prefix="/sites/{site_id}/assessment", tags=["assessment"])


@router.get("/stages")
@inject
async def list_stage_statuses(
    site_id: uuid.UUID, service: FromDishka[AssessmentService]
) -> list[StageStatusRead]:
    """Получить список статусов этапов.

    Args:
        site_id: ID стройки
        service: Сервис оценки

    Returns:
        Список StageStatusRead, упорядочены по position

    Raises:
        404: Сайт не найден, не принадлежит пользователю или график не загружен
    """
    return await service.list_stage_statuses(site_id)


@router.get("/deviations")
@inject
async def list_deviations(
    site_id: uuid.UUID, service: FromDishka[AssessmentService]
) -> list[DeviationRead]:
    """Получить список отклонений.

    Args:
        site_id: ID стройки
        service: Сервис оценки

    Returns:
        Список DeviationRead, отсортирован по severity и дате

    Raises:
        404: Сайт не найден или не принадлежит пользователю
    """
    return await service.list_deviations(site_id)


@router.get("/deviations/{deviation_id}")
@inject
async def get_deviation(
    site_id: uuid.UUID, deviation_id: uuid.UUID, service: FromDishka[AssessmentService]
) -> DeviationDetailRead:
    """Получить отклонение с доказательствами.

    Args:
        site_id: ID стройки
        deviation_id: ID отклонения
        service: Сервис оценки

    Returns:
        DeviationDetailRead с доказательствами

    Raises:
        404: Сайт не найден, не принадлежит пользователю или отклонение не найдено
    """
    return await service.get_deviation(site_id, deviation_id)


@router.put("/deviations/{deviation_id}/decision")
@inject
async def decide(
    site_id: uuid.UUID,
    deviation_id: uuid.UUID,
    data: DecisionIn,
    service: FromDishka[AssessmentService],
    user: FromDishka[CurrentUser],
) -> DeviationDetailRead:
    """Решение инженера по гипотезе: подтвердить, отклонить или снять (`decision: null`).

    Подписывает вошедший пользователь. Отклонённая гипотеза уходит в архив: её нет в списках
    и в отчёте. Решение переживает пересчёт — оно хранится по ключу «тип:этап:машина».
    """
    return await service.decide(site_id, deviation_id, data, user)


@router.get("/summary")
@inject
async def get_summary(
    site_id: uuid.UUID, service: FromDishka[AssessmentService]
) -> SiteSummaryRead:
    """Получить сводку статуса стройки.

    Args:
        site_id: ID стройки
        service: Сервис оценки

    Returns:
        SiteSummaryRead с вердиктом (behind/no_deviations/insufficient_data)

    Raises:
        404: Сайт не найден или не принадлежит пользователю
    """
    return await service.get_summary(site_id)
