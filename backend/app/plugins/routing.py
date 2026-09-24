"""Сборка всех роутов (аналог plugins/Routing.kt).

Каждый домен экспортирует свой router; здесь они собираются в один api_router,
который main.py монтирует под settings.api_prefix.
"""

from fastapi import APIRouter

from app.domains.schedule.router import router as schedule_router
from app.domains.site.router import router as site_router
from app.domains.user.router import router as user_router
from app.domains.utility.router import router as utility_router

api_router = APIRouter()
api_router.include_router(site_router)
api_router.include_router(schedule_router)
api_router.include_router(user_router)
api_router.include_router(utility_router)
