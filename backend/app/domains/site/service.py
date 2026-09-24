"""Бизнес-логика объектов строительства."""

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.site.guard import SiteAccessGuard
from app.domains.site.models import Site
from app.domains.site.repository import SiteRepository
from app.domains.site.schemas import SiteCreate, SiteUpdate
from app.domains.user.provider import CurrentUser
from app.plugins.exceptions import AppError


class SiteService:
    """CRUD и бизнес-логика сайтов."""

    def __init__(
        self,
        repository: SiteRepository,
        session: AsyncSession,
        guard: SiteAccessGuard,
        current_user: CurrentUser,
    ) -> None:
        self._repository = repository
        self._session = session
        self._guard = guard
        self._current_user = current_user

    async def create(self, data: SiteCreate) -> Site:
        """Создать сайт текущего пользователя."""
        site = Site(name=data.name, address=data.address, owner_id=self._current_user.id)
        await self._repository.add(site)
        await self._session.commit()
        return site

    async def list(self) -> Sequence[Site]:
        """Получить все сайты текущего пользователя."""
        return await self._repository.list_by_owner(self._current_user.id)

    async def get(self, site_id: uuid.UUID) -> Site:
        """Получить сайт с проверкой доступа."""
        return await self._guard.require(site_id)

    async def update(self, site_id: uuid.UUID, data: SiteUpdate) -> Site:
        """Обновить сайт (только свои поля, без None для name)."""
        site = await self._guard.require(site_id)

        # Получить только установленные поля
        update_dict = data.model_dump(exclude_unset=True)

        # Запретить явный None для name
        if "name" in update_dict and update_dict["name"] is None:
            raise AppError("name не может быть null", status_code=422)

        # Применить только установленные поля
        for key, value in update_dict.items():
            setattr(site, key, value)

        await self._session.commit()
        await self._session.refresh(site)
        return site

    async def delete(self, site_id: uuid.UUID) -> None:
        """Удалить сайт с проверкой доступа."""
        site = await self._guard.require(site_id)
        await self._repository.delete(site)
        await self._session.commit()
