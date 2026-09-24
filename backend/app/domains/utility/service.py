"""Сервис для служебных эндпоинтов."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings


class HealthService:
    def __init__(self, session: AsyncSession, settings: Settings) -> None:
        self._session = session
        self._settings = settings

    async def check_ready(self) -> bool:
        try:
            await self._session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    def get_version(self) -> str:
        return self._settings.backend_tag
