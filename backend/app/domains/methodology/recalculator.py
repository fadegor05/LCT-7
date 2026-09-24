"""Интерфейс и реализация для пересчёта статуса проверяемости сайта."""

import uuid
from typing import Protocol


class StatusRecalculator(Protocol):
    """Протокол для пересчёта статуса проверяемости сайта.

    Используется для обновления статуса сайта когда меняются правила методологии.
    Реальная реализация предоставляется доменом assessment (LCT-11).
    """

    async def recalculate(self, site_id: uuid.UUID) -> None:
        """Пересчитать статус проверяемости сайта.

        Args:
            site_id: ID сайта для пересчёта

        Raises:
            Может выбросить исключение при ошибке в слое assessment
        """
        ...


class NoopStatusRecalculator:
    """No-op реализация StatusRecalculator (ничего не делает).

    Используется как заглушка при разработке до появления реального пересчётчика
    в доме assessment (LCT-11).
    """

    async def recalculate(self, site_id: uuid.UUID) -> None:
        """Ничего не делать (no-op).

        Args:
            site_id: ID сайта (игнорируется)
        """
        pass
