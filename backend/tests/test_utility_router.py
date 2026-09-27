"""Тесты служебных эндпоинтов: /health, /ready, /version."""

from collections.abc import AsyncIterable, AsyncIterator

import pytest
from dishka import Provider, Scope, make_async_container, provide
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import Settings
from app.domains.utility.provider import UtilityProvider
from app.main import create_app


async def test_health_answers_without_dependencies(client: AsyncClient) -> None:
    """Живость не зависит от инфраструктуры: 200 и фиксированное тело."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_ready_reports_available_database(client: AsyncClient) -> None:
    response = await client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"database": True}


class BrokenDatabaseProvider(Provider):
    """Тот же контракт, что у DatabaseProvider, но база заведомо не открывается.

    Файл лежит в несуществующей директории: первый же запрос падает локально,
    без сети и таймаутов. `create_all` на старте намеренно нет — ошибку должен
    поймать сам `HealthService.check_ready()`.
    """

    scope = Scope.APP

    @provide
    async def engine(self) -> AsyncIterable[AsyncEngine]:
        engine = create_async_engine("sqlite+aiosqlite:////nonexistent-dir-xyz/sub/db.sqlite3")
        yield engine
        await engine.dispose()

    @provide
    def sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def session(self, maker: async_sessionmaker[AsyncSession]) -> AsyncIterable[AsyncSession]:
        async with maker() as session:
            yield session


class StaticSettingsProvider(Provider):
    """Settings в обход lru_cache-синглтона: остальные тесты его не видят."""

    scope = Scope.APP

    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self._settings = settings

    @provide
    def settings(self) -> Settings:
        return self._settings


@pytest.fixture
async def broken_client() -> AsyncIterator[AsyncClient]:
    container = make_async_container(
        StaticSettingsProvider(Settings()),
        BrokenDatabaseProvider(),
        UtilityProvider(),
    )
    app = create_app(container)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api") as client:
        yield client
    await container.close()


async def test_ready_reports_unavailable_database(broken_client: AsyncClient) -> None:
    """Контракт деградации — собственный JSON, а не {"detail": ...} от AppError."""
    response = await broken_client.get("/ready")

    assert response.status_code == 503
    assert response.json() == {"database": False}


async def test_version_returns_backend_tag_default(client: AsyncClient) -> None:
    response = await client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": "dev"}


@pytest.fixture
async def tagged_client() -> AsyncIterator[AsyncClient]:
    """Контейнер с явным backend_tag, чтобы проверить, что тег не захардкожен."""
    # Импорт локальный: на уровне модуля pytest попытался бы собрать класс
    # с именем на Test* как набор тестов.
    from tests.conftest import TestDatabaseProvider

    container = make_async_container(
        StaticSettingsProvider(Settings(backend_tag="v1.2.3")),
        TestDatabaseProvider(),
        UtilityProvider(),
    )
    app = create_app(container)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api") as client:
        yield client
    await container.close()


async def test_version_returns_configured_backend_tag(tagged_client: AsyncClient) -> None:
    response = await tagged_client.get("/version")

    assert response.status_code == 200
    assert response.json() == {"version": "v1.2.3"}
