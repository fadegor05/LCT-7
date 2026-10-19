"""Поллер бота: разбор /start и привязка chat_id."""

from typing import Any

import pytest
from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.settings import Settings
from app.domains.notification.channels import ChannelLinkService
from app.domains.notification.models import ChannelKind
from app.domains.notification.repository import (
    ChannelLinkTokenRepository,
    UserChannelRepository,
)
from app.domains.notification.telegram_link import TelegramLinkPoller, parse_start_token
from app.domains.user.service import STAND_USER_ID, UserService


class FakeUpdatesClient:
    """Отдаёт заготовленные апдейты и запоминает ответы бота."""

    def __init__(self, updates: list[dict[str, Any]]) -> None:
        self._updates = updates
        self.sent: list[tuple[str, str]] = []

    async def get_updates(self, offset: int | None, timeout_s: int) -> list[dict[str, Any]]:
        return [u for u in self._updates if offset is None or u["update_id"] >= offset]

    async def send_message(self, chat_id: str, text: str) -> None:
        self.sent.append((chat_id, text))


def update(update_id: int, chat_id: int, text: str) -> dict[str, Any]:
    return {
        "update_id": update_id,
        "message": {"chat": {"id": chat_id}, "text": text},
    }


def test_parse_start_token() -> None:
    assert parse_start_token("/start abc123") == "abc123"
    assert parse_start_token("/start   abc123  ") == "abc123"
    assert parse_start_token("/start@lct7_bot abc123") == "abc123"
    assert parse_start_token("/start") is None
    assert parse_start_token("привет") is None
    assert parse_start_token("") is None


def settings_with_bot() -> Settings:
    settings = Settings()
    settings.notify.telegram.token = "123:abc"
    settings.notify.telegram.bot_username = "lct7_bot"
    return settings


async def issue_token(container: AsyncContainer) -> str:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()
        session = await request_container.get(AsyncSession)
        link = ChannelLinkService(
            channels=UserChannelRepository(session),
            tokens=ChannelLinkTokenRepository(session),
            session=session,
            settings=settings_with_bot(),
        )
        issued = await link.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        return issued.token


async def test_start_with_token_binds_the_chat(container: AsyncContainer) -> None:
    token = await issue_token(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    client = FakeUpdatesClient([update(1, 424242, f"/start {token}")])
    poller = TelegramLinkPoller(maker, client, settings_with_bot())  # type: ignore[arg-type]

    handled = await poller.run_once()

    assert handled == 1
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        binding = await UserChannelRepository(session).get_for(STAND_USER_ID, ChannelKind.TELEGRAM)
        assert binding is not None
        assert binding.address == "424242"
    assert "привязаны" in client.sent[0][1]


async def test_second_start_with_same_token_reports_stale_link(
    container: AsyncContainer,
) -> None:
    """Review Focus 2: токен одноразовый, второй раз — понятный ответ, не падение."""
    token = await issue_token(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    client = FakeUpdatesClient(
        [update(1, 424242, f"/start {token}"), update(2, 999, f"/start {token}")]
    )
    poller = TelegramLinkPoller(maker, client, settings_with_bot())  # type: ignore[arg-type]

    await poller.run_once()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        bindings = await UserChannelRepository(session).list_for_user(STAND_USER_ID)
        assert len(bindings) == 1
        assert bindings[0].address == "424242"
    assert "недействительна" in client.sent[1][1] or "устарела" in client.sent[1][1]


async def test_plain_message_is_ignored_with_a_hint(container: AsyncContainer) -> None:
    await issue_token(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    client = FakeUpdatesClient([update(1, 424242, "привет")])
    poller = TelegramLinkPoller(maker, client, settings_with_bot())  # type: ignore[arg-type]

    handled = await poller.run_once()

    assert handled == 0
    assert len(client.sent) == 1


async def test_offset_advances_past_handled_updates(container: AsyncContainer) -> None:
    """Второй проход не должен повторно обрабатывать те же апдейты."""
    token = await issue_token(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    client = FakeUpdatesClient([update(7, 424242, f"/start {token}")])
    poller = TelegramLinkPoller(maker, client, settings_with_bot())  # type: ignore[arg-type]

    await poller.run_once()
    second = await poller.run_once()

    assert second == 0


class ExplodingClient(FakeUpdatesClient):
    """БД отвалилась: первая обработка падает, вторая проходит."""

    def __init__(self, updates: list[dict[str, Any]]) -> None:
        super().__init__(updates)
        self.calls = 0


async def test_failed_update_is_retried_not_skipped(container: AsyncContainer) -> None:
    """Сбой при обработке не должен съедать апдейт: пользователь нажал Start один раз.

    offset нельзя двигать до успешной обработки — иначе следующий getUpdates
    запросит апдейты после потерянного, и привязка молча не состоится.
    """
    token = await issue_token(container)
    maker = await container.get(async_sessionmaker[AsyncSession])
    client = ExplodingClient([update(5, 424242, f"/start {token}")])
    poller = TelegramLinkPoller(maker, client, settings_with_bot())  # type: ignore[arg-type]

    boom = RuntimeError("database is unavailable")
    original = poller._handle

    async def flaky(upd: dict[str, Any]) -> bool:
        client.calls += 1
        if client.calls == 1:
            raise boom
        return await original(upd)

    poller._handle = flaky  # type: ignore[method-assign]

    with pytest.raises(RuntimeError):
        await poller.run_once()

    # Второй проход должен снова увидеть тот же апдейт и привязать чат
    linked = await poller.run_once()

    assert linked == 1
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        binding = await UserChannelRepository(session).get_for(STAND_USER_ID, ChannelKind.TELEGRAM)
        assert binding is not None
