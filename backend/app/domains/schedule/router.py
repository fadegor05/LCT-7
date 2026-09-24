"""HTTP-роуты графика выполнения работ."""

import uuid

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, UploadFile

from app.domains.schedule.schemas import ScheduleReport, StageDatesUpdate, StageRead
from app.domains.schedule.service import ScheduleService

router = APIRouter(prefix="/sites/{site_id}/schedule", tags=["schedule"])


@router.post("/import", status_code=201)
@inject
async def import_schedule(
    site_id: uuid.UUID,
    file: UploadFile,
    service: FromDishka[ScheduleService],
) -> ScheduleReport:
    """Импортировать график из файла.

    Args:
        site_id: ID сайта
        file: Файл (CSV или XLSX)
        service: Сервис графика

    Returns:
        ScheduleReport с информацией об импорте

    Raises:
        404: Сайт не найден или не принадлежит текущему пользователю
        422: Ошибка формата файла или неподдерживаемое расширение
    """
    filename = file.filename or ""
    content = await file.read()
    report = await service.import_schedule(site_id, filename, content)
    return report


@router.get("")
@inject
async def get_schedule(site_id: uuid.UUID, service: FromDishka[ScheduleService]) -> ScheduleReport:
    """Получить отчёт о графике сайта.

    Args:
        site_id: ID сайта
        service: Сервис графика

    Returns:
        ScheduleReport

    Raises:
        404: Сайт не найден, не принадлежит текущему пользователю или график не загружен
    """
    report = await service.get_schedule(site_id)
    return report


@router.patch("/stages/{stage_id}")
@inject
async def update_stage_dates(
    site_id: uuid.UUID,
    stage_id: uuid.UUID,
    data: StageDatesUpdate,
    service: FromDishka[ScheduleService],
) -> StageRead:
    """Обновить даты этапа графика.

    Args:
        site_id: ID сайта
        stage_id: ID этапа
        data: Новые даты
        service: Сервис графика

    Returns:
        StageRead с обновлённым этапом

    Raises:
        404: Сайт не найден, не принадлежит текущему пользователю или этап не найден
        422: Ошибка валидации (end < start)
    """
    stage = await service.update_stage_dates(site_id, stage_id, data)
    return StageRead.model_validate(stage)
