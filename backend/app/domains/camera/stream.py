"""Фоновый планировщик снимков со стрима (спецификация стрима, §3).

Раз в `tick_s` берёт камеры, у которых пора снимать, и снимает их не больше `concurrency`
сразу. Запускается в lifespan только при `STREAM__ENABLED=true`. Выборка — `FOR UPDATE SKIP
LOCKED`: при нескольких репликах одну камеру снимает одна, но на одном экземпляре это лишь
страховка; единственный экземпляр — расчётное предположение.
"""

import asyncio
import logging
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from dishka import AsyncContainer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.stream.base import StreamBusy, StreamGrabber
from app.core.settings import Settings
from app.domains.camera.capture import CameraFrameIngest, grab_frame, record_capture, utcnow
from app.domains.camera.models import Camera
from app.domains.camera.schedule import capture_due

logger = logging.getLogger(__name__)


class StreamCapture:
    """Фоновая задача: снимает кадр с камер, которым пора."""

    def __init__(
        self,
        container: AsyncContainer,
        maker: async_sessionmaker[AsyncSession],
        grabber: StreamGrabber,
        settings: Settings,
    ) -> None:
        self._container = container
        self._maker = maker
        self._grabber = grabber
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def run_once(self, now: datetime | None = None) -> int:
        """Снять кадр со всех камер, которым пора; число попыток."""
        now = now or utcnow()
        cfg = self._settings.stream
        tz = ZoneInfo(cfg.timezone)
        async with self._maker() as session:
            rows = await session.execute(
                select(Camera)
                .where(Camera.stream_url.is_not(None), Camera.capture_every_s.is_not(None))
                .order_by(Camera.id)
                .with_for_update(of=Camera, skip_locked=True)
            )
            due = [
                camera
                for camera in rows.scalars().all()
                if camera.capture_every_s is not None
                and capture_due(
                    now=now,
                    last_attempt=camera.last_capture_attempt_at,
                    every_s=camera.capture_every_s,
                    failures=camera.capture_failures,
                    hours=cfg.window,
                    tz=tz,
                    max_interval_s=cfg.max_backoff_s,
                )
            ]
            # Момент попытки ставим до снимка: камеру не возьмут снова, пока она отвечает
            for camera in due:
                camera.last_capture_attempt_at = now
            targets = [(camera.id, camera.stream_url) for camera in due]
            await session.commit()

        limit = asyncio.Semaphore(cfg.concurrency)

        async def one(camera_id: uuid.UUID, url: str | None) -> None:
            async with limit:
                await self._capture(camera_id, url, now)

        await asyncio.gather(*(one(camera_id, url) for camera_id, url in targets))
        return len(targets)

    async def _capture(self, camera_id: uuid.UUID, url: str | None, at: datetime) -> None:
        if url is None:
            return
        try:
            grabbed = await grab_frame(self._grabber, url)
        except StreamBusy:
            return  # камеру уже снимают («Снять кадр сейчас»)
        try:
            async with self._container() as request:
                session = await request.get(AsyncSession)
                ingest = await request.get(CameraFrameIngest)
                camera = await session.get(Camera, camera_id)
                if camera is None or camera.stream_url != url:  # камеру правили во время снимка
                    return
                await record_capture(session, ingest, camera, grabbed, at)
                await session.commit()
        except Exception:
            logger.exception("снимок со стрима камеры %s: сбой записи", camera_id)

    async def start(self) -> None:
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop(), name="stream-capture")

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _loop(self) -> None:
        tick = self._settings.stream.tick_s
        while not self._stopping.is_set():
            try:
                await self.run_once()
            except Exception:
                logger.exception("снимки со стрима: сбой, продолжаю")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=tick)
            except TimeoutError:
                pass


async def start_stream_capture(
    container: AsyncContainer, settings: Settings
) -> StreamCapture | None:
    """Запустить планировщик, если он включён настройкой; иначе None и ничего не запущено."""
    if not settings.stream.enabled:
        return None
    capture = await container.get(StreamCapture)
    await capture.start()
    return capture
