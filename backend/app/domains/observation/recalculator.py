"""Реализация ObservationRecalculator для photo: настоящий пересчёт через ObservationService."""

import uuid
from datetime import date

from app.domains.observation.service import ObservationService


class LiveObservationRecalculator:
    """Оборачивает ObservationService.recompute под протокол photo.recalculator.

    Реализует интерфейс ObservationRecalculator из photo.recalculator.
    """

    def __init__(self, service: ObservationService) -> None:
        self._service = service

    async def recompute(self, site_id: uuid.UUID, observed_on: date) -> None:
        await self._service.recompute(site_id, observed_on)
