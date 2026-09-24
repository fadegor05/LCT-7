"""Реализация StatusRecalculator поверх RecomputeCoordinator (LCT-11)."""

import logging
import uuid

from app.domains.assessment.coordinator import RecomputeCoordinator

logger = logging.getLogger(__name__)


class LiveStatusRecalculator:
    """Реализация StatusRecalculator поверх RecomputeCoordinator.

    Используется для пересчёта статуса проверяемости сайта при изменении методики.
    Поглощает исключения и логирует их (не пробрасывает).
    """

    def __init__(self, coordinator: RecomputeCoordinator) -> None:
        """Инициализировать LiveStatusRecalculator.

        Args:
            coordinator: RecomputeCoordinator для оркестрации переучёта.
        """
        self._coordinator = coordinator

    async def recalculate(self, site_id: uuid.UUID) -> None:
        """Пересчитать статус проверяемости сайта.

        Реализует StatusRecalculator Protocol: async def recalculate(site_id: uuid.UUID) -> None

        Поглощает исключения и логирует их как ошибки (не пробрасывает).

        Args:
            site_id: ID сайта для пересчёта.
        """
        try:
            await self._coordinator.recompute_site(site_id)
        except Exception:
            logger.exception("Assessment recompute failed for site=%s", site_id)
