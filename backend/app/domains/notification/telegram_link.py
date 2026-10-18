"""Фоновая привязка телеграма: long polling бота и разбор /start <токен>.

Устроено как app/domains/camera/stream.py: start()/stop(), запуск в lifespan
только при настроенном боте. Webhook не используется — ему нужен публичный HTTPS,
которого нет при локальной разработке.
"""

import asyncio
import logging
import re
from typing import Any

from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.notify.telegram import TelegramClient
from app.core.settings import Settings
from app.domains.notification.channels import ChannelLinkService
from app.domains.notification.repository import (
    ChannelLinkTokenRepository,
    UserChannelRepository,
)
from app.plugins.exceptions import AppError

logger = logging.getLogger(__name__)

# /start <токен>, в группах телеграм добавляет к команде имя бота
_START = re.compile(r"^/start(?:@\S+)?\s+(\S+)\s*$")

HELLO = (
    "Это бот уведомлений «Веха». Чтобы получать сюда уведомления, "
    "нажмите «Привязать» в личном кабинете на сайте."
)
LINKED = "Готово, уведомления привязаны к этому чату."


def parse_start_token(text: str) -> str | None:
    """Достать токен из текста команды; None — это не /start с токеном."""
    match = _START.match(text.strip())
    return match.group(1) if match else None


class TelegramLinkPoller:
    """Опрашивает Bot API и привязывает чаты по одноразовым токенам."""

    def __init__(
        self,
        maker: async_sessionmaker[AsyncSession],
        client: TelegramClient,
        settings: Settings,
    ) -> None:
        self._maker = maker
        self._client = client
        self._settings = settings
        # Курсор апдейтов живёт в памяти: телеграм хранит их сутки, после рестарта
        # поллер перечитает, а повторный /start по погашенному токену безвреден
        self._offset: int | None = None
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def run_once(self) -> int:
        """Разобрать одну пачку апдейтов; сколько чатов привязали."""
        updates = await self._client.get_updates(
            offset=self._offset, timeout_s=self._settings.notify.telegram.poll_timeout_s
        )
        linked = 0
        for update in updates:
            self._offset = int(update["update_id"]) + 1
            if await self._handle(update):
                linked += 1
        return linked

    async def _handle(self, update: dict[str, Any]) -> bool:
        message = update.get("message") or {}
        chat_id = (message.get("chat") or {}).get("id")
        text = message.get("text") or ""
        if chat_id is None:
            return False

        token = parse_start_token(text)
        if token is None:
            await self._reply(str(chat_id), HELLO)
            return False

        async with self._maker() as session:
            service = ChannelLinkService(
                channels=UserChannelRepository(session),
                tokens=ChannelLinkTokenRepository(session),
                session=session,
                settings=self._settings,
            )
            try:
                await service.redeem(token, address=str(chat_id))
            except AppError as error:
                await self._reply(str(chat_id), error.message)
                return False

        await self._reply(str(chat_id), LINKED)
        return True

    async def _reply(self, chat_id: str, text: str) -> None:
        try:
            await self._client.send_message(chat_id, text)
        except Exception as error:
            logger.warning("Не удалось ответить в чат %s: %s", chat_id, error)

    async def start(self) -> None:
        self._stopping.clear()
        self._task = asyncio.create_task(self._loop())

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await self.run_once()
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.warning("Поллер телеграма: %s", error)
                # Телеграм недоступен — не молотим его вхолостую
                await asyncio.sleep(5)

    async def stop(self) -> None:
        self._stopping.set()
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None


async def start_telegram_poller(
    container: AsyncContainer, settings: Settings
) -> TelegramLinkPoller | None:
    """Запустить поллер, если бот настроен; иначе None и ничего не запущено."""
    if not settings.notify.telegram_configured:
        return None
    poller = await container.get(TelegramLinkPoller)
    await poller.start()
    return poller
