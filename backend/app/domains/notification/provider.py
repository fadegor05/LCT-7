"""DI-провайдеры домена notification."""

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.notify.factory import ChannelRegistry, create_channel_registry
from app.core.settings import Settings
from app.domains.notification.dispatcher import (
    BackgroundDispatcher,
    NotificationDispatcher,
    NullDispatcher,
)
from app.domains.notification.repository import (
    ChannelLinkTokenRepository,
    NotificationRepository,
    UserChannelRepository,
)
from app.domains.notification.service import NotificationService


class NotificationProvider(Provider):
    scope = Scope.REQUEST

    notifications = provide(NotificationRepository)
    channels = provide(UserChannelRepository)
    tokens = provide(ChannelLinkTokenRepository)

    @provide(scope=Scope.REQUEST)
    def service(
        self,
        repository: NotificationRepository,
        session: AsyncSession,
        dispatcher: NotificationDispatcher,
    ) -> NotificationService:
        return NotificationService(repository, session, dispatcher)


class NullDispatcherProvider(Provider):
    """Доставки нет. Переопределяется провайдером каналов, когда они настроены."""

    scope = Scope.APP

    @provide
    def dispatcher(self) -> NotificationDispatcher:
        return NullDispatcher()


class ChannelsProvider(Provider):
    """Реестр каналов и доставка. Один на приложение."""

    scope = Scope.APP

    @provide
    def registry(self, settings: Settings) -> ChannelRegistry:
        return create_channel_registry(settings)

    @provide
    def dispatcher(
        self,
        maker: async_sessionmaker[AsyncSession],
        registry: ChannelRegistry,
        settings: Settings,
    ) -> NotificationDispatcher:
        return BackgroundDispatcher(maker=maker, registry=registry, settings=settings)
