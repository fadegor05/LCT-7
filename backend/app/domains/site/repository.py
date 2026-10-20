"""Доступ к данным объектов строительства."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select

from app.core.repository import BaseRepository
from app.domains.site.models import Site


class SiteRepository(BaseRepository[Site]):
    model = Site

    async def list_by_owner(self, owner_id: uuid.UUID) -> Sequence[Site]:
        """Получить сайты владельца, упорядочены по created_at (новые первыми)."""
        result = await self._session.execute(
            select(self.model)
            .where(self.model.owner_id == owner_id)
            .order_by(self.model.created_at.desc())
        )
        return result.scalars().all()

    async def list_owner_ids(self) -> Sequence[uuid.UUID]:
        """Владельцы, у которых есть хотя бы один объект."""
        result = await self._session.execute(select(self.model.owner_id).distinct())
        return result.scalars().all()
