"""Сервис для служебных эндпоинтов."""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ml.base import DetectorClient
from app.core.settings import Settings
from app.domains.utility.schemas import DetectorStatus

logger = logging.getLogger(__name__)


class HealthService:
    def __init__(self, session: AsyncSession, settings: Settings, detector: DetectorClient) -> None:
        self._session = session
        self._settings = settings
        self._detector = detector

    async def check_ready(self) -> bool:
        try:
            await self._session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def get_detector_status(self) -> DetectorStatus:
        """Получить статус детектора с защитой от таймаутов."""
        configured = self._detector.configured
        ready = False
        model = None

        if configured:
            try:
                # Защита от таймаутов: max 3 секунды на каждый вызов
                ready = await asyncio.wait_for(self._detector.ready(), timeout=3)
                info = await asyncio.wait_for(self._detector.info(), timeout=3)
                if info is not None:
                    model = info.model_version
            except TimeoutError:
                logger.warning("Детектор не ответил в течение 3 секунд")
                ready = False
            except Exception as e:
                logger.warning(f"Ошибка при проверке статуса детектора: {e}")
                ready = False

        return DetectorStatus(configured=configured, ready=ready, model=model)

    def get_version(self) -> str:
        return self._settings.backend_tag

    async def get_model_version(self) -> str | None:
        """Получить версию модели детектора."""
        try:
            # Защита от таймаутов: max 3 секунды
            info = await asyncio.wait_for(self._detector.info(), timeout=3)
            if info is not None:
                return info.model_version
        except Exception:
            pass
        return None
