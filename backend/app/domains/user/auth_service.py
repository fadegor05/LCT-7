"""Логика аутентификации (вход по логину и паролю)."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import AuthSettings
from app.domains.user.models import User
from app.domains.user.repository import UserRepository
from app.domains.user.security import create_token, verify_against_dummy, verify_password
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
