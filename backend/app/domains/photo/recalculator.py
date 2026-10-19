"""Protocol для реакции на изменения дат фотографий (пересчёт наблюдений)."""

import uuid
from collections.abc import Iterable
from datetime import date
from typing import Protocol


class ObservationRecalculator(Protocol):
    """Пересчитать наблюдение стройки за дату.

    Реальная реализация предоставляется доменом observation (LCT-10).
    """

    async def recompute(self, site_id: uuid.UUID, observed_on: date) -> None: ...

    async def recompute_many(self, site_id: uuid.UUID, dates: Iterable[date]) -> None:
        """Несколько дат — один пересчёт статусов объекта в конце (очередь загрузки)."""
        ...


class NoopObservationRecalculator:
    """No-op реализация (заглушка, пока observation не подключён в конкретном контейнере)."""

    async def recompute(self, site_id: uuid.UUID, observed_on: date) -> None:
        pass

    async def recompute_many(self, site_id: uuid.UUID, dates: Iterable[date]) -> None:
        pass
