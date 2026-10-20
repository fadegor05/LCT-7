"""ObservationService тесты: recompute, list_observations, get_observation."""

import uuid
from datetime import date, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.domains.camera.models import Camera
from app.domains.methodology.catalog import EquipmentCatalog
from app.domains.methodology.models import EquipmentType
from app.domains.methodology.recalculator import NoopStatusRecalculator
from app.domains.observation.activity import ActivityParams
from app.domains.observation.models import ObservedEquipment
from app.domains.observation.policies import (
    ActivityPolicy,
    AggregationPolicy,
    ObservabilityPolicy,
)
from app.domains.observation.repository import ObservationRepository, ObservedEquipmentRepository
from app.domains.observation.service import ObservationService
from app.domains.photo.models import DateSource, Detection, Photo, ProcessingStatus
from app.domains.photo.repository import DetectionRepository, PhotoRepository
from app.domains.site.guard import SiteAccessGuard
from app.domains.site.models import Site
from app.domains.user.models import User
from app.domains.user.service import UserService
from app.plugins.exceptions import AppError


async def seed_user(container) -> None:
    """Создаёт стендового пользователя."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


async def seed_test_data(
    session: AsyncSession, site_id: uuid.UUID, owner_id: uuid.UUID
) -> dict[str, uuid.UUID]:
    """Создать базовые тестовые данные.

    Возвращает словарь с ID типов техники.
    """
    # Создаём типы техники
    eq_crane = EquipmentType(id=uuid.uuid4(), code="crane", title="Кран", synonyms=[])
    eq_excavator = EquipmentType(id=uuid.uuid4(), code="excavator", title="Экскаватор", synonyms=[])
    session.add(eq_crane)
    session.add(eq_excavator)
    await session.commit()

    return {"crane": eq_crane.id, "excavator": eq_excavator.id}


class TestObservationServiceRecompute:
    """Тесты метода recompute."""

    @pytest.mark.asyncio
    async def test_recompute_happy_path(self, container) -> None:
        """Happy path: фото с датой и детекциями -> создаёт наблюдение."""
        await seed_user(container)

        site_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        obs_date = date(2025, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=owner_id, full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner_id)
            session.add(site)

            equipment_ids = await seed_test_data(session, site_id, owner_id)

            # Создаём фото
            photo = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="test.jpg",
                original_name="test.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo)
            await session.flush()

            # Создаём детекции
            det1 = Detection(
                id=uuid.uuid4(),
                photo_id=photo.id,
                equipment_type_id=equipment_ids["crane"],
                bbox=[0.1, 0.1, 0.5, 0.5],
                score=0.9,
                model_version="v1",
            )
            session.add(det1)
            await session.commit()

        # Запускаем recompute
        async with container() as request_container:
            service = await self._create_service(request_container)
            result = await service.recompute(site_id, obs_date)

        assert result is not None
        assert result.site_id == site_id
        assert result.observed_on == obs_date
        assert result.photo_count == 1
        assert result.observability == "low"  # 1 фото при min_photos_medium=2 -> low

    @pytest.mark.asyncio
    async def test_recompute_activity_basis_names_camera_zone(self, container) -> None:
        """Название зоны камеры доходит через сервис до основания активности техники."""
        await seed_user(container)

        site_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        camera_id = uuid.uuid4()
        obs_date = date(2025, 1, 15)
        left_half = [[0.0, 0.0], [0.5, 0.0], [0.5, 1.0], [0.0, 1.0]]

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            session.add(User(id=owner_id, full_name="Owner"))
            session.add(Site(id=site_id, name="Test Site", owner_id=owner_id))
            equipment_ids = await seed_test_data(session, site_id, owner_id)
            session.add(
                Camera(
                    id=camera_id,
                    site_id=site_id,
                    name="Север",
                    zone=left_half,
                    zone_name="Въезд",
                )
            )
            await session.flush()
            # Два кадра одной камеры: машина стоит правее зоны, то есть вне неё
            for minute in (0, 5):
                photo = Photo(
                    id=uuid.uuid4(),
                    site_id=site_id,
                    storage_key=f"test-{minute}.jpg",
                    original_name=f"test-{minute}.jpg",
                    width=100,
                    height=100,
                    captured_on=obs_date,
                    captured_at=datetime(2025, 1, 15, 10, minute),
                    camera_id=camera_id,
                    date_source=DateSource.MANUAL.value,
                    processing_status=ProcessingStatus.DONE.value,
                )
                session.add(photo)
                await session.flush()
                session.add(
                    Detection(
                        id=uuid.uuid4(),
                        photo_id=photo.id,
                        equipment_type_id=equipment_ids["crane"],
                        bbox=[0.7, 0.1, 0.8, 0.2],
                        score=0.9,
                        model_version="v1",
                    )
                )
            await session.commit()

        async with container() as request_container:
            service = await self._create_service(request_container)
            result = await service.recompute(site_id, obs_date)

        assert result is not None
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            rows = (
                (
                    await session.execute(
                        select(ObservedEquipment).where(
                            ObservedEquipment.observation_id == result.id
                        )
                    )
                )
                .scalars()
                .all()
            )

        (row,) = rows
        assert row.activity_basis is not None
        assert row.activity_basis.endswith("Зона «Въезд»: вне зоны")

    @pytest.mark.asyncio
    async def test_recompute_skips_night_frames(self, container) -> None:
        """Только светлое время суток (clean-mvp): ночной кадр в наблюдение не идёт."""
        from datetime import datetime

        await seed_user(container)
        site_id, owner_id, obs_date = uuid.uuid4(), uuid.uuid4(), date(2025, 1, 15)
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            session.add(User(id=owner_id, full_name="Owner"))
            session.add(Site(id=site_id, name="Test Site", owner_id=owner_id))
            await seed_test_data(session, site_id, owner_id)
            for hour in (3, 10, 22):
                session.add(
                    Photo(
                        id=uuid.uuid4(),
                        site_id=site_id,
                        storage_key=f"{hour}.jpg",
                        original_name=f"{hour}.jpg",
                        width=100,
                        height=100,
                        captured_on=obs_date,
                        captured_at=datetime(2025, 1, 15, hour, 0),
                        date_source=DateSource.STAMP.value,
                        processing_status=ProcessingStatus.DONE.value,
                    )
                )
            await session.commit()

        async with container() as request_container:
            service = await self._create_service(request_container)
            result = await service.recompute(site_id, obs_date)

        assert result is not None
        assert result.photo_count == 1  # только 10:00

    @pytest.mark.asyncio
    async def test_recompute_is_idempotent_same_id(self, container) -> None:
        """Calling recompute twice → same Observation.id, no duplicate rows."""
        await seed_user(container)

        site_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        obs_date = date(2025, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=owner_id, full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner_id)
            session.add(site)

            equipment_ids = await seed_test_data(session, site_id, owner_id)

            # Создаём фото
            photo = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="test.jpg",
                original_name="test.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo)
            await session.flush()

            # Создаём детекции
            det1 = Detection(
                id=uuid.uuid4(),
                photo_id=photo.id,
                equipment_type_id=equipment_ids["crane"],
                bbox=[0.1, 0.1, 0.5, 0.5],
                score=0.9,
                model_version="v1",
            )
            session.add(det1)
            await session.commit()

        # Первый вызов recompute
        async with container() as request_container:
            service = await self._create_service(request_container)
            result1 = await service.recompute(site_id, obs_date)

        first_id = result1.id

        # Второй вызов recompute с теми же данными
        async with container() as request_container:
            service = await self._create_service(request_container)
            result2 = await service.recompute(site_id, obs_date)

        assert result2.id == first_id
        assert result2.photo_count == 1

        # Проверяем, что в БД только одна строка
        async with container() as request_container:
            repo = ObservationRepository(await request_container.get(AsyncSession))
            all_obs = await repo.list_by_site(site_id)
            assert len(all_obs) == 1
            assert all_obs[0].id == first_id

    @pytest.mark.asyncio
    async def test_recompute_idempotent_with_added_photo(self, container) -> None:
        """Call recompute, add photo, recompute again → same id, updated photo_count."""
        await seed_user(container)

        site_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        obs_date = date(2025, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=owner_id, full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner_id)
            session.add(site)

            equipment_ids = await seed_test_data(session, site_id, owner_id)

            # Создаём первое фото
            photo1 = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="test1.jpg",
                original_name="test1.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo1)
            await session.flush()

            det1 = Detection(
                id=uuid.uuid4(),
                photo_id=photo1.id,
                equipment_type_id=equipment_ids["crane"],
                bbox=[0.1, 0.1, 0.5, 0.5],
                score=0.9,
                model_version="v1",
            )
            session.add(det1)
            await session.commit()

        # Первый recompute
        async with container() as request_container:
            service = await self._create_service(request_container)
            result1 = await service.recompute(site_id, obs_date)

        first_id = result1.id
        assert result1.photo_count == 1

        # Добавляем второе фото
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            photo2 = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="test2.jpg",
                original_name="test2.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo2)
            await session.flush()

            det2 = Detection(
                id=uuid.uuid4(),
                photo_id=photo2.id,
                equipment_type_id=equipment_ids["excavator"],
                bbox=[0.2, 0.2, 0.6, 0.6],
                score=0.85,
                model_version="v1",
            )
            session.add(det2)
            await session.commit()

        # Второй recompute
        async with container() as request_container:
            service = await self._create_service(request_container)
            result2 = await service.recompute(site_id, obs_date)

        assert result2.id == first_id
        assert result2.photo_count == 2

    @pytest.mark.asyncio
    async def test_recompute_with_zero_photos_deletes_existing(self, container) -> None:
        """Create observation, then remove photos or redate them, recompute → row deleted."""
        await seed_user(container)

        site_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        obs_date = date(2025, 1, 15)
        other_date = date(2025, 1, 16)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=owner_id, full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner_id)
            session.add(site)

            equipment_ids = await seed_test_data(session, site_id, owner_id)

            # Создаём фото на нужную дату
            photo = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="test.jpg",
                original_name="test.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo)
            await session.flush()

            det = Detection(
                id=uuid.uuid4(),
                photo_id=photo.id,
                equipment_type_id=equipment_ids["crane"],
                bbox=[0.1, 0.1, 0.5, 0.5],
                score=0.9,
                model_version="v1",
            )
            session.add(det)
            await session.commit()

        # Первый recompute - создаёт наблюдение
        async with container() as request_container:
            service = await self._create_service(request_container)
            result = await service.recompute(site_id, obs_date)

        assert result is not None
        obs_id = result.id

        # Меняем дату фото на другую
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            photo = await session.get(
                Photo, (await self._get_photo_id_for_site(request_container, site_id))
            )
            if photo:
                photo.captured_on = other_date
                await session.commit()

        # Второй recompute - должен удалить наблюдение
        async with container() as request_container:
            service = await self._create_service(request_container)
            result = await service.recompute(site_id, obs_date)

        assert result is None

        # Проверяем, что наблюдение действительно удалено
        async with container() as request_container:
            repo = ObservationRepository(await request_container.get(AsyncSession))
            obs = await repo.get(obs_id)
            assert obs is None

    @pytest.mark.asyncio
    async def test_recompute_counts_pending_photo_but_no_detections_from_it(
        self, container
    ) -> None:
        """Pending photo counts toward photo_count but contributes no detections."""
        await seed_user(container)

        site_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        obs_date = date(2025, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=owner_id, full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner_id)
            session.add(site)

            equipment_ids = await seed_test_data(session, site_id, owner_id)

            # Создаём done фото
            photo_done = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="done.jpg",
                original_name="done.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo_done)
            await session.flush()

            # Детекция в done фото
            det_done = Detection(
                id=uuid.uuid4(),
                photo_id=photo_done.id,
                equipment_type_id=equipment_ids["crane"],
                bbox=[0.1, 0.1, 0.5, 0.5],
                score=0.9,
                model_version="v1",
            )
            session.add(det_done)

            # Создаём pending фото
            photo_pending = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="pending.jpg",
                original_name="pending.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.PENDING.value,
            )
            session.add(photo_pending)
            await session.commit()

        # Запускаем recompute
        async with container() as request_container:
            service = await self._create_service(request_container)
            result = await service.recompute(site_id, obs_date)

        assert result is not None
        assert result.photo_count == 2  # Оба фото учтены

        # Проверяем, что есть техника только от done фото
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            equipment_rows = await session.get(ObservedEquipment, result.id)
            # Note: get_by_id не поддерживается, используем query
            from sqlalchemy import select

            stmt = select(ObservedEquipment).where(ObservedEquipment.observation_id == result.id)
            query_result = await session.execute(stmt)
            equipment_rows = query_result.scalars().all()

        assert len(equipment_rows) == 1
        assert equipment_rows[0].equipment_type_id == equipment_ids["crane"]

    @pytest.mark.asyncio
    async def test_recompute_low_observability(self, container) -> None:
        """Few photos (below min_photos_medium) → observability=low with notes."""
        await seed_user(container)

        site_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        obs_date = date(2025, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=owner_id, full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner_id)
            session.add(site)

            equipment_ids = await seed_test_data(session, site_id, owner_id)

            # Создаём 1 done фото
            photo = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="test.jpg",
                original_name="test.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo)
            await session.flush()

            det = Detection(
                id=uuid.uuid4(),
                photo_id=photo.id,
                equipment_type_id=equipment_ids["crane"],
                bbox=[0.1, 0.1, 0.5, 0.5],
                score=0.9,
                model_version="v1",
            )
            session.add(det)
            await session.commit()

            # Store equipment_ids for later use
            equipment_ids_stored = equipment_ids

        # First: recompute with default policy (min_photos_medium=2) -> LOW
        async with container() as request_container:
            service = await self._create_service(request_container)
            result = await service.recompute(site_id, obs_date)

        assert result is not None
        assert result.photo_count == 1
        assert result.observability == "low"
        assert result.observability_notes is not None

        # Second: add another done photo and recompute with default policy -> MEDIUM
        # This exercises the transition from LOW to MEDIUM with min_photos_medium=2
        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            # Create another done photo for the same date
            photo2 = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="test2.jpg",
                original_name="test2.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo2)
            await session.flush()

            # Add a detection to the second photo using the stored equipment_ids
            det2 = Detection(
                id=uuid.uuid4(),
                photo_id=photo2.id,
                equipment_type_id=equipment_ids_stored["excavator"],
                bbox=[0.2, 0.2, 0.6, 0.6],
                score=0.85,
                model_version="v1",
            )
            session.add(det2)
            await session.commit()

            # Recompute with default policy: 2 photos >= 2 threshold -> MEDIUM
            service = await self._create_service(request_container)
            result = await service.recompute(site_id, obs_date)

        assert result is not None
        assert result.photo_count == 2
        assert result.observability == "medium"
        assert result.observability_notes is not None

    @pytest.mark.asyncio
    async def test_recompute_frames_accumulation(self, container) -> None:
        """Verify frames are accumulated correctly (not summed, but maxed)."""
        await seed_user(container)

        site_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        obs_date = date(2025, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=owner_id, full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner_id)
            session.add(site)

            equipment_ids = await seed_test_data(session, site_id, owner_id)

            # Фото 1: 2 крана
            photo1 = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="photo1.jpg",
                original_name="photo1.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo1)
            await session.flush()

            det1a = Detection(
                id=uuid.uuid4(),
                photo_id=photo1.id,
                equipment_type_id=equipment_ids["crane"],
                bbox=[0.1, 0.1, 0.3, 0.3],
                score=0.9,
                model_version="v1",
            )
            det1b = Detection(
                id=uuid.uuid4(),
                photo_id=photo1.id,
                equipment_type_id=equipment_ids["crane"],
                bbox=[0.5, 0.5, 0.7, 0.7],
                score=0.85,
                model_version="v1",
            )
            session.add(det1a)
            session.add(det1b)

            # Фото 2: 1 кран
            photo2 = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="photo2.jpg",
                original_name="photo2.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo2)
            await session.flush()

            det2 = Detection(
                id=uuid.uuid4(),
                photo_id=photo2.id,
                equipment_type_id=equipment_ids["crane"],
                bbox=[0.2, 0.2, 0.4, 0.4],
                score=0.8,
                model_version="v1",
            )
            session.add(det2)
            await session.commit()

        # Запускаем recompute
        async with container() as request_container:
            service = await self._create_service(request_container)
            result = await service.recompute(site_id, obs_date)

        assert result is not None
        # count_min должен быть max(2, 1) = 2, а не 3
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            from sqlalchemy import select

            stmt = select(ObservedEquipment).where(ObservedEquipment.observation_id == result.id)
            query_result = await session.execute(stmt)
            equipment_rows = query_result.scalars().all()

        assert len(equipment_rows) == 1
        assert equipment_rows[0].count_min == 2  # max, not sum

    async def _create_service(self, request_container) -> ObservationService:
        """Helper to create ObservationService with all dependencies."""
        session = await request_container.get(AsyncSession)
        photo_repo = PhotoRepository(session)
        detection_repo = DetectionRepository(session)
        obs_repo = ObservationRepository(session)
        eq_repo = ObservedEquipmentRepository(session)
        guard = await request_container.get(SiteAccessGuard)
        catalog = await request_container.get(EquipmentCatalog)
        settings = await request_container.get(Settings)

        # Using default settings from task brief
        agg_policy = AggregationPolicy(
            min_score_high=settings.observation.min_score_high,
            min_score_medium=settings.observation.min_score_medium,
        )
        obs_policy = ObservabilityPolicy(
            min_photos_medium=settings.observation.min_photos_medium,
            min_photos_high=settings.observation.min_photos_high,
        )
        act_policy = ActivityPolicy(ActivityParams())

        return ObservationService(
            repository=obs_repo,
            equipment_repo=eq_repo,
            photos=photo_repo,
            detections=detection_repo,
            session=session,
            guard=guard,
            catalog=catalog,
            aggregation=agg_policy,
            observability=obs_policy,
            activity=act_policy,
            recalculator=NoopStatusRecalculator(),
        )

    async def _get_photo_id_for_site(self, request_container, site_id: uuid.UUID) -> uuid.UUID:
        """Get first photo ID for a site."""
        session = await request_container.get(AsyncSession)
        repo = PhotoRepository(session)
        photos = await repo.list_by_site(site_id)
        if photos:
            return photos[0].id
        raise ValueError("No photos found")


class TestObservationServiceGetObservation:
    """Тесты метода get_observation."""

    @pytest.mark.asyncio
    async def test_get_observation_not_found_404(self, container) -> None:
        """get_observation for nonexistent date → AppError(404)."""
        await seed_user(container)

        site_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        obs_date = date(2025, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=owner_id, full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner_id)
            session.add(site)
            await session.commit()

        async with container() as request_container:
            service = await self._create_service(request_container)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            with pytest.raises(AppError) as exc_info:
                await service.get_observation(site_id, obs_date)

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_get_observation_enriches_equipment(self, container) -> None:
        """get_observation returns equipment with code and title from catalog."""
        await seed_user(container)

        site_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        obs_date = date(2025, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=owner_id, full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner_id)
            session.add(site)

            eq_crane = EquipmentType(id=uuid.uuid4(), code="crane", title="Кран", synonyms=[])
            session.add(eq_crane)
            await session.flush()

            photo = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="test.jpg",
                original_name="test.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo)
            await session.flush()

            det = Detection(
                id=uuid.uuid4(),
                photo_id=photo.id,
                equipment_type_id=eq_crane.id,
                bbox=[0.1, 0.1, 0.5, 0.5],
                score=0.9,
                model_version="v1",
            )
            session.add(det)
            await session.commit()

        # Создаём наблюдение
        async with container() as request_container:
            service = await self._create_service(request_container)
            await service.recompute(site_id, obs_date)

        # Получаем наблюдение
        async with container() as request_container:
            service = await self._create_service(request_container)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            obs_read = await service.get_observation(site_id, obs_date)

        assert len(obs_read.equipment) == 1
        assert obs_read.equipment[0].equipment_code == "crane"
        assert obs_read.equipment[0].equipment_title == "Кран"

    async def _create_service(self, request_container) -> ObservationService:
        """Helper to create ObservationService."""
        session = await request_container.get(AsyncSession)
        photo_repo = PhotoRepository(session)
        detection_repo = DetectionRepository(session)
        obs_repo = ObservationRepository(session)
        eq_repo = ObservedEquipmentRepository(session)
        guard = await request_container.get(SiteAccessGuard)
        catalog = await request_container.get(EquipmentCatalog)
        settings = await request_container.get(Settings)

        agg_policy = AggregationPolicy(
            min_score_high=settings.observation.min_score_high,
            min_score_medium=settings.observation.min_score_medium,
        )
        obs_policy = ObservabilityPolicy(
            min_photos_medium=settings.observation.min_photos_medium,
            min_photos_high=settings.observation.min_photos_high,
        )
        act_policy = ActivityPolicy(ActivityParams())

        return ObservationService(
            repository=obs_repo,
            equipment_repo=eq_repo,
            photos=photo_repo,
            detections=detection_repo,
            session=session,
            guard=guard,
            catalog=catalog,
            aggregation=agg_policy,
            observability=obs_policy,
            activity=act_policy,
            recalculator=NoopStatusRecalculator(),
        )


class TestObservationServiceListObservations:
    """Тесты метода list_observations."""

    @pytest.mark.asyncio
    async def test_list_observations_enriches_equipment(self, container) -> None:
        """list_observations returns observations with enriched equipment."""
        await seed_user(container)

        site_id = uuid.uuid4()
        owner_id = uuid.uuid4()
        obs_date = date(2025, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=owner_id, full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner_id)
            session.add(site)

            eq_excavator = EquipmentType(
                id=uuid.uuid4(), code="excavator", title="Экскаватор", synonyms=[]
            )
            session.add(eq_excavator)
            await session.flush()

            photo = Photo(
                id=uuid.uuid4(),
                site_id=site_id,
                storage_key="test.jpg",
                original_name="test.jpg",
                width=100,
                height=100,
                captured_on=obs_date,
                date_source=DateSource.MANUAL.value,
                processing_status=ProcessingStatus.DONE.value,
            )
            session.add(photo)
            await session.flush()

            det = Detection(
                id=uuid.uuid4(),
                photo_id=photo.id,
                equipment_type_id=eq_excavator.id,
                bbox=[0.1, 0.1, 0.5, 0.5],
                score=0.9,
                model_version="v1",
            )
            session.add(det)
            await session.commit()

        # Создаём наблюдение
        async with container() as request_container:
            service = await self._create_service(request_container)
            await service.recompute(site_id, obs_date)

        # Получаем список
        async with container() as request_container:
            service = await self._create_service(request_container)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            obs_list = await service.list_observations(site_id)

        assert len(obs_list) == 1
        assert len(obs_list[0].equipment) == 1
        assert obs_list[0].equipment[0].equipment_code == "excavator"
        assert obs_list[0].equipment[0].equipment_title == "Экскаватор"

    async def _create_service(self, request_container) -> ObservationService:
        """Helper to create ObservationService."""
        session = await request_container.get(AsyncSession)
        photo_repo = PhotoRepository(session)
        detection_repo = DetectionRepository(session)
        obs_repo = ObservationRepository(session)
        eq_repo = ObservedEquipmentRepository(session)
        guard = await request_container.get(SiteAccessGuard)
        catalog = await request_container.get(EquipmentCatalog)
        settings = await request_container.get(Settings)

        agg_policy = AggregationPolicy(
            min_score_high=settings.observation.min_score_high,
            min_score_medium=settings.observation.min_score_medium,
        )
        obs_policy = ObservabilityPolicy(
            min_photos_medium=settings.observation.min_photos_medium,
            min_photos_high=settings.observation.min_photos_high,
        )
        act_policy = ActivityPolicy(ActivityParams())

        return ObservationService(
            repository=obs_repo,
            equipment_repo=eq_repo,
            photos=photo_repo,
            detections=detection_repo,
            session=session,
            guard=guard,
            catalog=catalog,
            aggregation=agg_policy,
            observability=obs_policy,
            activity=act_policy,
            recalculator=NoopStatusRecalculator(),
        )
