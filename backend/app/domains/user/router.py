"""HTTP-роуты стендового пользователя."""

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter

from app.domains.user.provider import CurrentUser
from app.domains.user.schemas import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me")
@inject
async def read_me(user: FromDishka[CurrentUser]) -> UserRead:
    return UserRead.model_validate(user)
