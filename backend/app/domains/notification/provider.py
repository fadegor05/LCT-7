"""DI-провайдеры домена notification."""

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notification.dispatcher import NotificationDispatcher, NullDispatcher
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
