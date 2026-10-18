"""Доступ к данным фотографий и детекций."""

import uuid
from collections.abc import Sequence

from sqlalchemy import delete, desc, select

from app.core.repository import BaseRepository
from app.domains.photo.models import Detection, Photo


class PhotoRepository(BaseRepository[Photo]):
    """Репозиторий фотографий."""

    model = Photo

    async def list_by_site(self, site_id: uuid.UUID, undated: bool = False) -> Sequence[Photo]:
        """Получить фотографии по site_id.

        Args:
            site_id: ID стройки.
            undated: Если True, возвращает только фотографии с captured_on IS NULL.
                     Если False, возвращает все фотографии сайта.

        Returns:
            Список фотографий, упорядочен по uploaded_at (возр.), потом по id.
        """
        query = select(self.model).where(self.model.site_id == site_id)
        if undated:
            query = query.where(self.model.captured_on.is_(None))
        query = query.order_by(self.model.uploaded_at, self.model.id)
        result = await self._session.execute(query)
        return result.scalars().all()

    async def get_in_site(self, site_id: uuid.UUID, photo_id: uuid.UUID) -> Photo | None:
        """Получить фотографию, убедившись, что она принадлежит сайту.

        Args:
            site_id: ID стройки.
            photo_id: ID фотографии.

        Returns:
            Photo если существует и принадлежит сайту, иначе None.
        """
        result = await self._session.execute(
            select(self.model).where((self.model.id == photo_id) & (self.model.site_id == site_id))
        )
        return result.scalar_one_or_none()

    async def list_by_status(self, site_id: uuid.UUID, statuses: set[str]) -> Sequence[Photo]:
        """Получить фотографии по site_id и статусам обработки.

        Args:
            site_id: ID стройки.
            statuses: Набор статусов (напр. {"pending", "failed"}).

        Returns:
            Список фотографий, упорядочен по uploaded_at (возр.), потом по id.
        """
        query = select(self.model).where(
            (self.model.site_id == site_id) & (self.model.processing_status.in_(statuses))
        )
        query = query.order_by(self.model.uploaded_at, self.model.id)
        result = await self._session.execute(query)
        return result.scalars().all()


class DetectionRepository(BaseRepository[Detection]):
    """Репозиторий детекций оборудования на фотографиях."""

    model = Detection

    async def list_by_photo(self, photo_id: uuid.UUID) -> Sequence[Detection]:
        """Получить детекции по фотографии.

        Args:
            photo_id: ID фотографии.

        Returns:
            Список детекций, упорядочен по score (убыв.), потом по id.
        """
        result = await self._session.execute(
            select(self.model)
            .where(self.model.photo_id == photo_id)
            .order_by(desc(self.model.score), self.model.id)
        )
        return result.scalars().all()

    async def list_by_photos(self, photo_ids: Sequence[uuid.UUID]) -> Sequence[Detection]:
        """Получить детекции нескольких фотографий одним запросом.

        Args:
            photo_ids: ID фотографий.

        Returns:
            Список детекций (порядок не важен для вызывающего).
        """
        if not photo_ids:
            return []
        result = await self._session.execute(
            select(self.model).where(self.model.photo_id.in_(photo_ids))
        )
        return result.scalars().all()

    async def add_many(self, detections: Sequence[Detection]) -> None:
        """Добавить несколько детекций и флашить.

        Args:
            detections: Список детекций для добавления.
        """
        self._session.add_all(detections)
        await self._session.flush()

    async def delete_by_photo(self, photo_id: uuid.UUID) -> None:
        """Удалить все детекции по фотографии.

        Args:
            photo_id: ID фотографии.
        """
        await self._session.execute(delete(self.model).where(self.model.photo_id == photo_id))
        await self._session.flush()

    async def model_versions(self, photo_id: uuid.UUID) -> set[str]:
        """Получить набор версий моделей детекторов для фотографии.

        Args:
            photo_id: ID фотографии.

        Returns:
            Набор уникальных значений model_version для детекций фотографии.
        """
        result = await self._session.execute(
            select(self.model.model_version).where(self.model.photo_id == photo_id)
        )
        return set(result.scalars().all())
