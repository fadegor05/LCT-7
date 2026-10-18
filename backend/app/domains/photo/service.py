"""Бизнес-логика загрузки фотографий и детекций оборудования."""

import asyncio
import hashlib
import logging
import os
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ml.base import (
    DetectionResult,
    DetectorClient,
    DetectorError,
)
from app.adapters.storage.base import FileStorage, StorageError
from app.core.settings import Settings
from app.domains.camera.models import Camera
from app.domains.camera.zone import bbox_in_zone
from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.photo.date_resolver import (
    DateResolver,
    InvalidImageError,
    read_image_info,
)
from app.domains.photo.models import DateSource, Detection, Photo, ProcessingStatus
from app.domains.photo.recalculator import ObservationRecalculator
from app.domains.photo.render import RENDER_VERSION, render_annotated
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.photo.schemas import (
    DetectBacklogReport,
    DetectionRead,
    PhotoDetail,
    PhotoRead,
    UploadItem,
    UploadReport,
)
from app.domains.site.guard import SiteAccessGuard
from app.plugins.exceptions import AppError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadInput:
    """Входные данные для загрузки файла."""

    filename: str
    content: bytes
    content_type: str | None


@dataclass(frozen=True)
class AnnotatedImage:
    """Аннотированный снимок. content=None — у клиента актуальная версия (304)."""

    etag: str
    content: bytes | None
    content_type: str = "image/jpeg"


