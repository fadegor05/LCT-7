"""Доставка уведомления по привязанным каналам."""

import logging
import uuid

import pytest
from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.notify.base import ChannelMessage, NotifyError
from app.adapters.notify.factory import ChannelRegistry
from app.core.settings import Settings
from app.domains.notification.dispatcher import BackgroundDispatcher
from app.domains.notification.models import (
    ChannelKind,
    Notification,
    NotificationType,
    UserChannel,
)
from app.domains.notification.repository import UserChannelRepository
from app.domains.user.service import STAND_USER_ID, UserService


class SpyChannel:
    kind = ChannelKind.TELEGRAM

    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[tuple[str, ChannelMessage]] = []
        self.error = error

    async def send(self, address: str, message: ChannelMessage) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append((address, message))


async def seed(container: AsyncContainer, *, enabled: bool = True) -> uuid.UUID:
    """Пользователь, привязанный телеграм и одно уведомление; вернуть его id."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()
        session = await request_container.get(AsyncSession)
        session.add(
            UserChannel(
                user_id=STAND_USER_ID,
                channel=ChannelKind.TELEGRAM,
                address="424242",
                enabled=enabled,
            )
        )
        notification = Notification(
            user_id=STAND_USER_ID,
            type=NotificationType.SYSTEM,
            title="Отклонение",
            body="Нет экскаватора",
            link="/sites/1",
        )
        session.add(notification)
        await session.commit()
        return notification.id


def make_dispatcher(
    maker: async_sessionmaker[AsyncSession], channel: SpyChannel
) -> BackgroundDispatcher:
    settings = Settings()
    settings.notify.public_url = "https://stand.example"
    return BackgroundDispatcher(
        maker=maker,
        registry=ChannelRegistry({ChannelKind.TELEGRAM: channel}),  # type: ignore[dict-item]
        settings=settings,
    )


async def test_delivers_to_enabled_channel(container: AsyncContainer) -> None:
    notification_id = await seed(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    channel = SpyChannel()

    delivered = await make_dispatcher(maker, channel).deliver(notification_id)

    assert delivered == 1
    assert channel.sent[0][0] == "424242"
    assert channel.sent[0][1].title == "Отклонение"


async def test_relative_link_becomes_absolute(container: AsyncContainer) -> None:
    """В телеграме относительный путь бесполезен."""
    notification_id = await seed(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    channel = SpyChannel()

    await make_dispatcher(maker, channel).deliver(notification_id)

    assert channel.sent[0][1].link == "https://stand.example/sites/1"


async def test_disabled_channel_is_skipped(container: AsyncContainer) -> None:
    notification_id = await seed(container, enabled=False)
    maker = await container.get(async_sessionmaker[AsyncSession])
    channel = SpyChannel()

    delivered = await make_dispatcher(maker, channel).deliver(notification_id)

    assert delivered == 0
    assert channel.sent == []


async def test_channel_failure_is_logged_and_swallowed(
    container: AsyncContainer, caplog: pytest.LogCaptureFixture
) -> None:
    """Review Focus 3: бот заблокирован — доставка молчит в лог, привязка цела."""
    notification_id = await seed(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    channel = SpyChannel(error=NotifyError("403 bot was blocked"))

    with caplog.at_level(logging.WARNING):
        delivered = await make_dispatcher(maker, channel).deliver(notification_id)

    assert delivered == 0
    assert "403" in caplog.text

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        # Привязка не удаляется из-за неудачной отправки
        still_linked = await UserChannelRepository(session).get_for(
            STAND_USER_ID, ChannelKind.TELEGRAM
        )
        assert still_linked is not None
        assert still_linked.enabled is True


async def test_missing_notification_is_not_an_error(container: AsyncContainer) -> None:
    """Транзакция откатилась — доставлять нечего, падать нельзя."""
    await seed(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    channel = SpyChannel()

    delivered = await make_dispatcher(maker, channel).deliver(uuid.uuid4())

    assert delivered == 0
    assert channel.sent == []


async def test_close_waits_for_scheduled_deliveries(container: AsyncContainer) -> None:
    """Деплой не должен терять уже запланированную отправку.

    Без слива задач `lifespan` закрывает контейнер и диспоузит engine под
    выполняющейся задачей: сообщение не уходит, в логах — «Task was destroyed».
    """
    notification_id = await seed(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    channel = SpyChannel()
    dispatcher = make_dispatcher(maker, channel)

    dispatcher.schedule(notification_id)
    await dispatcher.close()

    assert channel.sent != [], "close() вернулся до того, как доставка состоялась"


async def test_close_is_safe_without_scheduled_tasks(container: AsyncContainer) -> None:
    maker = await container.get(async_sessionmaker[AsyncSession])

    await make_dispatcher(maker, SpyChannel()).close()
