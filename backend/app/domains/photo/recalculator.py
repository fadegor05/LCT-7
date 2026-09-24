"""Protocol для реакции на изменения дат фотографий (пересчёт наблюдений)."""

import uuid
from datetime import date
from typing import Protocol


class ObservationRecalculator(Protocol):
    """Пересчитать наблюдение стройки за дату.

    Реальная реализация предоставляется доменом observation (LCT-10).
    """

    async def recompute(self, site_id: uuid.UUID, observed_on: date) -> None: ...


class NoopObservationRecalculator:
    """No-op реализация (заглушка, пока observation не подключён в конкретном контейнере)."""

    async def recompute(self, site_id: uuid.UUID, observed_on: date) -> None:
        pass
