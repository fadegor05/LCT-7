"""HTTP-роуты для управления фотографиями и детекциями."""

import uuid

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Header, UploadFile
from fastapi.responses import Response

from app.core.settings import Settings
from app.domains.photo.models import ProcessingStatus
from app.domains.photo.schemas import (
    DateUpdate,
    DetectBacklogReport,
    PhotoDetail,
    PhotoRead,
    UploadReport,
)
from app.domains.photo.service import PhotoService, UploadInput
from app.plugins.exceptions import AppError

router = APIRouter(prefix="/sites/{site_id}/photos", tags=["photos"])


@router.post("", status_code=201)
@inject
async def upload_photos(
    site_id: uuid.UUID,
    files: list[UploadFile],
    service: FromDishka[PhotoService],
    settings: FromDishka[Settings],
) -> UploadReport:
    """Загрузить пакет фотографий.

    Проверяет количество файлов перед чтением, затем валидирует каждый файл.
    Ошибка одного файла не влияет на остальные.

    Args:
        site_id: ID стройки
        files: Список файлов для загрузки
        service: Сервис фотографий
        settings: Настройки приложения

    Returns:
        UploadReport с результатами загрузки

    Raises:
        413: Слишком много файлов в пачке
        422: Список файлов пуст или другая ошибка валидации
    """
    # Проверяем количество файлов перед чтением
    if len(files) > settings.storage.max_batch_files:
        raise AppError(
            f"Слишком много файлов в пачке (максимум {settings.storage.max_batch_files})",
            status_code=413,
        )

    # Читаем содержимое файлов
    upload_inputs: list[UploadInput] = []
    for file in files:
        # Читаем с лимитом, чтобы не загружать слишком большой файл
        content = await file.read(settings.storage.max_upload_bytes + 1)
        filename = file.filename or ""
        content_type = file.content_type

        upload_inputs.append(
            UploadInput(filename=filename, content=content, content_type=content_type)
        )

    # Загружаем пакет
    report = await service.upload_batch(site_id, upload_inputs)
    return report


@router.post("/detect")
@inject
async def detect_backlog(
    site_id: uuid.UUID,
    service: FromDishka[PhotoService],
    status: str = "pending,failed",
) -> DetectBacklogReport:
    """Запустить детекцию для необработанных фотографий.

    Args:
        site_id: ID стройки
        status: Comma-separated статусы (pending, failed), по умолчанию оба
        service: Сервис фотографий

    Returns:
        DetectBacklogReport с результатами

    Raises:
        404: Сайт не найден или не принадлежит пользователю
        409: Детектор не настроен
        422: Некорректное значение статуса
    """
    # Парсим статусы
    status_values = set()
    for s in status.split(","):
        s = s.strip().lower()
        if s == "pending":
            status_values.add(ProcessingStatus.PENDING)
        elif s == "failed":
            status_values.add(ProcessingStatus.FAILED)
        else:
            raise AppError(f"Неизвестный статус: {s}", status_code=422)

    if not status_values:
        raise AppError("Нужно указать хотя бы один статус", status_code=422)

    return await service.detect_backlog(site_id, status_values)


@router.get("")
@inject
async def list_photos(
    site_id: uuid.UUID,
    service: FromDishka[PhotoService],
    undated: bool = False,
) -> list[PhotoRead]:
    """Получить список фотографий стройки.

    Args:
        site_id: ID стройки
        undated: Если True, возвращает только фотографии без даты
        service: Сервис фотографий

    Returns:
        Список PhotoRead

    Raises:
        404: Сайт не найден или не принадлежит текущему пользователю
    """
    photos = await service.list_photos(site_id, undated=undated)
    return photos


