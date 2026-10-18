"""Снимки со стрима камеры в её ленту: «Снять кадр сейчас» и фоновый планировщик идут одним путём.

Кадр берёт `StreamGrabber`, дальше — обычная загрузка фотографии (`PhotoService.add_camera_frame`)
с датой из момента снимка и источником «channel». Итог попытки пишется у камеры: момент,
причина неудачи, сбои подряд. Учётные данные из ссылки в ответах и записях не появляются.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ml.base import DetectorClient
from app.adapters.storage.base import FileStorage
from app.adapters.stream.base import StreamBusy, StreamError, StreamGrabber, mask_credentials
from app.core.settings import Settings
from app.domains.camera.models import Camera
from app.domains.camera.repository import CameraRepository
from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.photo.date_resolver import DateResolver
from app.domains.photo.recalculator import ObservationRecalculator
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.photo.schemas import PhotoRead
from app.domains.photo.service import PhotoService, UploadItem
from app.domains.site.guard import SiteAccessGuard
from app.plugins.exceptions import AppError


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class CaptureResult:
    photo: PhotoRead | None
    error: str | None


async def grab_frame(grabber: StreamGrabber, url: str) -> bytes | str:
    """Кадр JPEG или причина неудачи — без учётных данных из ссылки.

    `StreamBusy` не превращаем: снимок уже идёт — это не попытка и не сбой камеры.
    """
    try:
        return await grabber.grab(url)
    except StreamBusy:
        raise
    except StreamError as e:
        return mask_credentials(str(e))


class CameraFrameIngest:
    """Принять кадр камеры в её ленту. Доступ к стройке проверяет вызывающий."""

    def __init__(
        self,
        photos: PhotoRepository,
        detections: DetectionRepository,
        session: AsyncSession,
        storage: FileStorage,
        detector: DetectorClient,
        resolver: DateResolver,
        catalog: EquipmentCatalog,
        settings: Settings,
        recalculator: ObservationRecalculator,
    ) -> None:
        self._photos = photos
        self._detections = detections
        self._session = session
        self._storage = storage
        self._detector = detector
        self._resolver = resolver
        self._catalog = catalog
        self._settings = settings
        self._recalculator = recalculator

    async def store(self, camera: Camera, content: bytes, at: datetime) -> UploadItem:
        local = at.astimezone(ZoneInfo(self._settings.stream.timezone))
        # Гварда нет: пакет грузит HTTP-путь, а кадр со стрима — только этот сервис
        photos = PhotoService(
            repository=self._photos,
            detections=self._detections,
            session=self._session,
            guard=None,
            storage=self._storage,
            detector=self._detector,
            resolver=self._resolver,
            catalog=self._catalog,
            settings=self._settings,
            recalculator=self._recalculator,
        )
        return await photos.add_camera_frame(
            camera.site_id,
            camera.id,
            content,
            filename=f"stream-{local:%Y%m%d-%H%M%S}.jpg",
            captured_on=local.date(),
        )


async def record_capture(
    session: AsyncSession,
    ingest: CameraFrameIngest,
    camera: Camera,
    grabbed: bytes | str,
    at: datetime,
) -> CaptureResult:
    """Принять снятый кадр и записать итог попытки у камеры. Коммит — за вызывающим."""
    camera.last_capture_attempt_at = at
    error: str | None = None
    photo: PhotoRead | None = None
    if isinstance(grabbed, str):
        error = grabbed
    else:
        item = await ingest.store(camera, grabbed, at)
        error = item.error
        photo = item.photo
    if error is None:
        camera.last_capture_at = at
        camera.last_capture_error = None
        camera.capture_failures = 0
    else:
        camera.last_capture_error = mask_credentials(error)
        camera.capture_failures = (camera.capture_failures or 0) + 1
    return CaptureResult(photo, error)


class CameraCaptureService:
    """«Снять кадр сейчас»: синхронно снимает кадр и кладёт его в ленту камеры."""

    def __init__(
        self,
        repository: CameraRepository,
        session: AsyncSession,
        guard: SiteAccessGuard,
        grabber: StreamGrabber,
        ingest: CameraFrameIngest,
    ) -> None:
        self._repository = repository
        self._session = session
        self._guard = guard
        self._grabber = grabber
        self._ingest = ingest

    async def capture_now(self, site_id: uuid.UUID, camera_id: uuid.UUID) -> PhotoRead:
        await self._guard.require(site_id)
        camera = await self._camera(site_id, camera_id)
        url = camera.stream_url
        if url is None:
            raise AppError("У камеры нет ссылки на стрим", status_code=422)
        at = utcnow()
        # Камеру ждём до таймаута: транзакцию закрываем, чтобы не держать соединение с базой
        await self._session.commit()
        try:
            grabbed = await grab_frame(self._grabber, url)
        except StreamBusy as e:
            raise AppError(str(e), status_code=409) from e
        self._session.expire_all()
        camera = await self._camera(site_id, camera_id)  # могли удалить
        if camera.stream_url != url:
            raise AppError(
                "Ссылку камеры изменили во время снимка — снимите кадр ещё раз", status_code=409
            )
        result = await record_capture(self._session, self._ingest, camera, grabbed, at)
        await self._session.commit()
        if result.photo is None:
            raise AppError(result.error or "Кадр не принят", status_code=422)
        return result.photo

    async def _camera(self, site_id: uuid.UUID, camera_id: uuid.UUID) -> Camera:
        camera = await self._repository.get(camera_id)
        if camera is None or camera.site_id != site_id:
            raise AppError("Камера не найдена", status_code=404)
        return camera
