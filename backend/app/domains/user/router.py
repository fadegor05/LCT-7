"""HTTP-роуты текущего пользователя.

Регистрации нет (пользователей создаёт CLI), вход — в auth_router. Здесь только чтение
и смена ФИО, которым подписываются решения инженера.
"""

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from app.domains.user.provider import CurrentUser
from app.domains.user.schemas import UserRead, UserUpdate
from app.domains.user.service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
@inject
async def read_me(user: FromDishka[CurrentUser]) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/me")
@inject
async def update_me(data: UserUpdate, service: FromDishka[UserService]) -> UserRead:
    user = await service.rename(data.full_name)
    return UserRead.model_validate(user)
