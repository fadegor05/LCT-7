"""Логика аутентификации (вход по логину и паролю)."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import AuthSettings
from app.domains.user.models import User
from app.domains.user.repository import UserRepository
from app.domains.user.security import (
    create_token,
    hash_password,
    verify_against_dummy,
    verify_password,
)
from app.plugins.exceptions import AppError


class AuthService:
    """Сервис аутентификации."""

    def __init__(
        self, repository: UserRepository, session: AsyncSession, settings: AuthSettings
    ) -> None:
        self._repository = repository
        self._session = session
        self._settings = settings

    async def login(self, login: str, password: str) -> tuple[str, User]:
        """Аутентифицировать по логину и паролю.

        Возвращает (token, user) если успешно.
        Поднимает AppError 401 если логин или пароль неверны.
        """
        login_lower = login.strip().lower()
        user = await self._repository.get_by_login(login_lower)

        if user is None:
            await verify_against_dummy(password)
            raise AppError("Неверный логин или пароль", status_code=401)

        if not user.password_hash or not (await verify_password(password, user.password_hash)):
            raise AppError("Неверный логин или пароль", status_code=401)

        token = create_token(user.id, self._settings)
        return token, user

    async def register(self, login: str, password: str, full_name: str | None) -> tuple[str, User]:
        """Зарегистрировать пользователя и сразу выдать токен.

        Поднимает AppError 409, если логин занят (в том числе при гонке двух запросов:
        её ловит уникальный индекс).
        """
        login_lower = login.strip().lower()
        taken = AppError("Логин уже занят", status_code=409, code="login_taken")

        if await self._repository.get_by_login(login_lower) is not None:
            raise taken

        user = User(
            id=uuid.uuid4(),
            full_name=(full_name or "").strip() or login_lower,
            login=login_lower,
            password_hash=await hash_password(password),
        )
        try:
            await self._repository.add(user)
            await self._session.commit()
        except IntegrityError:
            await self._session.rollback()
            raise taken from None

        return create_token(user.id, self._settings), user
