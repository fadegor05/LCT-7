"""Общие фикстуры бэкенда: контейнер на файловом SQLite, приложение, HTTP-клиент.

Схема создаётся из метаданных (`create_all`), а не миграциями: миграции проверяются
отдельно (`alembic upgrade --sql head`), а тестам нужна только схема.
"""

from collections.abc import AsyncIterable, AsyncIterator
from pathlib import Path
from typing import cast

import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.adapters.ml.base import DetectorClient
from app.adapters.storage.base import FileStorage
from app.adapters.storage.local import LocalFileStorage
from app.core.settings import Settings, get_settings
from app.domains.assessment.provider import AssessmentProvider
from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.methodology.provider import MethodologyProvider
from app.domains.observation.provider import ObservationProvider
from app.domains.photo.date_resolver import DateResolver, NullStampOcr, StampOcr
from app.domains.photo.recalculator import NoopObservationRecalculator, ObservationRecalculator
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.photo.service import PhotoService
from app.domains.schedule.provider import ScheduleProvider
from app.domains.site.guard import SiteAccessGuard
from app.domains.site.provider import SiteProvider
from app.domains.user.provider import UserProvider
from app.domains.utility.provider import UtilityProvider
from app.main import create_app
from app.models import Base
from tests.fakes import FakeDetector


class TestAppProvider(Provider):
    scope = Scope.APP

    @provide
    def settings(self) -> Settings:
        return get_settings()


class TestDatabaseProvider(Provider):
    """Тот же контракт, что у DatabaseProvider, но поверх файлового SQLite.

    Файл (а не `:memory:` + StaticPool) даёт каждой сессии свой физический коннект,
    как в проде с Postgres (см. `app/plugins/di.py`). Раньше все сессии в тесте
    делили один SQLite-коннект через StaticPool: закрытие одной сессии шлёт ROLLBACK
    на этот единственный коннект и может незаметно снести ещё не закоммиченный,
    но уже flush()-нутый write другой, независимой сессии, если та в этот момент
    держит открытую транзакцию на том же коннекте. WAL + busy_timeout нужны, чтобы
    параллельные писатели на один файл не падали с "database is locked".
    """

    scope = Scope.APP

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path

    @provide
    async def engine(self) -> AsyncIterable[AsyncEngine]:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{self.db_path}",
            connect_args={"check_same_thread": False},
        )

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection: object, connection_record: object) -> None:
            cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()

    @provide
    def sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def session(self, maker: async_sessionmaker[AsyncSession]) -> AsyncIterable[AsyncSession]:
        async with maker() as session:
            yield session


class TestPhotoProvider(Provider):
    """Тестовый DI провайдер для photo домена.

    Предоставляет тестовые реализации для photo домена:
    - FileStorage: LocalFileStorage с директорией, управляемой pytest
    - DetectorClient: FakeDetector
    - DateResolver и репозитории: стандартные реализации

    Args:
        storage_root: Директория для файлового хранилища (управляется pytest's tmp_path)
    """

    def __init__(self, storage_root: Path) -> None:
        """Инициализировать TestPhotoProvider.

        Args:
            storage_root: Директория для LocalFileStorage (обычно pytest tmp_path).
        """
        super().__init__()
        self.storage_root = storage_root

    # APP scope
    @provide(scope=Scope.APP)
    def storage(self) -> FileStorage:
        """Создать LocalFileStorage для тестов.

        Использует директорию, переданную в __init__, которая управляется pytest.
        """
        return LocalFileStorage(root=self.storage_root)

    @provide(scope=Scope.APP)
    def detector(self) -> DetectorClient:
        """Создать FakeDetector для тестов."""
        return FakeDetector()

    @provide(scope=Scope.APP)
    def stamp_ocr(self) -> StampOcr:
        """Создать NullStampOcr для тестов."""
        return NullStampOcr()

    @provide(scope=Scope.APP)
    def date_resolver(self, ocr: StampOcr) -> DateResolver:
        """Создать DateResolver для тестов."""
        return DateResolver(ocr=ocr)

    @provide(scope=Scope.APP, provides=ObservationRecalculator)
    def observation_recalculator(self) -> ObservationRecalculator:
        """Заглушка по умолчанию — реальная реализация приходит из ObservationProvider."""
        return NoopObservationRecalculator()

    # REQUEST scope
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
        """Создать PhotoService для тестов."""
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


@pytest.fixture
async def container(tmp_path: Path) -> AsyncIterator[AsyncContainer]:
    """DI контейнер для тестов с фотографиями.

    Args:
        tmp_path: pytest's temporary directory fixture (автоматически очищается).
    """
    # MUTATION: Use shared directory to test isolation failure
    # Uncomment next line to break isolation test:
    # storage_root = Path("/tmp/shared-probe/storage")
    # Normal (correct) behavior:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "test.db"

    container = make_async_container(
        TestAppProvider(),
        TestDatabaseProvider(db_path=db_path),
        UserProvider(),
        SiteProvider(),
        ScheduleProvider(),
        MethodologyProvider(),
        TestPhotoProvider(storage_root=storage_root),
        ObservationProvider(),
        AssessmentProvider(),
        UtilityProvider(),
    )
    yield container
    await container.close()


@pytest.fixture
async def engine(container: AsyncContainer) -> AsyncEngine:
    return await container.get(AsyncEngine)


@pytest.fixture
def app(container: AsyncContainer) -> FastAPI:
    return create_app(container)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api") as client:
        yield client


@pytest.fixture
async def detector(container: AsyncContainer) -> FakeDetector:
    """Получить FakeDetector из контейнера для конфигурации в тестах."""
    detector_client = await container.get(DetectorClient)
    return cast(FakeDetector, detector_client)


@pytest.fixture
async def storage(container: AsyncContainer) -> LocalFileStorage:
    """Получить LocalFileStorage из контейнера для проверки файлов в тестах."""
    file_storage = await container.get(FileStorage)
    return cast(LocalFileStorage, file_storage)
