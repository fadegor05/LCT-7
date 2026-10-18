"""Шов доставки: сервис уведомлений просит отправить, не зная как.

Настоящая реализация (BackgroundDispatcher) появляется вместе с адаптерами каналов;
здесь интерфейс и пустышка, с которой работают тесты сервиса.
"""

import uuid
from typing import Protocol


class NotificationDispatcher(Protocol):
    """Планировщик доставки. Синхронный: вызывается из уже закоммиченного сервиса."""

    def schedule(self, notification_id: uuid.UUID) -> None:
        """Запланировать доставку уведомления по привязанным каналам."""
        ...


class NullDispatcher:
    """Ничего не доставляет. Умолчание, когда каналы не настроены."""

    def schedule(self, notification_id: uuid.UUID) -> None:
        return None
