"""Доступ к данным фотографий и детекций."""

import uuid
from collections.abc import Sequence
from typing import cast

from sqlalchemy import CursorResult, delete, desc, func, select, update

from app.core.repository import BaseRepository
from app.domains.photo.models import IN_QUEUE, Detection, Photo, ProcessingStatus


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
            # Кадр в очереди ещё не получил дату — он не «без даты», его рано разбирать
            query = query.where(
                self.model.captured_on.is_(None), self.model.processing_status.not_in(IN_QUEUE)
            )
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

    async def count_in_queue(self, site_id: uuid.UUID) -> int:
        """Сколько кадров объекта ещё в очереди или в обработке."""
        result = await self._session.execute(
            select(func.count())
            .select_from(self.model)
            .where(self.model.site_id == site_id, self.model.processing_status.in_(IN_QUEUE))
        )
        return int(result.scalar_one())

    async def queue_counts(self, site_id: uuid.UUID) -> tuple[int, int]:
        """(ждут, обрабатываются) по объекту."""
        result = await self._session.execute(
            select(self.model.processing_status, func.count())
            .where(self.model.site_id == site_id, self.model.processing_status.in_(IN_QUEUE))
            .group_by(self.model.processing_status)
        )
        counts = {status: count for status, count in result.all()}
        return (
            int(counts.get(ProcessingStatus.QUEUED.value, 0)),
            int(counts.get(ProcessingStatus.PROCESSING.value, 0)),
        )

    async def list_in_batches(self, site_id: uuid.UUID) -> Sequence[Photo]:
        """Кадры объекта из незакрытых пачек загрузки."""
        result = await self._session.execute(
            select(self.model)
            .where(self.model.site_id == site_id, self.model.upload_batch_id.is_not(None))
            .order_by(self.model.upload_batch_id, self.model.upload_batch_pos)
        )
        return result.scalars().all()

    async def claim_queued(self, limit: int) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """Взять до `limit` кадров из очереди в обработку: (кадр, объект), старые первыми.

        `FOR UPDATE SKIP LOCKED`: при нескольких экземплярах кадр берёт один. Коммитит
        вызывающий — до этого кадры заблокированы.
        """
        result = await self._session.execute(
            select(self.model)
            .where(self.model.processing_status == ProcessingStatus.QUEUED.value)
            .order_by(self.model.uploaded_at, self.model.upload_batch_pos, self.model.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
        photos = result.scalars().all()
        for photo in photos:
            photo.processing_status = ProcessingStatus.PROCESSING.value
        return [(p.id, p.site_id) for p in photos]

    async def requeue_processing(self) -> int:
        """После перезапуска: кадры, оборванные посреди обработки, — снова в очередь."""
        result = await self._session.execute(
            update(self.model)
            .where(self.model.processing_status == ProcessingStatus.PROCESSING.value)
            .values(processing_status=ProcessingStatus.QUEUED.value)
        )
        return int(cast(CursorResult, result).rowcount or 0)

    async def sites_with_open_batches(self) -> list[uuid.UUID]:
        """Объекты с незакрытыми пачками — закрыть их, если очередь уже пуста."""
        result = await self._session.execute(
            select(self.model.site_id).where(self.model.upload_batch_id.is_not(None)).distinct()
        )
        return list(result.scalars().all())


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
