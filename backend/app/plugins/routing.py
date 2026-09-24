"""Сборка всех роутов (аналог plugins/Routing.kt).

Каждый домен экспортирует свой router; здесь они собираются в один api_router,
который main.py монтирует под settings.api_prefix.
"""

from fastapi import APIRouter

from app.domains.methodology.router import equipment_router
from app.domains.methodology.router import router as methodology_router
from app.domains.observation.router import router as observation_router
from app.domains.photo.router import router as photo_router
from app.domains.schedule.router import router as schedule_router
from app.domains.site.router import router as site_router
from app.domains.user.router import router as user_router
from app.domains.utility.router import router as utility_router

api_router = APIRouter()
api_router.include_router(site_router)
api_router.include_router(schedule_router)
api_router.include_router(user_router)
api_router.include_router(utility_router)
api_router.include_router(equipment_router)
api_router.include_router(methodology_router)
api_router.include_router(photo_router)
api_router.include_router(observation_router)
