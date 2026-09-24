"""Pydantic-схемы служебных эндпоинтов."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    database: bool


class VersionResponse(BaseModel):
    version: str
