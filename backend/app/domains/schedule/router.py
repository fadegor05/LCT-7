"""HTTP-роуты графика выполнения работ."""

import uuid
from typing import Annotated

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Form, UploadFile

from app.domains.schedule.models import ParseMode
from app.domains.schedule.schemas import ScheduleReport, StageDatesUpdate, StageRead
from app.domains.schedule.service import ScheduleService
from app.plugins.exceptions import AppError

router = APIRouter(prefix="/sites/{site_id}/schedule", tags=["schedule"])

# Максимальный размер загружаемого файла: 5 МБ
MAX_UPLOAD_BYTES = 5 * 1024 * 1024


@router.post("/import", status_code=201)
@inject
async def import_schedule(
    site_id: uuid.UUID,
    file: UploadFile,
    service: FromDishka[ScheduleService],
    mode: Annotated[ParseMode, Form()] = ParseMode.AUTO,
) -> ScheduleReport:
    """Импортировать график из файла.

    Args:
        site_id: ID сайта
        file: Файл (CSV или XLSX)
        mode: Режим разбора: auto (встроенный, при неудаче LLM), llm, builtin
        service: Сервис графика

    Returns:
        ScheduleReport с информацией об импорте

    Raises:
        404: Сайт не найден или не принадлежит текущему пользователю
        413: Файл слишком большой (более 5 МБ)
        422: Ошибка формата файла или неподдерживаемое расширение
        503/504: Выбран LLM-разбор, а модель недоступна или не ответила
    """
    filename = file.filename or ""
    # Читаем файл в chunks, проверяя размер
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise AppError("Файл слишком большой (максимум 5 МБ)", status_code=413)
    report = await service.import_schedule(site_id, filename, content, mode)
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
