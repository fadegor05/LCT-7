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

    def redact(self, text: str) -> str:
        """Часть контракта клиента: канал чистит им тексты ошибок."""
        return text


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


async def test_client_redacts_the_token_from_transport_errors() -> None:
    """Утёкший в лог токен бота — это захват бота целиком.

    httpx кладёт в текст ошибки URL запроса, а URL Bot API содержит токен.
    Диспетчер пишет текст NotifyError в лог дословно, так что чистить надо здесь.
    """
    import httpx

    from app.adapters.notify.telegram import TelegramClient

    token = "7654321:AAHsuperSecretBotToken"  # noqa: S105 — тестовое значение

    class ExplodingTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError(f"Connection refused to {request.url}")

    client = TelegramClient(token=token)
    client._transport = ExplodingTransport()

    with pytest.raises(NotifyError) as caught:
        await client.send_message("1", "текст")

    assert token not in str(caught.value)
    assert "***" in str(caught.value)


async def test_channel_error_from_client_carries_no_token() -> None:
    """Тот же путь, но через канал: обёртка не должна возвращать токен обратно."""
    from app.adapters.notify.telegram import TelegramClient

    token = "7654321:AAHsuperSecretBotToken"  # noqa: S105 — тестовое значение

    class Leaky(TelegramClient):
        async def send_message(self, chat_id: str, text: str) -> None:
            raise RuntimeError(f"boom at https://api.telegram.org/bot{token}/sendMessage")

    channel = TelegramChannel(Leaky(token=token))

    with pytest.raises(NotifyError) as caught:
        await channel.send("1", ChannelMessage(title="Т", body="Б", link=None))

    assert token not in str(caught.value)


async def test_client_sends_through_the_proxy_when_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """В России api.telegram.org заблокирован — запросы должны идти через Xray."""
    import httpx as httpx_module

    from app.adapters.notify.telegram import TelegramClient

    captured: dict[str, object] = {}
    real = httpx_module.AsyncClient

    def spy(**kwargs: object) -> httpx_module.AsyncClient:
        captured.update(kwargs)
        return real(transport=httpx_module.MockTransport(lambda _: httpx_module.Response(200)))

    monkeypatch.setattr("app.adapters.notify.telegram.httpx.AsyncClient", spy)

    client = TelegramClient(token="1:abc", proxy_url="http://xray:8080")
    await client.send_message("1", "текст")

    assert captured["proxy"] == "http://xray:8080"


async def test_client_goes_direct_without_a_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    """Пустая настройка — поведение как раньше, без прокси."""
    import httpx as httpx_module

    from app.adapters.notify.telegram import TelegramClient

    captured: dict[str, object] = {}
    real = httpx_module.AsyncClient

    def spy(**kwargs: object) -> httpx_module.AsyncClient:
        captured.update(kwargs)
        return real(transport=httpx_module.MockTransport(lambda _: httpx_module.Response(200)))

    monkeypatch.setattr("app.adapters.notify.telegram.httpx.AsyncClient", spy)

    await TelegramClient(token="1:abc").send_message("1", "текст")

    assert captured.get("proxy") is None


async def test_error_message_names_the_exception_type() -> None:
    """У httpx.ConnectTimeout пустой str(), и без типа в логе остаётся «getUpdates:».

    Именно так выглядел отказ на проде: строка без причины, по которой нельзя
    отличить блокировку от неподнятого прокси или сбоя DNS.
    """
    import httpx as httpx_module

    from app.adapters.notify.telegram import TelegramClient

    class TimingOutTransport(httpx_module.AsyncBaseTransport):
        async def handle_async_request(
            self, request: httpx_module.Request
        ) -> httpx_module.Response:
            raise httpx_module.ConnectTimeout("")

    client = TelegramClient(token="1:abc")
    client._transport = TimingOutTransport()

    with pytest.raises(NotifyError) as send_error:
        await client.send_message("1", "текст")
    with pytest.raises(NotifyError) as updates_error:
        await client.get_updates(offset=None, timeout_s=1)

    assert "ConnectTimeout" in str(send_error.value)
    assert "ConnectTimeout" in str(updates_error.value)
