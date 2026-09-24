"""HTTP-роуты для управления наблюдениями."""

import uuid
from datetime import date

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from app.domains.observation.schemas import ObservationRead
from app.domains.observation.service import ObservationService

router = APIRouter(prefix="/sites/{site_id}/observations", tags=["observations"])


@router.get("")
@inject
async def list_observations(
    site_id: uuid.UUID, service: FromDishka[ObservationService]
) -> list[ObservationRead]:
    """Получить список наблюдений стройки.

    Args:
        site_id: ID стройки
        service: Сервис наблюдений

    Returns:
        Список ObservationRead

    Raises:
        404: Сайт не найден или не принадлежит текущему пользователю
    """
    return await service.list_observations(site_id)


@router.get("/{observed_on}")
@inject
async def get_observation(
    site_id: uuid.UUID, observed_on: date, service: FromDishka[ObservationService]
) -> ObservationRead:
    """Получить наблюдение за конкретную дату.

    Args:
        site_id: ID стройки
        observed_on: Дата наблюдения
        service: Сервис наблюдений

    Returns:
        ObservationRead

    Raises:
        404: Сайт не найден, не принадлежит пользователю или наблюдение не найдено
    """
    return await service.get_observation(site_id, observed_on)
