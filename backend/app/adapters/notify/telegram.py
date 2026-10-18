"""Телеграм: тонкий клиент Bot API и канал доставки поверх него.

Единственное место в проекте, знающее про формат Bot API. Токен в логи не пишется.
"""

import logging
from typing import Any, ClassVar

import httpx

from app.adapters.notify.base import ChannelMessage, NotifyError
from app.domains.notification.models import ChannelKind

logger = logging.getLogger(__name__)

# Жёсткий лимит одного сообщения в Bot API
TELEGRAM_TEXT_LIMIT = 4096


def format_message(message: ChannelMessage) -> str:
    """Собрать текст сообщения и обрезать до лимита Bot API.

    Разметка не используется намеренно: заголовки уведомлений приходят из доменов
    и могут содержать символы, которые пришлось бы экранировать.
    """
    parts = [message.title, "", message.body]
    if message.link:
        parts += ["", message.link]
    text = "\n".join(parts)
    if len(text) > TELEGRAM_TEXT_LIMIT:
        text = text[: TELEGRAM_TEXT_LIMIT - 1] + "…"
    return text


class TelegramClient:
    """Обёртка над Bot API. Создаётся один раз на приложение."""

    def __init__(self, token: str, timeout_s: float = 35.0) -> None:
        self._token = token
        self._timeout_s = timeout_s

    def _url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self._token}/{method}"

    async def send_message(self, chat_id: str, text: str) -> None:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.post(
                self._url("sendMessage"),
                json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            )
        if response.status_code != 200:
            # Тело содержит описание ошибки Bot API, но не токен — его нет в ответе
            raise NotifyError(f"Telegram sendMessage {response.status_code}: {response.text}")

    async def get_updates(self, offset: int | None, timeout_s: int) -> list[dict[str, Any]]:
        """Long polling. Телеграм держит соединение, пока не появится апдейт."""
        params: dict[str, Any] = {"timeout": timeout_s}
        if offset is not None:
            params["offset"] = offset
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(self._url("getUpdates"), params=params)
        if response.status_code != 200:
            raise NotifyError(f"Telegram getUpdates {response.status_code}")
        payload = response.json()
        if not payload.get("ok"):
            raise NotifyError("Telegram getUpdates вернул ok=false")
        return list(payload.get("result", []))


class TelegramChannel:
    """Доставка уведомления в телеграм-чат."""

    kind: ClassVar[ChannelKind] = ChannelKind.TELEGRAM

    def __init__(self, client: TelegramClient) -> None:
        self._client = client

    async def send(self, address: str, message: ChannelMessage) -> None:
        try:
            await self._client.send_message(address, format_message(message))
        except NotifyError:
            raise
        except Exception as error:  # httpx, таймауты, разбор JSON
            raise NotifyError(f"Не удалось отправить в телеграм: {error}") from error
