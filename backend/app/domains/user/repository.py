"""Доступ к данным стендового пользователя.

Своих запросов нет: таблица из одной строки, хватает get/add из BaseRepository.
"""

from app.core.repository import BaseRepository
from app.domains.user.models import User


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_login(self, login: str) -> User | None:
        """Найти пользователя по логину (в нижнем регистре)."""
        return await self.get_by(login=login.lower())
