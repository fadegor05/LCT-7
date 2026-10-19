"""Базовые интерфейсы доставки уведомлений по внешним каналам.

Устроено как adapters/storage: Protocol здесь, реализации рядом, сборка в factory.
Добавить канал = один файл плюс строка в фабрике.
"""

from typing import ClassVar, Protocol

from pydantic import BaseModel

from app.domains.notification.models import ChannelKind


class NotifyError(Exception):
    """Ошибка доставки. Ловится диспетчером и пишется в лог."""


class ChannelMessage(BaseModel):
    """Сообщение в терминах канала: адаптер сам решает, как его подать."""

    title: str
    body: str
    # Абсолютный URL; относительный путь во внешнем канале бесполезен
    link: str | None = None


class NotificationChannel(Protocol):
    """Канал доставки одному адресату."""

    kind: ClassVar[ChannelKind]

    async def send(self, address: str, message: ChannelMessage) -> None:
        """Отправить сообщение по адресу канала.

        Raises:
            NotifyError: При любой ошибке доставки.
        """
        ...
