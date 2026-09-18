"""Доступ к данным пользователя (аналог UserRepository.kt)."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.user.models import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> Sequence[User]:
        result = await self._session.execute(select(User).order_by(User.created_at))
        return result.scalars().all()

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def add(self, user: User) -> User:
        self._session.add(user)
        await self._session.flush()
        return user