@router.get("/{photo_id}")
@inject
async def get_photo(
    site_id: uuid.UUID,
    photo_id: uuid.UUID,
    service: FromDishka[PhotoService],
) -> PhotoDetail:
    """Получить фотографию с детекциями.

    Args:
        site_id: ID стройки
        photo_id: ID фотографии
        service: Сервис фотографий

    Returns:
        PhotoDetail с детекциями

    Raises:
        404: Сайт не найден, не принадлежит пользователю или фотография не найдена
    """
    photo = await service.get_photo(site_id, photo_id)
    return photo


@router.patch("/{photo_id}/date")
@inject
async def update_photo_date(
    site_id: uuid.UUID,
    photo_id: uuid.UUID,
    data: DateUpdate,
    service: FromDishka[PhotoService],
) -> PhotoRead:
    """Установить дату съёмки вручную.

    Args:
        site_id: ID стройки
        photo_id: ID фотографии
        data: DateUpdate с новой датой
        service: Сервис фотографий

    Returns:
        PhotoRead с обновлённой фотографией

    Raises:
        404: Сайт не найден, не принадлежит пользователю или фотография не найдена
        422: Дата в будущем или другая ошибка валидации
    """
    photo = await service.set_date(site_id, photo_id, data.captured_on)
    return photo


@router.get("/{photo_id}/image")
@inject
async def get_photo_image(
    site_id: uuid.UUID,
    photo_id: uuid.UUID,
    service: FromDishka[PhotoService],
) -> Response:
    """Получить изображение фотографии.

    Args:
        site_id: ID стройки
        photo_id: ID фотографии
        service: Сервис фотографий

    Returns:
        Response с байтами изображения и правильным content-type

    Raises:
        404: Сайт не найден, не принадлежит пользователю, фотография не найдена
             или файл недоступен
    """
    content, content_type = await service.get_image(site_id, photo_id)

    return Response(
        content=content,
        media_type=content_type,
        headers={
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, max-age=86400, immutable",
        },
    )


@router.get("/{photo_id}/annotated")
@inject
async def get_annotated_image(
    site_id: uuid.UUID,
    photo_id: uuid.UUID,
    service: FromDishka[PhotoService],
    if_none_match: str | None = Header(default=None),
) -> Response:
    """Получить изображение с аннотациями детекций.

    Картинка рисуется один раз и кэшируется в хранилище (см.
    PhotoService.get_annotated). Браузер кэширует её по ETag: адрес один и тот
    же, а рамки меняются после переобнаружения, поэтому ответ всегда
    перепроверяется (no-cache), но при совпадении ETag уходит пустой 304.

    Args:
        site_id: ID стройки
        photo_id: ID фотографии
        service: Сервис фотографий
        if_none_match: Заголовок If-None-Match

    Returns:
        Response с JPEG байтами аннотированного изображения или 304

    Raises:
        404: Сайт не найден, не принадлежит пользователю, фотография не найдена
             или файл недоступен/повреждён
    """
    image = await service.get_annotated(site_id, photo_id, if_none_match)
    headers = {
        "ETag": image.etag,
        "Cache-Control": "private, no-cache",
        "X-Content-Type-Options": "nosniff",
    }
    if image.content is None:
        return Response(status_code=304, headers=headers)

    return Response(content=image.content, media_type=image.content_type, headers=headers)


@router.post("/{photo_id}/detect")
@inject
async def redetect_photo(
    site_id: uuid.UUID,
    photo_id: uuid.UUID,
    service: FromDishka[PhotoService],
) -> PhotoDetail:
    """Переобнаружить оборудование на фотографии.

    Запускает детектор заново, заменяя старые детекции если модель обновилась.

    Args:
        site_id: ID стройки
        photo_id: ID фотографии
        service: Сервис фотографий

    Returns:
        PhotoDetail с обновлёнными детекциями

    Raises:
        404: Сайт не найден, не принадлежит пользователю или фотография не найдена
        409: Детектор не настроен
        502: Детектор недоступен или вернул ошибку
    """
    photo = await service.redetect(site_id, photo_id)
    return photo
