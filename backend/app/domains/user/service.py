"""Логика стендовой идентичности.

Авторизации в MVP нет (product.md §14): пользователь один, его идентификатор
зафиксирован константой, а строка создаётся при старте приложения.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.user.models import User
from app.domains.user.repository import UserRepository
from app.plugins.exceptions import AppError

# Идентификатор единственного пользователя стенда зашит константой, чтобы ссылки
# site.created_by и hypothesis_decision.decided_by переживали перезапуск сервиса.
STAND_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
STAND_USER_DEFAULT_NAME = "Инженер стройплощадки"


class UserService:
    def __init__(self, repository: UserRepository, session: AsyncSession) -> None:
        self._repository = repository
        self._session = session

    async def ensure_stand_user(self) -> User:
        """Идемпотентный seed: вызывается на каждом старте и не перетирает ФИО."""
        user = await self._repository.get(STAND_USER_ID)
        if user is not None:
            return user

        user = User(id=STAND_USER_ID, full_name=STAND_USER_DEFAULT_NAME)
        await self._repository.add(user)
        await self._session.commit()
        return user

    async def get_current(self) -> User:
        user = await self._repository.get(STAND_USER_ID)
        if user is None:
            raise AppError(
                "Стенд не инициализирован: пользователь не создан",
                status_code=503,
            )
        return user

    async def rename(self, full_name: str) -> User:
        user = await self.get_current()
        user.full_name = full_name
        await self._session.commit()
        return user
