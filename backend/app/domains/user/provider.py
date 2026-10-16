"""DI-провайдер домена user.

CurrentUser разрешается из JWT токена в Authorization header.
"""

import logging
from typing import NewType

from dishka import Provider, Scope, from_context, provide
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.settings import Settings
from app.domains.user.auth_service import AuthService
from app.domains.user.models import User
from app.domains.user.repository import UserRepository
from app.domains.user.security import decode_token
from app.domains.user.service import UserService
from app.plugins.exceptions import AppError

logger = logging.getLogger(__name__)

CurrentUser = NewType("CurrentUser", User)
LoginRateLimiter = NewType("LoginRateLimiter", SlidingWindowRateLimiter)


class UserProvider(Provider):
    scope = Scope.REQUEST

    request = from_context(provides=Request, scope=Scope.REQUEST)
    repository = provide(UserRepository)

    @provide(scope=Scope.APP)
    def login_rate_limiter(self, settings: Settings) -> LoginRateLimiter:
        return LoginRateLimiter(
            SlidingWindowRateLimiter(
                limit=settings.auth.login_rate_limit_per_min,
                window_s=60.0,
            )
        )

    @provide(scope=Scope.REQUEST)
    async def service(
        self, repository: UserRepository, session: AsyncSession, settings: Settings
    ) -> UserService:
        return UserService(repository, session, settings.auth)

    @provide(scope=Scope.REQUEST)
    async def auth_service(
        self, repository: UserRepository, session: AsyncSession, settings: Settings
    ) -> AuthService:
        return AuthService(repository, session, settings.auth)

    @provide(scope=Scope.REQUEST)
    async def current_user(
        self, request: Request, repository: UserRepository, settings: Settings
    ) -> CurrentUser:
        """Разрешить CurrentUser из JWT токена в Authorization header.

        Если нет токена или токен невалиден -> AppError 401.
        Если пользователь не найден -> AppError 401.
        """
        # Читаем заголовок Authorization
        auth_header = request.headers.get("Authorization", "")

        # Проверяем формат "Bearer <token>"
        if not auth_header.startswith("Bearer "):
            raise AppError("Требуется авторизация", status_code=401)

        token = auth_header[7:]  # Срезаем "Bearer "

        # Декодируем токен, поднимает AppError 401 если невалиден
        user_id = decode_token(token, settings.auth)

        # Загружаем пользователя по ID
        user = await repository.get(user_id)
        if user is None:
            raise AppError("Требуется авторизация", status_code=401)

        return CurrentUser(user)
