"""Служебные роуты: healthcheck (аналог utility/Routes.kt)."""

from fastapi import APIRouter

from app.domains.utility.schemas import HealthResponse

router = APIRouter(tags=["utility"])


@router.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
