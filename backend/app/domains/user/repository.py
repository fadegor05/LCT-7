"""Доступ к данным стендового пользователя.

Своих запросов нет: таблица из одной строки, хватает get/add из BaseRepository.
"""

from app.core.repository import BaseRepository
from app.domains.user.models import User


class UserRepository(BaseRepository[User]):
    model = User
