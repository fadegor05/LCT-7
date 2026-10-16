"""Логика стендовой идентичности и аутентификации.

В MVP пользователь один, его идентификатор зафиксирован константой,
а строка создаётся при старте приложения.
"""

import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import AuthSettings
from app.domains.user.models import User
from app.domains.user.repository import UserRepository
from app.domains.user.security import hash_password
from app.plugins.exceptions import AppError

logger = logging.getLogger(__name__)

# Идентификатор единственного пользователя стенда зашит константой, чтобы ссылки
# site.created_by и hypothesis_decision.decided_by переживали перезапуск сервиса.
STAND_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
STAND_USER_DEFAULT_NAME = "Инженер стройплощадки"


class UserService:
    def __init__(
        self,
        repository: UserRepository,
        session: AsyncSession,
        settings: AuthSettings | None = None,
    ) -> None:
        self._repository = repository
        self._session = session
        self._settings = settings

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

    async def ensure_seed_credentials(self) -> None:
        """Идемпотентный seed: установить логин и пароль для стендового пользователя.

        Вызывается при старте приложения, если settings.auth.seed_login и seed_password
        установлены, устанавливает их для стендового пользователя.
        Идемпотентен: не перетирает существующий логин/пароль.
        """
        if self._settings is None:
            return

        user = await self.get_current()

        # Если уже есть логин, ничего не делаем
        if user.login is not None:
            return

        # Если нет seed-данных, логируем warning
        if not self._settings.seed_login or not self._settings.seed_password:
            logger.warning("Stand user has no login and no seed credentials configured")
            return

        user.login = self._settings.seed_login.lower()
        user.password_hash = await hash_password(self._settings.seed_password)
        await self._session.commit()

        logger.info(f"Seeded stand user with login: {user.login}")
