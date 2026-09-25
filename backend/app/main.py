"""Точка входа FastAPI (аналог Application.kt).

Запуск в проде/деве через Granian:
    granian --interface asgi app.main:app --host 0.0.0.0 --port 8000
"""

import logging
from contextlib import asynccontextmanager

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI

from app.adapters.ml.base import DetectorClient
from app.core.settings import get_settings
from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.photo.startup import check_detector_classes
from app.domains.user.service import UserService
from app.plugins.di import create_container
from app.plugins.exceptions import register_exception_handlers
from app.plugins.routing import api_router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Схема БД накатывается миграциями Alembic (`alembic upgrade head`) до старта
    # сервера — см. команду запуска в deploy/docker/dev/core.yaml и Dockerfile.
    # Здесь только идемпотентный seed стендового пользователя.
    async with app.state.dishka_container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()

    # Проверяем соответствие классов детектора каталогу оборудования
    try:
        detector = await app.state.dishka_container.get(DetectorClient)
        catalog = await app.state.dishka_container.get(EquipmentCatalog)
        await check_detector_classes(detector, catalog)
    except Exception as e:
        logger.warning(f"Ошибка при проверке классов детектора при запуске: {e}")

    yield
    await app.state.dishka_container.close()


def create_app(container: AsyncContainer | None = None) -> FastAPI:
    app = FastAPI(
        title="LCT-7 API",
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )

    setup_dishka(container or create_container(), app)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
