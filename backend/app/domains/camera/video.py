"""Видео с камеры: отрывок режется на кадры по шагу, кадры идут в ленту камеры.

Время каждого кадра — момент в самом видео (начало отрывка + номер кадра × шаг), а не дата
файла. Файл на диске принимает роут; здесь разбор видео и передача кадров в фотографии.
"""

import asyncio
import os
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import UploadFile

from app.adapters.video.base import FrameExtractor, VideoError
from app.core.settings import Settings
from app.domains.camera.repository import CameraRepository
from app.domains.camera.schemas import VideoUploadReport
from app.domains.photo.service import PhotoService
from app.domains.site.guard import SiteAccessGuard
from app.plugins.exceptions import AppError

# Видео пишем на диск кусками: в память целиком не читаем
CHUNK_BYTES = 1024 * 1024


async def spool_upload(upload: UploadFile, max_bytes: int, max_mb: float) -> Path:
    """Видео из запроса — во временный файл на диске; больше `max_bytes` — 413.

    Файл удаляет вызывающий (после обработки). При ошибке файл удаляется здесь.
    """
    fd, name = tempfile.mkstemp(suffix=".video")
    path = Path(name)
    size = 0
    try:
        with os.fdopen(fd, "wb") as out:
            while chunk := await upload.read(CHUNK_BYTES):
                size += len(chunk)
                if size > max_bytes:
                    raise AppError(
                        f"Видео слишком большое: максимум {max_mb:g} МБ", status_code=413
                    )
                await asyncio.to_thread(out.write, chunk)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    return path


class CameraVideoService:
    """Видео с камеры в её ленту: кадры по шагу, каждый кадр — со своим временем."""

    def __init__(
        self,
        cameras: CameraRepository,
        guard: SiteAccessGuard,
        extractor: FrameExtractor,
        photos: PhotoService,
        settings: Settings,
    ) -> None:
        self._cameras = cameras
        self._guard = guard
        self._extractor = extractor
        self._photos = photos
        self._settings = settings

    async def upload(
        self,
        site_id: uuid.UUID,
        camera_id: uuid.UUID,
        path: Path,
        filename: str,
        recorded_at: datetime,
        step_s: int,
    ) -> VideoUploadReport:
        """Нарезать видео на кадры и принять их в ленту камеры.

        Args:
            site_id: ID стройки
            camera_id: Камера, с которой снято видео
            path: Видео на диске
            filename: Имя файла из запроса (в имени кадров)
            recorded_at: Момент начала отрывка; с поясом — пересчитаем в местное время стройки
            step_s: Шаг между кадрами, секунды

        Raises:
            AppError(404) если сайт не принадлежит пользователю или камера не на этом объекте
            AppError(422) если шаг вне допустимого или видео не читается
        """
        await self._guard.require(site_id)
        camera = await self._cameras.get(camera_id)
        if camera is None or camera.site_id != site_id:
            raise AppError("Камера не найдена", status_code=404)
        video = self._settings.video
        if not video.min_step_s <= step_s <= video.max_step_s:
            raise AppError(
                f"Шаг кадров: от {video.min_step_s} до {video.max_step_s} с", status_code=422
            )
        try:
            duration = await self._extractor.duration_s(path)
            frames = await self._extractor.extract(path, step_s, video.max_frames)
        except VideoError as e:
            raise AppError(str(e), status_code=422) from e

        start = self._local(recorded_at)
        stem = Path(filename).stem[:60]
        inputs = [
            (f"video-{stem}-{i:04d}.jpg", content, start + timedelta(seconds=i * step_s))
            for i, content in enumerate(frames)
        ]
        report = await self._photos.upload_video_frames(site_id, camera_id, inputs)
        return VideoUploadReport(
            items=report.items,
            uploaded=report.uploaded,
            failed=report.failed,
            duration_s=duration,
            step_s=step_s,
        )

    def _local(self, at: datetime) -> datetime:
        """Местное время стройки без пояса; без пояса время уже местное."""
        if at.tzinfo is None:
            return at
        return at.astimezone(ZoneInfo(self._settings.stream.timezone)).replace(tzinfo=None)
