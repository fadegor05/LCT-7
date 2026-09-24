"""Гвард доступа к сайтам: проверка прав владения."""

import uuid

from app.domains.site.models import Site
from app.domains.site.repository import SiteRepository
from app.domains.user.provider import CurrentUser
from app.plugins.exceptions import AppError


class SiteAccessGuard:
    """Проверяет право доступа к сайту по owner_id."""

    def __init__(self, repository: SiteRepository, current_user: CurrentUser) -> None:
        self._repository = repository
        self._current_user = current_user

    async def require(self, site_id: uuid.UUID) -> Site:
        """Загрузить сайт, проверить, что владелец текущий пользователь.

        Поднимает 404 если сайта нет или owner_id != текущему пользователю.
        """
        site = await self._repository.get(site_id)
        if site is None or site.owner_id != self._current_user.id:
            raise AppError("Стройка не найдена", status_code=404)
        return site
