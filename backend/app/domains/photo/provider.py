"""DI-провайдер домена photo."""

from collections.abc import AsyncIterable

import httpx
from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ml.base import DetectorClient
from app.adapters.ml.factory import create_detector
from app.adapters.ml.http import DetectorHttpClient
from app.adapters.storage.base import FileStorage
from app.adapters.storage.factory import create_storage
from app.core.settings import Settings
from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.photo.date_resolver import DateResolver, NullStampOcr, StampOcr
from app.domains.photo.recalculator import NoopObservationRecalculator, ObservationRecalculator
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.photo.service import PhotoService
from app.domains.site.guard import SiteAccessGuard


class PhotoProvider(Provider):
    """DI провайдер для домена photo."""

    # APP scope: инфраструктура, которая создаётся один раз и переиспользуется

    @provide(scope=Scope.APP)
    async def detector_http_client(self) -> AsyncIterable[DetectorHttpClient]:
        """Создать shared DetectorHttpClient для детектора.

        Закрывается при завершении контейнера.
        """
        client = httpx.AsyncClient()
        yield DetectorHttpClient(client)
        await client.aclose()

    @provide(scope=Scope.APP)
    def storage(self, settings: Settings) -> FileStorage:
        """Создать хранилище файлов."""
        return create_storage(settings)

    @provide(scope=Scope.APP)
    def detector(
        self,
        settings: Settings,
        http_client: DetectorHttpClient,
    ) -> DetectorClient:
        """Создать клиент детектора."""
        # Unwrap the NewType to get the underlying AsyncClient
        return create_detector(settings, http_client)  # type: ignore

    @provide(scope=Scope.APP)
    def stamp_ocr(self) -> StampOcr:
        """Создать OCR для чтения штампов."""
        return NullStampOcr()

    @provide(scope=Scope.APP)
    def date_resolver(self, ocr: StampOcr) -> DateResolver:
        """Создать resolver для разрешения дат."""
        return DateResolver(ocr=ocr)

    @provide(scope=Scope.APP, provides=ObservationRecalculator)
    def observation_recalculator(self) -> ObservationRecalculator:
        """Заглушка по умолчанию — реальная реализация приходит из ObservationProvider."""
        return NoopObservationRecalculator()

    # REQUEST scope: привязаны к сессии БД

    photo_repository = provide(PhotoRepository, scope=Scope.REQUEST)
    detection_repository = provide(DetectionRepository, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST)
    async def photo_service(
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
    ) -> PhotoService:
        """Создать PhotoService."""
        return PhotoService(
            repository=repository,
            detections=detections,
            session=session,
            guard=guard,
            storage=storage,
            detector=detector,
            resolver=resolver,
            catalog=catalog,
            settings=settings,
            recalculator=recalculator,
        )
