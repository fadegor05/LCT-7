"""Служебные роуты: liveness, readiness и версия сборки (аналог utility/Routes.kt)."""

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.domains.utility.schemas import HealthResponse, ReadyResponse, VersionResponse
from app.domains.utility.service import HealthService

router = APIRouter(tags=["utility"])


@router.get("/health")
async def health() -> HealthResponse:
    """Живость процесса: без DI, чтобы не зависеть от состояния инфраструктуры."""
    return HealthResponse(status="ok")


# response_model=None: при недоступной БД нужен собственный JSON-контракт с кодом 503,
# а не {"detail": ...} от AppError, поэтому роут возвращает либо схему, либо JSONResponse.
@router.get(
    "/ready",
    response_model=None,
    responses={200: {"model": ReadyResponse}, 503: {"model": ReadyResponse}},
)
@inject
async def ready(service: FromDishka[HealthService]) -> ReadyResponse | JSONResponse:
    if await service.check_ready():
        return ReadyResponse(database=True)
    return JSONResponse(
        status_code=503,
        content=ReadyResponse(database=False).model_dump(),
    )


@router.get("/version")
@inject
async def version(service: FromDishka[HealthService]) -> VersionResponse:
    return VersionResponse(version=service.get_version())
