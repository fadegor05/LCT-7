"""PhotoRepository и DetectionRepository: list_by_site, list_by_photo, etc."""

import uuid
from datetime import UTC, date, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.methodology.models import EquipmentType
from app.domains.photo.models import Detection, Photo, ProcessingStatus
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.site.models import Site
from app.domains.user.models import User


async def seed_data(
    container,
) -> tuple[uuid.UUID, uuid.UUID, list[uuid.UUID], uuid.UUID]:
    """Подготовить тестовые данные: пользователя, сайт, фото, детекции, оборудование.

    Returns:
        (user_id, site_id, [photo_ids], equipment_type_id)
    """
    user_id = uuid.uuid4()
    site_id = uuid.uuid4()
    equipment_type_id = uuid.uuid4()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)

        # Создаём пользователя
        user = User(id=user_id, full_name="Test User")
        session.add(user)

        # Создаём сайт
        site = Site(id=site_id, name="Test Site", owner_id=user_id)
        session.add(site)

        # Создаём тип оборудования
        equipment_type = EquipmentType(
            id=equipment_type_id, code="CRANE_1", title="Crane Type A", synonyms=[]
        )
        session.add(equipment_type)

        # Создаём фотографии
        photo_ids = []
        for i in range(3):
            photo_id = uuid.uuid4()
            photo_ids.append(photo_id)
            # Первые две - с датой, третья - нет
            captured_on = date(2025, 1, i + 1) if i < 2 else None
            photo = Photo(
                id=photo_id,
                site_id=site_id,
                storage_key=f"photo_{i}.jpg",
                original_name=f"photo_{i}.jpg",
                width=800,
                height=600,
                captured_on=captured_on,
                date_source="metadata" if captured_on else None,
                processing_status=ProcessingStatus.PENDING.value,
                uploaded_at=datetime(2025, 1, 10 + i, tzinfo=UTC),
            )
            session.add(photo)

        # Создаём детекции для фото[0]
        detection1 = Detection(
            id=uuid.uuid4(),
            photo_id=photo_ids[0],
            equipment_type_id=equipment_type_id,
            bbox=[0.1, 0.2, 0.3, 0.4],
            score=0.95,
            model_version="yoloe-26s.pt",
        )
        detection2 = Detection(
            id=uuid.uuid4(),
            photo_id=photo_ids[0],
            equipment_type_id=equipment_type_id,
            bbox=[0.5, 0.5, 0.7, 0.7],
            score=0.85,
            model_version="yoloe-26s.pt",
        )
        session.add(detection1)
        session.add(detection2)

        # Создаём детекцию для фото[1] с другой версией модели
        detection3 = Detection(
            id=uuid.uuid4(),
            photo_id=photo_ids[1],
            equipment_type_id=equipment_type_id,
            bbox=[0.2, 0.3, 0.4, 0.5],
            score=0.90,
            model_version="yoloe-27m.pt",
        )
        session.add(detection3)

        await session.commit()

    return user_id, site_id, photo_ids, equipment_type_id


class TestPhotoRepository:
    """Тесты PhotoRepository."""

    @pytest.mark.asyncio
    async def test_list_by_site_returns_all_photos(self, container) -> None:
        """list_by_site() возвращает все фотографии сайта."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(PhotoRepository)
            photos = await repo.list_by_site(site_id)

        assert len(photos) == 3
        assert {p.id for p in photos} == set(photo_ids)

    @pytest.mark.asyncio
    async def test_list_by_site_orders_by_uploaded_at_then_id(self, container) -> None:
        """list_by_site() упорядочивает по uploaded_at (возрастанию), затем по id."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(PhotoRepository)
            photos = await repo.list_by_site(site_id)

        # Проверяем, что упорядочены правильно
        uploaded_at_values = [p.uploaded_at for p in photos]
        assert uploaded_at_values == sorted(uploaded_at_values)

    @pytest.mark.asyncio
    async def test_list_by_site_undated_returns_only_null_captured_on(self, container) -> None:
        """list_by_site(undated=True) возвращает только фотографии с captured_on IS NULL."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(PhotoRepository)
            photos = await repo.list_by_site(site_id, undated=True)

        assert len(photos) == 1
        assert photos[0].id == photo_ids[2]  # Третья фотография (без даты)
        assert photos[0].captured_on is None

    @pytest.mark.asyncio
    async def test_get_in_site_returns_photo_if_belongs_to_site(self, container) -> None:
        """get_in_site() возвращает фотографию, если она принадлежит сайту."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(PhotoRepository)
            photo = await repo.get_in_site(site_id, photo_ids[0])

        assert photo is not None
        assert photo.id == photo_ids[0]
        assert photo.site_id == site_id

    @pytest.mark.asyncio
    async def test_get_in_site_returns_none_if_not_belongs_to_site(self, container) -> None:
        """get_in_site() возвращает None, если фотография другого сайта."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        other_site_id = uuid.uuid4()

        async with container() as request_container:
            repo = await request_container.get(PhotoRepository)
            photo = await repo.get_in_site(other_site_id, photo_ids[0])

        assert photo is None

    @pytest.mark.asyncio
    async def test_get_in_site_returns_none_if_photo_not_found(self, container) -> None:
        """get_in_site() возвращает None, если фотография не существует."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        non_existent_id = uuid.uuid4()

        async with container() as request_container:
            repo = await request_container.get(PhotoRepository)
            photo = await repo.get_in_site(site_id, non_existent_id)

        assert photo is None


