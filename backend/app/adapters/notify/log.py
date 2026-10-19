"""Канал-заглушка: пишет сообщение в лог приложения.

Умолчание, когда внешний канал не настроен, и то, с чем работают тесты.
"""

import logging
from typing import ClassVar

from app.adapters.notify.base import ChannelMessage
from app.domains.notification.models import ChannelKind

logger = logging.getLogger(__name__)


class LogChannel:
    """Ничего никуда не шлёт, только протоколирует попытку."""

    kind: ClassVar[ChannelKind] = ChannelKind.TELEGRAM

    async def send(self, address: str, message: ChannelMessage) -> None:
        logger.info(
            "Уведомление не отправлено (канал не настроен): адрес=%s, заголовок=%s, текст=%s",
            address,
            message.title,
            message.body,
        )
