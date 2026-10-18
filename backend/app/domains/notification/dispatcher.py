"""Шов доставки: сервис уведомлений просит отправить, не зная как."""

import asyncio
import logging
import uuid
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.notify.base import ChannelMessage
from app.adapters.notify.factory import ChannelRegistry
from app.core.settings import Settings
from app.domains.notification.models import ChannelKind
from app.domains.notification.repository import NotificationRepository, UserChannelRepository

logger = logging.getLogger(__name__)


class NotificationDispatcher(Protocol):
    """Планировщик доставки. Синхронный: вызывается из уже закоммиченного сервиса."""

    def schedule(self, notification_id: uuid.UUID) -> None:
        """Запланировать доставку уведомления по привязанным каналам."""
        ...


class NullDispatcher:
    """Ничего не доставляет. Умолчание, когда каналы не настроены."""

    def schedule(self, notification_id: uuid.UUID) -> None:
        return None


class BackgroundDispatcher:
    """Отправка в фоне, сразу после коммита уведомления.

    Задача не может пользоваться сессией запроса: к моменту её выполнения запрос
    уже закрыт. Берёт свою из sessionmaker.

    Сознательное упрощение (см. «Принятые риски» в спецификации): ретраев нет,
    статус доставки нигде не хранится, и откат транзакции после отправки оставит
    сообщение в телеграме.
    """

    def __init__(
        self,
        maker: async_sessionmaker[AsyncSession],
        registry: ChannelRegistry,
        settings: Settings,
    ) -> None:
        self._maker = maker
        self._registry = registry
        self._settings = settings
        # Ссылки на задачи, чтобы сборщик мусора не убрал их на полпути
        self._tasks: set[asyncio.Task[int]] = set()

    def schedule(self, notification_id: uuid.UUID) -> None:
        task = asyncio.create_task(self.deliver(notification_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def deliver(self, notification_id: uuid.UUID) -> int:
        """Разослать уведомление по включённым каналам; сколько каналов приняли."""
        async with self._maker() as session:
            notification = await NotificationRepository(session).get(notification_id)
            if notification is None:
                # Транзакция создателя откатилась — доставлять нечего
                return 0
            channels = await UserChannelRepository(session).list_enabled(notification.user_id)
            message = ChannelMessage(
                title=notification.title,
                body=notification.body,
                link=self._absolute(notification.link),
            )
            addresses = [(binding.channel, binding.address) for binding in channels]

        delivered = 0
        for kind, address in addresses:
            channel = self._registry.get(ChannelKind(kind))
            if channel is None:
                continue
            try:
                await channel.send(address, message)
            except Exception as error:
                logger.warning(
                    "Не доставлено уведомление %s в канал %s: %s", notification_id, kind, error
                )
                continue
            delivered += 1
        return delivered

    def _absolute(self, link: str | None) -> str | None:
        """Относительный путь из уведомления — в абсолютный URL для внешнего канала."""
        if not link:
            return None
        if link.startswith("http://") or link.startswith("https://"):
            return link
        return f"{self._settings.notify.public_url}/{link.lstrip('/')}"
