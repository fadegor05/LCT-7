"""Сборка всех роутов (аналог plugins/Routing.kt).

Каждый домен экспортирует свой router; здесь они собираются в один api_router,
который main.py монтирует под settings.api_prefix.
"""

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Depends

from app.domains.assessment.router import router as assessment_router
from app.domains.assistant.router import router as assistant_router
from app.domains.methodology.router import equipment_router
from app.domains.methodology.router import router as methodology_router
from app.domains.observation.router import router as observation_router
from app.domains.photo.router import router as photo_router
from app.domains.schedule.router import router as schedule_router
from app.domains.site.router import router as site_router
from app.domains.user.auth_router import router as auth_router
from app.domains.user.provider import CurrentUser
from app.domains.user.router import router as user_router
from app.domains.utility.router import router as utility_router


@inject
async def require_auth(user: FromDishka[CurrentUser]) -> None:
    """Зависимость для проверки авторизации.

    Если токена нет или он невалиден, UserProvider.current_user
    поднимет AppError 401.
    """
    pass


api_router = APIRouter()

# Публичные роуты: аутентификация и служебные
api_router.include_router(auth_router)
api_router.include_router(utility_router)

# Защищённые роуты: требуют авторизации
api_router.include_router(user_router, dependencies=[Depends(require_auth)])
api_router.include_router(site_router, dependencies=[Depends(require_auth)])
api_router.include_router(schedule_router, dependencies=[Depends(require_auth)])
api_router.include_router(equipment_router, dependencies=[Depends(require_auth)])
api_router.include_router(methodology_router, dependencies=[Depends(require_auth)])
api_router.include_router(photo_router, dependencies=[Depends(require_auth)])
api_router.include_router(observation_router, dependencies=[Depends(require_auth)])
api_router.include_router(assessment_router, dependencies=[Depends(require_auth)])
api_router.include_router(assistant_router, dependencies=[Depends(require_auth)])
