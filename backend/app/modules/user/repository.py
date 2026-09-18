"""Доступ к данным пользователя (аналог UserRepository.kt).

Наследуется от BaseRepository — базовые запросы (list/get/get_by/add/delete)
приходят оттуда, здесь остаётся только специфика домена.
"""

from collections.abc import Sequence

from sqlalchemy import select

from app.core.repository import BaseRepository
from app.modules.user.models import User


class UserRepository(BaseRepository[User]):
    model = User

    async def list(self) -> Sequence[User]:
        result = await self._session.execute(select(User).order_by(User.created_at))
        return result.scalars().all()

    async def get_by_email(self, email: str) -> User | None:
        return await self.get_by(email=email)
