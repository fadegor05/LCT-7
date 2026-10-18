"""Доступ к данным камер стройки."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select

from app.core.repository import BaseRepository
from app.domains.camera.models import Camera
from app.domains.photo.models import Photo


class CameraRepository(BaseRepository[Camera]):
    model = Camera

    async def for_site(self, site_id: uuid.UUID) -> Sequence[Camera]:
        """Камеры объекта, в порядке создания."""
        result = await self._session.execute(
            select(Camera).where(Camera.site_id == site_id).order_by(Camera.created_at, Camera.id)
        )
        return result.scalars().all()

    async def photo_counts(self, camera_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, int]:
        """Сколько фотографий привязано к каждой камере (камеры без фото в словарь не попадают)."""
        if not camera_ids:
            return {}
        result = await self._session.execute(
            select(Photo.camera_id, func.count())
            .where(Photo.camera_id.in_(camera_ids))
            .group_by(Photo.camera_id)
        )
        return {camera_id: int(n) for camera_id, n in result.all()}
