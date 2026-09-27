"""Pydantic-схемы служебных эндпоинтов."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class DetectorStatus(BaseModel):
    """Статус детектора ML."""

    configured: bool
    ready: bool
    model: str | None = None


class ReadyResponse(BaseModel):
    """Статус готовности приложения."""

    database: bool
    detector: DetectorStatus | None = None


class VersionResponse(BaseModel):
    """Информация о версии приложения."""

    version: str
    model: str | None = None