class PhotoService:
    """Бизнес-логика работы с фотографиями и детекциями."""

    def __init__(
        self,
        repository: PhotoRepository,
        detections: DetectionRepository,
        session: AsyncSession,
        guard: SiteAccessGuard,
        storage: FileStorage,
        detector: DetectorClient,
        resolver: DateResolver,
        catalog: EquipmentCatalog,
        settings: Settings,
        recalculator: ObservationRecalculator,
    ) -> None:
        self._repository = repository
        self._detections = detections
        self._session = session
        self._guard = guard
        self._storage = storage
        self._detector = detector
        self._resolver = resolver
        self._catalog = catalog
        self._settings = settings
        self._recalculator = recalculator

    async def upload_batch(
        self,
        site_id: uuid.UUID,
        files: Sequence[UploadInput],
        camera_id: uuid.UUID | None = None,
    ) -> UploadReport:
        """Загрузить пакет фотографий.

        Проверяет доступ к сайту, валидирует файлы (размер, формат, целостность).
        Обрабатывает файлы независимо: ошибка в одном не прерывает остальные.
        Для каждого файла: загружает в хранилище, создаёт Photo, запускает детекцию.
        После всех файлов: применяет NEIGHBOURS дейтинг для undated photos в батче.

        Args:
            site_id: ID стройки
            files: Список файлов для загрузки
            camera_id: Камера, с которой снят пакет; None — загружено вручную

        Returns:
            UploadReport с результатами

        Raises:
            AppError(404) если сайт не принадлежит пользователю
            AppError(404) если камера не найдена на этом объекте
            AppError(422) если список пуст
            AppError(413) если файлов больше лимита
        """
        # Проверка доступа
        await self._guard.require(site_id)

        # Валидация списка
        if not files:
            raise AppError("Не выбрано ни одного файла", status_code=422)

        if len(files) > self._settings.storage.max_batch_files:
            raise AppError(
                f"Максимум {self._settings.storage.max_batch_files} файлов за раз",
                status_code=413,
            )

        if camera_id is not None:
            await self._require_camera(site_id, camera_id)

        items: list[UploadItem] = []
        batch_photo_ids: list[uuid.UUID] = []

        # Обрабатываем файлы в порядке
        for file_input in files:
            item = await self._process_single_file(site_id, file_input, camera_id)
            items.append(item)
            if item.photo is not None:
                batch_photo_ids.append(item.photo.id)

        # Neighbour step: найти фото в батче без даты и проставить дату от соседей
        if batch_photo_ids:
            await self._apply_neighbours_dating(site_id, batch_photo_ids)
            await self._session.flush()
            await self._session.commit()

        # Reload photos from DB to get updated dates after neighbours dating
        final_items: list[UploadItem] = []
        for item in items:
            if item.photo is not None:
                photo = await self._repository.get(item.photo.id)
                if photo:
                    photo_read = PhotoRead.model_validate(photo)
                    final_items.append(
                        UploadItem(filename=item.filename, photo=photo_read, error=None)
                    )
                else:
                    final_items.append(item)
            else:
                final_items.append(item)

        uploaded = sum(1 for item in final_items if item.photo is not None)
        failed = sum(1 for item in final_items if item.error is not None)

        # Trigger observation recomputation for each distinct date (in sorted order for determinism)
        dates_to_recompute = {
            item.photo.captured_on
            for item in final_items
            if item.photo is not None and item.photo.captured_on is not None
        }
        for date_value in sorted(dates_to_recompute):
            try:
                await self._recalculator.recompute(site_id, date_value)
            except Exception:
                logger.exception("Ошибка при пересчёте наблюдений после загрузки фото")
                await self._session.rollback()

        return UploadReport(items=final_items, uploaded=uploaded, failed=failed)

    async def _require_camera(self, site_id: uuid.UUID, camera_id: uuid.UUID) -> None:
        """Камера должна существовать и принадлежать тому же объекту."""
        camera = await self._session.get(Camera, camera_id)
        if camera is None or camera.site_id != site_id:
            raise AppError("Камера не найдена", status_code=404)

    async def _process_single_file(
        self, site_id: uuid.UUID, file_input: UploadInput, camera_id: uuid.UUID | None = None
    ) -> UploadItem:
        """Обработать один файл: валидация, загрузка, создание Photo, детекция.

        Ошибка на любом этапе становится UploadItem.error.
        Если storage.put успешен, но DB write/commit не удалась - удаляем из storage.

        Args:
            site_id: ID стройки
            file_input: Входные данные файла
            camera_id: Камера снимка; None — загружено вручную

        Returns:
            UploadItem с результатом
        """
        # Шаг (a): Размер и пустой контент
        if len(file_input.content) > self._settings.storage.max_upload_bytes:
            return UploadItem(
                filename=file_input.filename,
                photo=None,
                error=f"Файл слишком большой (макс {self._settings.storage.max_upload_mb:g} МБ)",
            )

        if not file_input.content:
            return UploadItem(
                filename=file_input.filename,
                photo=None,
                error="Файл пуст",
            )

        # Шаг (b): Валидация изображения и определение формата
        try:
            info = await asyncio.to_thread(read_image_info, file_input.content)
        except InvalidImageError:
            logger.info("Файл %s не является корректным изображением", file_input.filename)
            return UploadItem(
                filename=file_input.filename,
                photo=None,
                error="Файл не является корректным изображением",
            )

        # Проверяем формат
        allowed_formats = {"JPEG", "PNG", "WEBP"}
        if info.format not in allowed_formats:
            return UploadItem(
                filename=file_input.filename,
                photo=None,
                error=f"Неподдерживаемый формат: {info.format}",
            )

        # Шаг (c): Разрешение даты
        try:
            resolved_date = await self._resolver.resolve(
                file_input.content, filename=file_input.filename
            )
        except InvalidImageError:
            logger.warning("Не удалось определить дату для %s", file_input.filename)
            return UploadItem(
                filename=file_input.filename,
                photo=None,
                error="Не удалось определить дату снимка",
            )

        # Шаг (d): Загрузка в storage
        photo_id = uuid.uuid4()
        ext = self._get_extension_from_format(info.format)
        content_type = self._get_content_type_from_format(info.format)
        storage_key = f"sites/{site_id}/photos/{photo_id}{ext}"

        try:
            await self._storage.put(storage_key, file_input.content, content_type)
        except StorageError:
            logger.exception("Не удалось сохранить файл в хранилище")
            return UploadItem(
                filename=file_input.filename,
                photo=None,
                error="Не удалось сохранить файл",
            )

        # Шаг (e): Создание Photo и flush
        original_name = os.path.basename(file_input.filename)[:255]
        photo = Photo(
            id=photo_id,
            site_id=site_id,
            storage_key=storage_key,
            original_name=original_name,
            width=info.width,
            height=info.height,
            captured_on=resolved_date.captured_on,
            date_source=resolved_date.source.value if resolved_date.source else None,
            processing_status=ProcessingStatus.PENDING.value,
            camera_id=camera_id,
        )

        self._session.add(photo)

        # Шаги (f) и (g): детекция и коммит. Ошибка БД на любом из них — ошибка этого
        # файла, а не 500 на всю пачку.
        try:
            # Вставить снимок до детекций: relationship между ними нет, и в общем flush
            # SQLAlchemy может записать детекции первыми — Postgres отклонит их по FK.
            await self._session.flush()
            await self._run_detection(photo, file_input.content, file_input.filename, content_type)
            await self._session.commit()
        except Exception:
            logger.exception("Не удалось сохранить снимок в БД")
            await self._session.rollback()
            # Удаляем файл из storage
            try:
                await self._storage.delete(storage_key)
            except StorageError:
                logger.warning("Не удалось удалить %s из хранилища после ошибки БД", storage_key)
            return UploadItem(
                filename=file_input.filename,
                photo=None,
                error="Ошибка сохранения снимка",
            )

        # Возвращаем успешный результат
        photo_read = PhotoRead.model_validate(photo)
        return UploadItem(filename=file_input.filename, photo=photo_read, error=None)

    async def _apply_result(
        self, photo: Photo, result: DetectionResult, *, keep_same_version: bool
    ) -> bool:
        """Применить результат детекции к фотографии.

        Создаёт Detection rows из результата, с семантикой keep vs replace для версий.
        Если keep_same_version=True и result.model_version совпадает с существующей версией,
        не заменяет детекции. Если keep_same_version=False, всегда заменяет (удаляет старые).

        Логирует warning если result.width/height отличаются от photo.width/height.

        Args:
            photo: Photo объект для обновления
            result: DetectionResult с детекциями
            keep_same_version: True — сохранить если версия совпадает; False — всегда заменить

        Returns:
            True если были обработаны новые детекции, False если сохранены старые
        """
        # Предупреждение о несовпадении размеров
        if (
            result.width is not None
            and result.height is not None
            and (result.width != photo.width or result.height != photo.height)
        ):
            logger.warning(
                "Размер изображения %s отличается: photo (%sx%s) vs result (%sx%s)",
                photo.original_name,
                photo.width,
                photo.height,
                result.width,
                result.height,
            )

        # Если keep_same_version=True, проверяем наличие версии
        if keep_same_version:
            existing_versions = await self._detections.model_versions(photo.id)
            if result.model_version in existing_versions:
                # Сохраняем существующие детекции
                photo.processing_status = ProcessingStatus.DONE.value
                return False
            # Разные версии - заменяем детекции
            await self._detections.delete_by_photo(photo.id)
        # Если keep_same_version=False (upload path), детекции ещё не созданы, нечего удалять

        # Обрабатываем новые детекции
        detection_objects = []
        for raw_det in result.detections:
            equipment_type = await self._catalog.by_code(raw_det.class_ours)
            if equipment_type is None:
                logger.warning(f"Неизвестный класс оборудования: {raw_det.class_ours}")
                continue

            detection = Detection(
                photo_id=photo.id,
                equipment_type_id=equipment_type.id,
                bbox=[raw_det.bbox[0], raw_det.bbox[1], raw_det.bbox[2], raw_det.bbox[3]],
                score=raw_det.conf,
                model_version=result.model_version,
            )
            detection_objects.append(detection)

        # Создаём rows
        if detection_objects:
            await self._detections.add_many(detection_objects)

        # Статус done даже если 0 детекций
        photo.processing_status = ProcessingStatus.DONE.value
        return True

    async def _run_detection(
        self, photo: Photo, content: bytes, filename: str, content_type: str | None
    ) -> None:
        """Запустить детекцию для фотографии.

        None -> остаток Photo в pending.
        DetectionResult -> создать Detection rows, статус done.
        DetectorError -> логировать warning, статус failed.
        Другие исключения -> логировать exception, статус failed.

        Не флашит сам: модифицирует объекты, флаш происходит в caller.

        Args:
            photo: Photo объект
            content: Байты изображения
            filename: Имя файла для логирования
            content_type: MIME-тип
        """
        try:
            result = await self._detector.detect(content, filename, content_type)
        except DetectorError as e:
            logger.warning(f"Детектор вернул ошибку для {filename}: {e} (transient={e.transient})")
            photo.processing_status = ProcessingStatus.FAILED.value
            return
        except Exception as e:
            logger.exception(f"Неожиданная ошибка детектора для {filename}: {e}")
            photo.processing_status = ProcessingStatus.FAILED.value
            return

        if result is None:
            # Детектор отключен - оставляем в pending
            return

        await self._apply_result(photo, result, keep_same_version=False)

    async def _apply_neighbours_dating(
        self, site_id: uuid.UUID, batch_photo_ids: list[uuid.UUID]
    ) -> None:
        """Применить NEIGHBOURS дейтинг для undated фото батче.

        Для каждого undated фото в батче найти ближайшее dated фото (по позиции),
        предпочитая более ранний по tie. Никагда не цепляться от другого neighbours
        датированного фото.

        Args:
            site_id: ID стройки
            batch_photo_ids: Список photo_id в порядке батча
        """
        if not batch_photo_ids:
            return

        # Получаем все фото батча из БД (в порядке, соответствующем batch_photo_ids)
        batch_photos = {}
        for photo_id in batch_photo_ids:
            photo = await self._repository.get(photo_id)
            if photo:
                batch_photos[photo_id] = photo

        # Находим undated photos в батче (в порядке батча)
        undated = [
            (i, batch_photos[pid])
            for i, pid in enumerate(batch_photo_ids)
            if pid in batch_photos and batch_photos[pid].captured_on is None
        ]
        if not undated:
            return

        # Для каждого undated найти соседа с датой (из NON-NEIGHBOURS источника)
        for undated_idx, undated_photo in undated:
            # Ищем ближайшего dated в батче
            best_photo = None
            best_distance = float("inf")
            best_idx = -1

            for batch_idx, pid in enumerate(batch_photo_ids):
                if pid not in batch_photos:
                    continue

                dated_photo = batch_photos[pid]

                # Пропускаем сам себя и undated
                if dated_photo.captured_on is None:
                    continue
                # Пропускаем NEIGHBOURS-датированные фото
                if dated_photo.date_source == DateSource.NEIGHBOURS.value:
                    continue

                distance = abs(batch_idx - undated_idx)
                # Предпочитаем более близкий, и на tie предпочитаем более ранний (меньший индекс)
                if distance < best_distance or (
                    distance == best_distance and (best_photo is None or batch_idx < best_idx)
                ):
                    best_photo = dated_photo
                    best_distance = distance
                    best_idx = batch_idx

            # Применяем дату от соседа (flush будет в caller)
            if best_photo:
                undated_photo.captured_on = best_photo.captured_on
                undated_photo.date_source = DateSource.NEIGHBOURS.value

    async def list_photos(self, site_id: uuid.UUID, undated: bool = False) -> list[PhotoRead]:
        """Получить список фотографий стройки.

        Args:
            site_id: ID стройки
            undated: Если True, возвращает только undated photos

        Returns:
            Список PhotoRead

        Raises:
            AppError(404) если сайт не принадлежит пользователю
        """
        await self._guard.require(site_id)
        photos = await self._repository.list_by_site(site_id, undated=undated)
        return [PhotoRead.model_validate(p) for p in photos]

    async def get_photo(self, site_id: uuid.UUID, photo_id: uuid.UUID) -> PhotoDetail:
        """Получить фотографию с детекциями.

        Обогащает детекции кодом и названием оборудования.

        Args:
            site_id: ID стройки
            photo_id: ID фотографии

        Returns:
            PhotoDetail с детекциями

        Raises:
            AppError(404) если сайт не принадлежит пользователю
            AppError(404) если фотография не найдена
        """
        await self._guard.require(site_id)

        photo = await self._repository.get_in_site(site_id, photo_id)
        if photo is None:
            raise AppError("Снимок не найден", status_code=404)

        # Получаем детекции
        detections_db = await self._detections.list_by_photo(photo_id)

        # Зона камеры снимка (одна выборка на фото); без камеры или зоны — in_zone не считаем
        zone = None
        if photo.camera_id is not None:
            camera = await self._session.get(Camera, photo.camera_id)
            zone = camera.zone if camera is not None else None

        # Обогащаем детекции кодом и названием оборудования
        detections_read = []
        for det in detections_db:
            equipment = await self._catalog.by_id(det.equipment_type_id)
            if equipment is None:
                # Неизвестная техника
                det_read = DetectionRead(
                    id=det.id,
                    equipment_type_id=det.equipment_type_id,
                    equipment_code="unknown",
                    equipment_title="Неизвестная техника",
                    bbox=det.bbox,
                    score=det.score,
                    model_version=det.model_version,
                    in_zone=bbox_in_zone(det.bbox, zone),
                )
            else:
                det_read = DetectionRead(
                    id=det.id,
                    equipment_type_id=det.equipment_type_id,
                    equipment_code=equipment.code,
                    equipment_title=equipment.title,
                    bbox=det.bbox,
                    score=det.score,
                    model_version=det.model_version,
                    in_zone=bbox_in_zone(det.bbox, zone),
                )
            detections_read.append(det_read)

        return PhotoDetail(
            id=photo.id,
            site_id=photo.site_id,
            original_name=photo.original_name,
            width=photo.width,
            height=photo.height,
            captured_on=photo.captured_on,
            date_source=photo.date_source,
            processing_status=photo.processing_status,
            uploaded_at=photo.uploaded_at,
            camera_id=photo.camera_id,
            detections=detections_read,
        )

    async def set_date(
        self, site_id: uuid.UUID, photo_id: uuid.UUID, captured_on: date
    ) -> PhotoRead:
        """Установить дату съёмки вручную.

        Args:
            site_id: ID стройки
            photo_id: ID фотографии
            captured_on: Дата съёмки

        Returns:
            PhotoRead

        Raises:
            AppError(404) если сайт не принадлежит пользователю
            AppError(404) если фотография не найдена
            AppError(422) если дата в будущем
        """
        await self._guard.require(site_id)

        # Проверяем будущую дату
        if captured_on > date.today():
            raise AppError("Дата не может быть в будущем", status_code=422)

        photo = await self._repository.get_in_site(site_id, photo_id)
        if photo is None:
            raise AppError("Снимок не найден", status_code=404)

        # Capture old date before mutation
        old_date = photo.captured_on

        photo.captured_on = captured_on
        photo.date_source = DateSource.MANUAL.value
        await self._session.commit()

        # Build response BEFORE calling recalculator hook to avoid session poisoning
        photo_read = PhotoRead.model_validate(photo)

        # Trigger observation recomputation for new and old dates
        try:
            await self._recalculator.recompute(site_id, captured_on)
            if old_date is not None and old_date != captured_on:
                await self._recalculator.recompute(site_id, old_date)
        except Exception:
            logger.exception("Ошибка при пересчёте наблюдений после изменения даты фото")
            await self._session.rollback()

        return photo_read

    async def get_image(self, site_id: uuid.UUID, photo_id: uuid.UUID) -> tuple[bytes, str]:
        """Получить байты изображения и его MIME-тип.

        Args:
            site_id: ID стройки
            photo_id: ID фотографии

        Returns:
            Tuple (bytes, content_type)

        Raises:
            AppError(404) если сайт не принадлежит пользователю
            AppError(404) если фотография не найдена или файл недоступен
        """
        await self._guard.require(site_id)

        photo = await self._repository.get_in_site(site_id, photo_id)
        if photo is None:
            raise AppError("Снимок не найден", status_code=404)

        try:
            content = await self._storage.get(photo.storage_key)
        except StorageError as e:
            raise AppError("Файл снимка недоступен", status_code=404) from e

        # Определяем content-type по расширению
        content_type = self._get_content_type_from_key(photo.storage_key)
        return content, content_type

    async def get_annotated(
        self,
        site_id: uuid.UUID,
        photo_id: uuid.UUID,
        if_none_match: str | None = None,
    ) -> AnnotatedImage:
        """Получить снимок с нарисованными рамками детекций.

        Отрисовка полноразмерного фото дорогая, поэтому результат кэшируется
        в хранилище под ключом, зависящим от детекций и версии рендера:
        переобнаружение даёт новый ключ, и устаревшая картинка не отдаётся.
        Тот же отпечаток служит ETag — если он совпал с If-None-Match,
        хранилище не трогаем вовсе.

        Args:
            site_id: ID стройки
            photo_id: ID фотографии
            if_none_match: Значение заголовка If-None-Match от клиента

        Returns:
            AnnotatedImage (content=None, если у клиента актуальная версия)

        Raises:
            AppError(404) если сайт/фотография не найдены или файл недоступен
        """
        photo = await self.get_photo(site_id, photo_id)
        storage_key = await self._storage_key(site_id, photo_id)

        fingerprint = hashlib.sha256(
            "|".join(
                [RENDER_VERSION, storage_key]
                + sorted(
                    f"{d.equipment_code}:{','.join(f'{v:.6f}' for v in d.bbox)}:{d.score:.4f}"
                    for d in photo.detections
                )
            ).encode()
        ).hexdigest()[:32]
        etag = f'"{fingerprint}"'

        if if_none_match and etag in [t.strip() for t in if_none_match.split(",")]:
            return AnnotatedImage(etag=etag, content=None)

        cache_key = f"sites/{site_id}/annotated/{photo_id}/{fingerprint}.jpg"
        try:
            return AnnotatedImage(etag=etag, content=await self._storage.get(cache_key))
        except StorageError:
            pass  # промах кэша — рисуем

        try:
            original = await self._storage.get(storage_key)
        except StorageError as e:
            raise AppError("Файл снимка недоступен", status_code=404) from e

        try:
            content, content_type = await asyncio.to_thread(
                render_annotated, original, photo.detections
            )
        except InvalidImageError as e:
            raise AppError("Файл снимка недоступен", status_code=404) from e

        try:
            await self._storage.put(cache_key, content, content_type)
        except StorageError:
            # Кэш — оптимизация: ошибка записи не должна ломать ответ
            logger.warning("Не удалось сохранить аннотированный снимок %s в кэш", cache_key)

        return AnnotatedImage(etag=etag, content=content, content_type=content_type)

    async def _storage_key(self, site_id: uuid.UUID, photo_id: uuid.UUID) -> str:
        """Ключ оригинала в хранилище (доступ к стройке уже проверен вызывающим)."""
        photo = await self._repository.get_in_site(site_id, photo_id)
        if photo is None:
            raise AppError("Снимок не найден", status_code=404)
        return photo.storage_key

    async def detect_backlog(
        self, site_id: uuid.UUID, statuses: set[ProcessingStatus]
    ) -> DetectBacklogReport:
        """Запустить детекцию для всех необработанных фотографий.

        Если детектор не настроен (не configured) → AppError 409 «Детектор не настроен».
        Итерирует фотографии со статусами из `statuses`, загружает из storage, запускает detect.
        - StorageError → photo failed
        - DetectorError → photo failed; после первой transient ошибки прекращает вызовы детектора
          и считает оставшиеся as skipped
        - Success → apply result с replace semantics и mark done
        - Каждую фотографию коммитит отдельно

        После цикла пересчитывает observations один раз per distinct captured_on (sorted),
        same error handling as upload_batch.

        processed = done + failed.

        Args:
            site_id: ID стройки
            statuses: Набор статусов для обработки (напр. {pending, failed})

        Returns:
            DetectBacklogReport {processed, done, failed, skipped}

        Raises:
            AppError(404) если сайт не принадлежит пользователю
            AppError(409) если детектор не настроен
        """
        await self._guard.require(site_id)

        # Проверяем, что детектор настроен
        if not self._detector.configured:
            raise AppError("Детектор не настроен", status_code=409)

        # Получаем список фотографий для обработки
        status_values = {s.value for s in statuses}
        photos = await self._repository.list_by_status(site_id, status_values)

        done = 0
        failed = 0
        skipped = 0
        detector_down = False

        # Обрабатываем каждую фотографию
        for photo in photos:
            if detector_down:
                # После первой transient ошибки пропускаем остальные
                skipped += 1
                continue

            # Получаем байты из storage
            try:
                content = await self._storage.get(photo.storage_key)
            except StorageError:
                logger.exception(f"Не удалось загрузить {photo.original_name} из хранилища")
                photo.processing_status = ProcessingStatus.FAILED.value
                failed += 1
                await self._session.commit()
                continue

            # Попытка заполнить дату из штампа, если фото без даты (LCT-13)
            if photo.captured_on is None:
                try:
                    resolved = await self._resolver.resolve(content, filename=photo.original_name)
                except InvalidImageError:
                    resolved = None
                if resolved is not None and resolved.captured_on is not None:
                    photo.captured_on = resolved.captured_on
                    photo.date_source = resolved.source.value if resolved.source else None

            # Запускаем детекцию
            try:
                result = await self._detector.detect(content, photo.original_name, None)
            except DetectorError as e:
                logger.warning(
                    f"Детектор вернул ошибку для {photo.original_name}: {e} "
                    f"(transient={e.transient})"
                )
                photo.processing_status = ProcessingStatus.FAILED.value
                failed += 1
                if e.transient:
                    detector_down = True
                    skipped += len(photos) - (done + failed + skipped + 1)
                await self._session.commit()
                continue
            except Exception as e:
                logger.exception(f"Неожиданная ошибка детектора для {photo.original_name}: {e}")
                photo.processing_status = ProcessingStatus.FAILED.value
                failed += 1
                await self._session.commit()
                continue

            # Если детектор отключен, оставляем в текущем статусе
            if result is None:
                await self._session.commit()
                continue

            # Применяем результат с keep-if-same-version семантикой
            await self._apply_result(photo, result, keep_same_version=True)
            done += 1
            await self._session.commit()

        # Пересчитываем observations для всех затронутых дат
        dates_to_recompute = {
            photo.captured_on for photo in photos if photo.captured_on is not None
        }
        for date_value in sorted(dates_to_recompute):
            try:
                await self._recalculator.recompute(site_id, date_value)
            except Exception:
                logger.exception("Ошибка при пересчёте наблюдений после detect_backlog")
                await self._session.rollback()

        processed = done + failed

        return DetectBacklogReport(processed=processed, done=done, failed=failed, skipped=skipped)

    async def redetect(self, site_id: uuid.UUID, photo_id: uuid.UUID) -> PhotoDetail:
        """Переобнаружить оборудование на фотографии.

        Если детектор вернёт result с тем же model_version,
        то сохраняем существующие detections (не заменяем).
        Если другой model_version - заменяем все detections новыми.

        Args:
            site_id: ID стройки
            photo_id: ID фотографии

        Returns:
            PhotoDetail с обновленными детекциями

        Raises:
            AppError(404) если сайт не принадлежит пользователю
            AppError(404) если фотография не найдена
            AppError(409) если детектор не настроен (вернул None)
            AppError(502) если детектор вернул ошибку
        """
        await self._guard.require(site_id)

        photo = await self._repository.get_in_site(site_id, photo_id)
        if photo is None:
            raise AppError("Снимок не найден", status_code=404)

        # Получаем байты из storage
        try:
            content = await self._storage.get(photo.storage_key)
        except StorageError as e:
            raise AppError("Файл снимка недоступен", status_code=404) from e

        # Запускаем детекцию
        try:
            result = await self._detector.detect(content, photo.original_name, None)
        except DetectorError as e:
            logger.exception(f"Детектор недоступен для {photo.original_name}: {e}")
            raise AppError("Детектор недоступен", status_code=502) from e
        except Exception as e:
            logger.exception(f"Неожиданная ошибка детектора: {e}")
            raise AppError("Детектор недоступен", status_code=502) from e

        if result is None:
            raise AppError("Детектор не настроен", status_code=409)

        # Применяем результат с семантикой keep-if-version-exists
        await self._apply_result(photo, result, keep_same_version=True)
        await self._session.commit()

        # Trigger observation recalculation after detections are updated
        if photo.captured_on is not None:
            try:
                await self._recalculator.recompute(site_id, photo.captured_on)
            except Exception:
                logger.exception("Ошибка при пересчёте наблюдений после переобнаружения")
                await self._session.rollback()

        # Возвращаем PhotoDetail
        return await self.get_photo(site_id, photo_id)

    @staticmethod
    def _get_extension_from_format(format_str: str) -> str:
        """Получить расширение файла по формату изображения.

        Args:
            format_str: Формат из PIL (JPEG, PNG, WEBP)

        Returns:
            Расширение (например, .jpg)
        """
        format_map = {
            "JPEG": ".jpg",
            "PNG": ".png",
            "WEBP": ".webp",
        }
        return format_map.get(format_str, ".jpg")

    @staticmethod
    def _get_content_type_from_format(format_str: str) -> str:
        """Получить MIME-тип по формату изображения.

        Args:
            format_str: Формат из PIL (JPEG, PNG, WEBP)

        Returns:
            MIME-тип (например, image/jpeg)
        """
        format_map = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
        }
        return format_map.get(format_str, "image/jpeg")

    @staticmethod
    def _get_content_type_from_key(key: str) -> str:
        """Получить MIME-тип из storage key (по расширению).

        Args:
            key: Storage key (например, sites/123/photos/abc.jpg)

        Returns:
            MIME-тип
        """
        if key.endswith(".jpg"):
            return "image/jpeg"
        elif key.endswith(".png"):
            return "image/png"
        elif key.endswith(".webp"):
            return "image/webp"
        return "image/jpeg"