class TestDetectionRepository:
    """Тесты DetectionRepository."""

    @pytest.mark.asyncio
    async def test_list_by_photo_returns_all_detections(self, container) -> None:
        """list_by_photo() возвращает все детекции фотографии."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(DetectionRepository)
            detections = await repo.list_by_photo(photo_ids[0])

        assert len(detections) == 2

    @pytest.mark.asyncio
    async def test_list_by_photo_orders_by_score_desc_then_id(self, container) -> None:
        """list_by_photo() упорядочивает по score (убыванию), затем по id."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(DetectionRepository)
            detections = await repo.list_by_photo(photo_ids[0])

        # Проверяем упорядочивание по score (убыванию)
        scores = [d.score for d in detections]
        assert scores == sorted(scores, reverse=True)
        # Проверяем, что первая детекция с более высоким score
        assert detections[0].score == 0.95
        assert detections[1].score == 0.85

    @pytest.mark.asyncio
    async def test_add_many_flushes_detections(self, container) -> None:
        """add_many() добавляет несколько детекций и флашит."""
        user_id, site_id, photo_ids, equipment_type_id = await seed_data(container)

        new_detection_id = uuid.uuid4()
        new_detection = Detection(
            id=new_detection_id,
            photo_id=photo_ids[2],  # Фотография без детекций
            equipment_type_id=equipment_type_id,
            bbox=[0.1, 0.1, 0.2, 0.2],
            score=0.75,
            model_version="yoloe-26s.pt",
        )

        async with container() as request_container:
            repo = await request_container.get(DetectionRepository)
            await repo.add_many([new_detection])
            session = await request_container.get(AsyncSession)
            await session.commit()

        # Проверяем, что детекция была добавлена
        async with container() as request_container:
            repo = await request_container.get(DetectionRepository)
            detections = await repo.list_by_photo(photo_ids[2])

        assert len(detections) == 1
        assert detections[0].id == new_detection_id

    @pytest.mark.asyncio
    async def test_delete_by_photo_removes_all_detections(self, container) -> None:
        """delete_by_photo() удаляет все детекции фотографии."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(DetectionRepository)
            await repo.delete_by_photo(photo_ids[0])
            session = await request_container.get(AsyncSession)
            await session.commit()

        # Проверяем, что детекции удалены
        async with container() as request_container:
            repo = await request_container.get(DetectionRepository)
            detections = await repo.list_by_photo(photo_ids[0])

        assert len(detections) == 0

    @pytest.mark.asyncio
    async def test_model_versions_returns_unique_versions(self, container) -> None:
        """model_versions() возвращает набор уникальных версий моделей."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(DetectionRepository)
            versions = await repo.model_versions(photo_ids[0])

        assert versions == {"yoloe-26s.pt"}

    @pytest.mark.asyncio
    async def test_model_versions_handles_multiple_versions(self, container) -> None:
        """model_versions() корректно работает с несколькими версиями моделей."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(DetectionRepository)
            # photo_ids[0] имеет обе детекции с yoloe-26s.pt
            # photo_ids[1] имеет yoloe-27m.pt
            versions_0 = await repo.model_versions(photo_ids[0])
            versions_1 = await repo.model_versions(photo_ids[1])

        assert versions_0 == {"yoloe-26s.pt"}
        assert versions_1 == {"yoloe-27m.pt"}

    @pytest.mark.asyncio
    async def test_model_versions_returns_empty_set_for_no_detections(self, container) -> None:
        """model_versions() возвращает пустой набор, если детекций нет."""
        user_id, site_id, photo_ids, _ = await seed_data(container)

        async with container() as request_container:
            repo = await request_container.get(DetectionRepository)
            versions = await repo.model_versions(photo_ids[2])  # Фотография без детекций

        assert versions == set()
