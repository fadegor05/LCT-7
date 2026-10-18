"""Телеграм как канал доставки: формат текста, лимит, ошибки."""

import pytest

from app.adapters.notify.base import ChannelMessage, NotifyError
from app.adapters.notify.telegram import (
    TELEGRAM_TEXT_LIMIT,
    TelegramChannel,
    format_message,
)
from app.domains.notification.models import ChannelKind


class FakeTelegramClient:
    """Вместо сети — список отправленного."""

    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[tuple[str, str]] = []
        self.error = error

    async def send_message(self, chat_id: str, text: str) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append((chat_id, text))


def test_format_includes_title_body_and_link() -> None:
    text = format_message(
        ChannelMessage(title="Отклонение", body="Нет экскаватора", link="https://x/y")
    )

    assert "Отклонение" in text
    assert "Нет экскаватора" in text
    assert "https://x/y" in text


def test_format_without_link_has_no_dangling_separator() -> None:
    text = format_message(ChannelMessage(title="Заголовок", body="Текст", link=None))

    assert text.strip() == text
    assert text.endswith("Текст")


def test_format_truncates_at_telegram_limit() -> None:
    """Review Focus 4: длинный текст обрезается, а не роняет отправку."""
    text = format_message(ChannelMessage(title="Т", body="я" * 10_000, link=None))

    assert len(text) <= TELEGRAM_TEXT_LIMIT
    assert text.endswith("…")


async def test_channel_sends_to_chat_id() -> None:
    client = FakeTelegramClient()
    channel = TelegramChannel(client)  # type: ignore[arg-type]

    await channel.send("12345", ChannelMessage(title="Заголовок", body="Текст", link=None))

    assert client.sent[0][0] == "12345"
    assert "Заголовок" in client.sent[0][1]


async def test_channel_wraps_transport_errors() -> None:
    """Review Focus 3: бот заблокирован — наружу уходит NotifyError, не httpx-ошибка."""
    client = FakeTelegramClient(error=RuntimeError("403 Forbidden: bot was blocked by the user"))
    channel = TelegramChannel(client)  # type: ignore[arg-type]

    with pytest.raises(NotifyError):
        await channel.send("12345", ChannelMessage(title="Т", body="Б", link=None))


def test_channel_declares_its_kind() -> None:
    assert TelegramChannel.kind == ChannelKind.TELEGRAM
