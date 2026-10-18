"""DI-контейнер Dishka (аналог plugins/Koin.kt).

Инфраструктурные провайдеры (settings, engine, session) живут здесь, доменные —
каждый в своём домене (app/domains/<домен>/provider.py), как Module.kt в Kotlin.
"""

from collections.abc import AsyncIterable

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.settings import Settings, get_settings
from app.domains.assessment.provider import AssessmentProvider
from app.domains.assistant.provider import AssistantClientProvider, AssistantProvider
from app.domains.camera.provider import CameraProvider, StreamCaptureProvider, StreamGrabberProvider
from app.domains.methodology.provider import MethodologyProvider
from app.domains.notification.provider import NotificationProvider, NullDispatcherProvider
from app.domains.observation.provider import ObservationProvider
from app.domains.photo.provider import PhotoProvider
from app.domains.schedule.provider import ScheduleLlmClientProvider, ScheduleProvider
from app.domains.site.provider import SiteProvider
from app.domains.user.provider import UserProvider
from app.domains.utility.provider import UtilityProvider


class AppProvider(Provider):
    scope = Scope.APP

    @provide
    def settings(self) -> Settings:
        return get_settings()


class DatabaseProvider(Provider):
    scope = Scope.APP

    @provide
    async def engine(self, settings: Settings) -> AsyncIterable[AsyncEngine]:
        engine = create_async_engine(settings.postgres.url, pool_pre_ping=True)
        yield engine
        await engine.dispose()

    @provide
    def sessionmaker(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return async_sessionmaker(engine, expire_on_commit=False)

    @provide(scope=Scope.REQUEST)
    async def session(self, maker: async_sessionmaker[AsyncSession]) -> AsyncIterable[AsyncSession]:
        async with maker() as session:
            yield session


def create_container() -> AsyncContainer:
    return make_async_container(
        AppProvider(),
        DatabaseProvider(),
        UserProvider(),
        SiteProvider(),
        CameraProvider(),
        StreamGrabberProvider(),
        StreamCaptureProvider(),
        ScheduleProvider(),
        ScheduleLlmClientProvider(),
        MethodologyProvider(),
        NotificationProvider(),
        NullDispatcherProvider(),
        PhotoProvider(),
        ObservationProvider(),
        AssessmentProvider(),
        AssistantClientProvider(),
        AssistantProvider(),
        UtilityProvider(),
    )
