"""Общие фикстуры бэкенда: контейнер на in-memory SQLite, приложение, HTTP-клиент.

Схема создаётся из метаданных (`create_all`), а не миграциями: миграции проверяются
отдельно (`alembic upgrade --sql head`), а тестам нужна только схема.
"""

from collections.abc import AsyncIterable, AsyncIterator

import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.core.settings import Settings, get_settings
from app.domains.user.provider import UserProvider
from app.main import create_app
from app.models import Base


class TestAppProvider(Provider):
    scope = Scope.APP

    @provide
    def settings(self) -> Settings:
        return get_settings()


class TestDatabaseProvider(Provider):
    """Тот же контракт, что у DatabaseProvider, но поверх SQLite в памяти.

    StaticPool обязателен: без него каждое соединение получает свою пустую базу.
    """

    scope = Scope.APP

    @provide
    async def engine(self) -> AsyncIterable[AsyncEngine]:
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
        )
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


@pytest.fixture
async def container() -> AsyncIterator[AsyncContainer]:
    container = make_async_container(TestAppProvider(), TestDatabaseProvider(), UserProvider())
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
