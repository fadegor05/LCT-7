"""Фоновая обработка загруженных снимков (очередь).

Запрос загрузки только принимает файлы (статус queued). Очередь берёт кадры пачками не
больше `UPLOAD__WORKERS` одновременно, ставит дату (штамп, EXIF, имя файла) и технику, а
когда кадры объекта кончаются — закрывает его пачки: дата по соседям, серия камеры и один
пересчёт наблюдений по всем датам. Выборка — `FOR UPDATE SKIP LOCKED`, как у планировщика
стрима; после перезапуска оборванные кадры возвращаются в очередь.
"""

import asyncio
import logging
import uuid
from typing import NewType

from dishka import AsyncContainer, Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.ml.base import DetectorClient
from app.adapters.storage.base import FileStorage
from app.core.settings import Settings
from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.photo.date_resolver import DateResolver
from app.domains.photo.recalculator import ObservationRecalculator
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.photo.service import PhotoService

logger = logging.getLogger(__name__)

# PhotoService без гварда: вне HTTP-запроса текущего пользователя нет, доступ к объекту
# проверил запрос загрузки
SystemPhotoService = NewType("SystemPhotoService", PhotoService)


class PhotoQueue:
    """Фоновая задача: обрабатывает кадры со статусом queued."""

    def __init__(
        self,
        container: AsyncContainer,
        maker: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self._container = container
        self._maker = maker
        self._settings = settings
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()
        self._wake = asyncio.Event()

    def wake(self) -> None:
        """Загрузка приняла кадры — не ждать следующего тика."""
        self._wake.set()

    async def run_once(self) -> int:
        """Обработать всё, что сейчас в очереди, и закрыть объекты; число кадров."""
        done = 0
        touched: set[uuid.UUID] = set()
        while not self._stopping.is_set():
            async with self._maker() as session:
                claimed = await PhotoRepository(session).claim_queued(self._settings.upload.workers)
                await session.commit()
            if not claimed:
                break
            await asyncio.gather(*(self._process(photo_id) for photo_id, _ in claimed))
            done += len(claimed)
            touched.update(site_id for _, site_id in claimed)
            # Объект, у которого кадры кончились, закрываем сразу — экраны оживают раньше,
            # чем дойдёт очередь других объектов
            for site_id in list(touched):
                if await self._finish(site_id):
                    touched.discard(site_id)
        for site_id in touched:
            await self._finish(site_id)
        return done

    async def recover(self) -> None:
        """После перезапуска: оборванные кадры — в очередь, незакрытые объекты — закрыть."""
        async with self._maker() as session:
            requeued = await PhotoRepository(session).requeue_processing()
            sites = await PhotoRepository(session).sites_with_open_batches()
            await session.commit()
        if requeued:
            logger.info("очередь снимков: %s кадров снова в очереди после перезапуска", requeued)
        for site_id in sites:
            await self._finish(site_id)

    async def _process(self, photo_id: uuid.UUID) -> None:
        try:
            async with self._container() as request:
                service = await request.get(SystemPhotoService)
                await service.process_queued(photo_id)
        except Exception:
            logger.exception("очередь снимков: сбой обработки кадра %s", photo_id)
            await self._fail(photo_id)

    async def _fail(self, photo_id: uuid.UUID) -> None:
        """Кадр не застревает в processing: ошибка — статус failed, его можно перезапустить."""
        try:
            async with self._maker() as session:
                photo = await PhotoRepository(session).get(photo_id)
                if photo is not None:
                    photo.processing_status = "failed"
                    await session.commit()
        except Exception:
            logger.exception("очередь снимков: не удалось пометить кадр %s", photo_id)

    async def _finish(self, site_id: uuid.UUID) -> bool:
        try:
            async with self._container() as request:
                service = await request.get(SystemPhotoService)
                return await service.finish_site_queue(site_id)
        except Exception:
            logger.exception("очередь снимков: сбой закрытия объекта %s", site_id)
            return True  # не повторять бесконечно; снимки уже обработаны

    async def start(self) -> None:
        self._stopping.clear()
        await self.recover()
        self._task = asyncio.create_task(self._loop(), name="photo-queue")

    async def stop(self) -> None:
        self._stopping.set()
        self._wake.set()
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None

    async def _loop(self) -> None:
        tick = self._settings.upload.tick_s
        while not self._stopping.is_set():
            self._wake.clear()
            try:
                await self.run_once()
            except Exception:
                logger.exception("очередь снимков: сбой, продолжаю")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=tick)
            except TimeoutError:
                pass


class PhotoQueueProvider(Provider):
    """Очередь снимков и сервис фото для неё (без гварда)."""

    queue = provide(PhotoQueue, scope=Scope.APP)

    @provide(scope=Scope.REQUEST)
    def system_photo_service(
        self,
        repository: PhotoRepository,
        detections: DetectionRepository,
        session: AsyncSession,
        storage: FileStorage,
        detector: DetectorClient,
        resolver: DateResolver,
        catalog: EquipmentCatalog,
        settings: Settings,
        recalculator: ObservationRecalculator,
    ) -> SystemPhotoService:
        return SystemPhotoService(
            PhotoService(
                repository=repository,
                detections=detections,
                session=session,
                guard=None,
                storage=storage,
                detector=detector,
                resolver=resolver,
                catalog=catalog,
                settings=settings,
                recalculator=recalculator,
            )
        )


async def start_photo_queue(container: AsyncContainer, settings: Settings) -> PhotoQueue | None:
    """Запустить очередь, если загрузка фоновая; иначе None."""
    if not settings.upload.background:
        return None
    queue = await container.get(PhotoQueue)
    await queue.start()
    return queue
