"""DI-провайдер домена photo."""

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ml.base import DetectorClient
from app.adapters.ml.factory import create_detector
from app.adapters.storage.base import FileStorage
from app.adapters.storage.factory import create_storage
from app.core.settings import Settings
from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.photo.date_resolver import DateResolver, NullStampOcr, StampOcr
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.photo.service import PhotoService
from app.domains.site.guard import SiteAccessGuard


class PhotoProvider(Provider):
    """DI провайдер для домена photo."""

    # APP scope: инфраструктура, которая создаётся один раз и переиспользуется

    @provide(scope=Scope.APP)
    def storage(self, settings: Settings) -> FileStorage:
        """Создать хранилище файлов."""
        return create_storage(settings)

    @provide(scope=Scope.APP)
    def detector(self, settings: Settings) -> DetectorClient:
        """Создать клиент детектора."""
        return create_detector(settings)

    @provide(scope=Scope.APP)
    def stamp_ocr(self) -> StampOcr:
        """Создать OCR для чтения штампов."""
        return NullStampOcr()

    @provide(scope=Scope.APP)
    def date_resolver(self, ocr: StampOcr) -> DateResolver:
        """Создать resolver для разрешения дат."""
        return DateResolver(ocr=ocr)

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
        )
