"""Модели фотографий: таблицы photos, detections."""

import uuid
from datetime import date

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.domains.methodology.models import EquipmentType
from app.domains.photo.models import DateSource, Detection, Photo, ProcessingStatus
from app.domains.site.models import Site
from app.domains.user.models import User


@pytest.mark.asyncio
async def test_photo_table_exists(engine: AsyncEngine) -> None:
    """Таблица photos создана в схеме."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='photos'")
        )
        assert result.scalar() == "photos"


@pytest.mark.asyncio
async def test_detection_table_exists(engine: AsyncEngine) -> None:
    """Таблица detections создана в схеме."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='detections'")
        )
        assert result.scalar() == "detections"


@pytest.mark.asyncio
async def test_photo_columns(engine: AsyncEngine) -> None:
    """Колонки таблицы photos соответствуют модели."""
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA table_info(photos)"))
        columns = {row[1] for row in result.all()}
        assert columns == {
            "id",
            "site_id",
            "storage_key",
            "original_name",
            "width",
            "height",
            "captured_on",
            "date_source",
            "processing_status",
            "camera_id",
            "uploaded_at",
            "captured_at",
            "date_hint",
            "uncertain_at",
            "time_check",
        }


@pytest.mark.asyncio
async def test_detection_columns(engine: AsyncEngine) -> None:
    """Колонки таблицы detections соответствуют модели."""
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA table_info(detections)"))
        columns = {row[1] for row in result.all()}
        assert columns == {
            "id",
            "photo_id",
            "equipment_type_id",
            "bbox",
            "score",
            "model_version",
            "created_at",
        }


@pytest.mark.asyncio
async def test_photo_nullable_columns(engine: AsyncEngine) -> None:
    """Проверка nullable для колонок photos (captured_on и date_source nullable)."""
    async with engine.connect() as conn:
        result = await conn.execute(text("PRAGMA table_info(photos)"))
        columns = {row[1]: row[3] for row in result.all()}  # name: notnull
        # notnull=1 означает NOT NULL, notnull=0 означает nullable
        assert columns["captured_on"] == 0, "captured_on должен быть nullable"
        assert columns["date_source"] == 0, "date_source должен быть nullable"
        assert columns["site_id"] == 1, "site_id должен быть NOT NULL"
        assert columns["storage_key"] == 1, "storage_key должен быть NOT NULL"
        assert columns["original_name"] == 1, "original_name должен быть NOT NULL"
        assert columns["width"] == 1, "width должен быть NOT NULL"
        assert columns["height"] == 1, "height должен быть NOT NULL"
        assert columns["processing_status"] == 1, "processing_status должен быть NOT NULL"
        assert columns["uploaded_at"] == 1, "uploaded_at должен быть NOT NULL"


@pytest.mark.asyncio
async def test_photo_persists_with_site(engine: AsyncEngine, container) -> None:
    """Photo сохраняется с site_id и читается обратно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Создаём пользователя и сайт
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Construction Site", owner_id=owner_id)
        session.add(site)

        # Создаём фото
        photo = Photo(
            id=uuid.uuid4(),
            site_id=site_id,
            storage_key="s3://bucket/photos/photo1.jpg",
            original_name="photo1.jpg",
            width=1920,
            height=1080,
            captured_on=date(2026, 9, 24),
            date_source=DateSource.METADATA.value,
            processing_status=ProcessingStatus.PENDING.value,
        )
        session.add(photo)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(Photo, photo.id)
        assert fetched is not None
        assert fetched.id == photo.id
        assert fetched.site_id == site_id
        assert fetched.storage_key == "s3://bucket/photos/photo1.jpg"
        assert fetched.original_name == "photo1.jpg"
        assert fetched.width == 1920
        assert fetched.height == 1080
        assert fetched.captured_on == date(2026, 9, 24)
        assert fetched.date_source == DateSource.METADATA.value
        assert fetched.processing_status == ProcessingStatus.PENDING.value
        assert fetched.uploaded_at is not None


@pytest.mark.asyncio
async def test_photo_with_null_capture_date_and_source(engine: AsyncEngine, container) -> None:
    """Photo может быть создана с null captured_on и date_source."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        photo = Photo(
            id=uuid.uuid4(),
            site_id=site_id,
            storage_key="s3://bucket/photo2.jpg",
            original_name="photo2.jpg",
            width=1024,
            height=768,
            captured_on=None,
            date_source=None,
            processing_status=ProcessingStatus.DONE.value,
        )
        session.add(photo)
        await session.commit()

        fetched = await session.get(Photo, photo.id)
        assert fetched is not None
        assert fetched.captured_on is None
        assert fetched.date_source is None


@pytest.mark.asyncio
async def test_detection_persists(engine: AsyncEngine, container) -> None:
    """Detection сохраняется и читается обратно."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        photo_id = uuid.uuid4()
        photo = Photo(
            id=photo_id,
            site_id=site_id,
            storage_key="s3://bucket/photo.jpg",
            original_name="photo.jpg",
            width=1920,
            height=1080,
        )
        session.add(photo)

        # Тип оборудования
        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(
            id=eq_type_id, code="excavator_crawler", title="Гусеничный экскаватор"
        )
        session.add(eq_type)

        # Детекция
        detection = Detection(
            id=uuid.uuid4(),
            photo_id=photo_id,
            equipment_type_id=eq_type_id,
            bbox=[0.1, 0.2, 0.8, 0.9],
            score=0.95,
            model_version="v1.0",
        )
        session.add(detection)
        await session.commit()

        # Читаем обратно
        fetched = await session.get(Detection, detection.id)
        assert fetched is not None
        assert fetched.id == detection.id
        assert fetched.photo_id == photo_id
        assert fetched.equipment_type_id == eq_type_id
        assert fetched.bbox == [0.1, 0.2, 0.8, 0.9]
        assert fetched.score == 0.95
        assert fetched.model_version == "v1.0"
        assert fetched.created_at is not None


@pytest.mark.asyncio
async def test_date_source_enum_values() -> None:
    """Enum DateSource содержит все требуемые значения."""
    assert DateSource.CHANNEL == "channel"
    assert DateSource.METADATA == "metadata"
    assert DateSource.STAMP == "stamp"
    assert DateSource.NEIGHBOURS == "neighbours"
    assert DateSource.MANUAL == "manual"


@pytest.mark.asyncio
async def test_processing_status_enum_values() -> None:
    """Enum ProcessingStatus содержит все требуемые значения."""
    assert ProcessingStatus.PENDING == "pending"
    assert ProcessingStatus.DONE == "done"
    assert ProcessingStatus.FAILED == "failed"


@pytest.mark.asyncio
async def test_bbox_json_roundtrip(engine: AsyncEngine, container) -> None:
    """bbox сохраняется как JSON и читается обратно как список float."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="John Doe")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        photo_id = uuid.uuid4()
        photo = Photo(
            id=photo_id,
            site_id=site_id,
            storage_key="s3://test.jpg",
            original_name="test.jpg",
            width=640,
            height=480,
        )
        session.add(photo)

        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(id=eq_type_id, code="test_eq", title="Test Equipment")
        session.add(eq_type)

        # Создаём детекцию с точными координатами
        bbox_data = [0.15, 0.25, 0.85, 0.95]
        detection = Detection(
            id=uuid.uuid4(),
            photo_id=photo_id,
            equipment_type_id=eq_type_id,
            bbox=bbox_data,
            score=0.87,
            model_version="v2.1",
        )
        session.add(detection)
        await session.commit()

        # Очищаем сессию и читаем заново
        fetched = await session.get(Detection, detection.id)
        assert fetched is not None
        assert fetched.bbox == bbox_data
        assert isinstance(fetched.bbox, list)
        assert all(isinstance(x, (int, float)) for x in fetched.bbox)


@pytest.mark.asyncio
async def test_photo_fk_site_cascade_delete() -> None:
    """FK photos.site_id -> sites.id имеет ondelete=CASCADE."""
    table = Photo.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "site_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"


@pytest.mark.asyncio
async def test_detection_fk_photo_cascade_delete() -> None:
    """FK detections.photo_id -> photos.id имеет ondelete=CASCADE."""
    table = Detection.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "photo_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    assert fk_constraints[0].ondelete == "CASCADE"


@pytest.mark.asyncio
async def test_detection_fk_equipment_type_no_cascade() -> None:
    """FK detections.equipment_type_id -> equipment_types.id НЕ имеет CASCADE."""
    table = Detection.__table__
    fk_constraints = [fk for fk in table.foreign_keys if "equipment_type_id" in fk.parent.name]
    assert len(fk_constraints) == 1
    # Проверяем, что нет CASCADE (должна быть RESTRICT или NOACTION по умолчанию)
    assert fk_constraints[0].ondelete is None or fk_constraints[0].ondelete == "RESTRICT"


@pytest.mark.asyncio
async def test_cascade_delete_site_removes_photos_and_detections(
    container, engine: AsyncEngine
) -> None:
    """REAL CASCADE DELETE (a): удаление Site каскадно удаляет photos и их detections.

    Использует PRAGMA foreign_keys=ON на общем engine (StaticPool).
    """
    # Включаем FK pragma для SQLite на общем соединении
    async with engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        # Проверяем, что FK включены
        result = await conn.exec_driver_sql("PRAGMA foreign_keys")
        row = result.fetchone()
        assert row[0] == 1, "FK pragma не включена"

    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Создаём инфраструктуру
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="Test User")
        session.add(owner)
        await session.commit()

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Test Site", owner_id=owner_id)
        session.add(site)
        await session.commit()

        # Создаём фото
        photo_id = uuid.uuid4()
        photo = Photo(
            id=photo_id,
            site_id=site_id,
            storage_key="s3://photo.jpg",
            original_name="photo.jpg",
            width=640,
            height=480,
        )
        session.add(photo)
        await session.commit()

        # Создаём тип оборудования
        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(id=eq_type_id, code="crane", title="Кран")
        session.add(eq_type)
        await session.commit()

        # Создаём две детекции
        detection1_id = uuid.uuid4()
        detection1 = Detection(
            id=detection1_id,
            photo_id=photo_id,
            equipment_type_id=eq_type_id,
            bbox=[0.1, 0.1, 0.5, 0.5],
            score=0.9,
            model_version="v1.0",
        )
        session.add(detection1)

        detection2_id = uuid.uuid4()
        detection2 = Detection(
            id=detection2_id,
            photo_id=photo_id,
            equipment_type_id=eq_type_id,
            bbox=[0.5, 0.5, 0.9, 0.9],
            score=0.85,
            model_version="v1.0",
        )
        session.add(detection2)
        await session.commit()

        # Удаляем сайт
        await session.delete(site)
        await session.commit()

    # Проверяем каскадное удаление в НОВОЙ сессии
    async with maker() as session:
        photo_count = await session.execute(select(Photo))
        assert len(photo_count.scalars().all()) == 0, "photos должна быть пуста"

        detection_count = await session.execute(select(Detection))
        assert len(detection_count.scalars().all()) == 0, "detections должна быть пуста"


@pytest.mark.asyncio
async def test_cascade_delete_photo_removes_detections(container, engine: AsyncEngine) -> None:
    """REAL CASCADE DELETE (b): удаление Photo каскадно удаляет его detections.

    Site и EquipmentType остаются нетронутыми.
    """
    # Включаем FK pragma для SQLite на общем соединении
    async with engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        result = await conn.exec_driver_sql("PRAGMA foreign_keys")
        row = result.fetchone()
        assert row[0] == 1, "FK pragma не включена"

    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="Test User")
        session.add(owner)
        await session.commit()

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Test Site", owner_id=owner_id)
        session.add(site)
        await session.commit()

        # Создаём две фотографии
        photo1_id = uuid.uuid4()
        photo1 = Photo(
            id=photo1_id,
            site_id=site_id,
            storage_key="s3://photo1.jpg",
            original_name="photo1.jpg",
            width=640,
            height=480,
        )
        session.add(photo1)

        photo2_id = uuid.uuid4()
        photo2 = Photo(
            id=photo2_id,
            site_id=site_id,
            storage_key="s3://photo2.jpg",
            original_name="photo2.jpg",
            width=640,
            height=480,
        )
        session.add(photo2)
        await session.commit()

        # Создаём тип оборудования
        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(id=eq_type_id, code="crane", title="Кран")
        session.add(eq_type)
        await session.commit()

        # Создаём две детекции для фото1 и одну для фото2
        detection1_id = uuid.uuid4()
        detection1 = Detection(
            id=detection1_id,
            photo_id=photo1_id,
            equipment_type_id=eq_type_id,
            bbox=[0.1, 0.1, 0.9, 0.9],
            score=0.9,
            model_version="v1.0",
        )
        session.add(detection1)

        detection2_id = uuid.uuid4()
        detection2 = Detection(
            id=detection2_id,
            photo_id=photo1_id,
            equipment_type_id=eq_type_id,
            bbox=[0.2, 0.2, 0.8, 0.8],
            score=0.85,
            model_version="v1.0",
        )
        session.add(detection2)

        detection3_id = uuid.uuid4()
        detection3 = Detection(
            id=detection3_id,
            photo_id=photo2_id,
            equipment_type_id=eq_type_id,
            bbox=[0.3, 0.3, 0.7, 0.7],
            score=0.8,
            model_version="v1.0",
        )
        session.add(detection3)
        await session.commit()

        # Удаляем только photo1
        await session.delete(photo1)
        await session.commit()

    # Проверяем в новой сессии
    async with maker() as session:
        # photo2 должна остаться
        photo2_check = await session.execute(select(Photo).where(Photo.id == photo2_id))
        assert photo2_check.scalar() is not None, "photo2 должна остаться"

        # detection3 (для photo2) должна остаться
        det3_check = await session.execute(select(Detection).where(Detection.id == detection3_id))
        assert det3_check.scalar() is not None, "detection3 должна остаться"

        # detection1 и detection2 (для photo1) должны быть удалены
        det1_check = await session.execute(select(Detection).where(Detection.id == detection1_id))
        assert det1_check.scalar() is None, "detection1 должна быть удалена"

        det2_check = await session.execute(select(Detection).where(Detection.id == detection2_id))
        assert det2_check.scalar() is None, "detection2 должна быть удалена"

        # Site и EquipmentType должны остаться
        site_check = await session.execute(select(Site).where(Site.id == site_id))
        assert site_check.scalar() is not None, "Site должен остаться"

        eq_check = await session.execute(
            select(EquipmentType).where(EquipmentType.id == eq_type_id)
        )
        assert eq_check.scalar() is not None, "EquipmentType должен остаться"


@pytest.mark.asyncio
async def test_cascade_delete_site_without_fk_enforcement_fails(
    container, engine: AsyncEngine
) -> None:
    """Мутация (a): БЕЗ PRAGMA foreign_keys=ON cascade не работает.

    Это доказывает, что тест (a) проверяет реальное поведение БД, а не просто ORM.
    """
    # Отключаем FK pragma для SQLite на общем соединении
    async with engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        result = await conn.exec_driver_sql("PRAGMA foreign_keys")
        row = result.fetchone()
        assert row[0] == 0, "FK pragma должна быть отключена для мутации"

    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Создаём инфраструктуру
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="Test User")
        session.add(owner)
        await session.commit()

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Test Site", owner_id=owner_id)
        session.add(site)
        await session.commit()

        # Создаём фото
        photo_id = uuid.uuid4()
        photo = Photo(
            id=photo_id,
            site_id=site_id,
            storage_key="s3://photo.jpg",
            original_name="photo.jpg",
            width=640,
            height=480,
        )
        session.add(photo)
        await session.commit()

        # Создаём тип оборудования
        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(id=eq_type_id, code="crane", title="Кран")
        session.add(eq_type)
        await session.commit()

        # Создаём две детекции
        detection1_id = uuid.uuid4()
        detection1 = Detection(
            id=detection1_id,
            photo_id=photo_id,
            equipment_type_id=eq_type_id,
            bbox=[0.1, 0.1, 0.5, 0.5],
            score=0.9,
            model_version="v1.0",
        )
        session.add(detection1)

        detection2_id = uuid.uuid4()
        detection2 = Detection(
            id=detection2_id,
            photo_id=photo_id,
            equipment_type_id=eq_type_id,
            bbox=[0.5, 0.5, 0.9, 0.9],
            score=0.85,
            model_version="v1.0",
        )
        session.add(detection2)
        await session.commit()

        # Удаляем сайт
        await session.delete(site)
        await session.commit()

    # БЕЗ PRAGMA foreign_keys=ON cascade НЕ работает, поэтому фото/детекции остаются
    async with maker() as session:
        photo_count = await session.execute(select(Photo))
        photos = photo_count.scalars().all()
        # ЭТО должно ПРОВАЛИТЬСЯ: фото ВСЕ ЕЩЕ ЕСТЬ без CASCADE
        assert len(photos) != 0, "Мутация работает: без FK enforcement cascade не работает"

    # Восстанавливаем PRAGMA для других тестов
    async with engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=OFF")


@pytest.mark.asyncio
async def test_no_cascade_delete_equipment_type(container, engine: AsyncEngine) -> None:
    """REAL FK ENFORCEMENT (c): equipment_type НЕ может быть удален если на него ссылается.

    С PRAGMA foreign_keys=ON должен быть IntegrityError.
    """
    # Включаем FK pragma для SQLite на общем соединении
    async with engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        result = await conn.exec_driver_sql("PRAGMA foreign_keys")
        row = result.fetchone()
        assert row[0] == 1, "FK pragma не включена"

    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        # Инфраструктура
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="Test User")
        session.add(owner)
        await session.commit()

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Test Site", owner_id=owner_id)
        session.add(site)
        await session.commit()

        # Создаём фото
        photo_id = uuid.uuid4()
        photo = Photo(
            id=photo_id,
            site_id=site_id,
            storage_key="s3://photo.jpg",
            original_name="photo.jpg",
            width=640,
            height=480,
        )
        session.add(photo)
        await session.commit()

        # Создаём тип оборудования
        eq_type_id = uuid.uuid4()
        eq_type = EquipmentType(id=eq_type_id, code="crane", title="Кран")
        session.add(eq_type)
        await session.commit()

        # Создаём детекцию, ссылающуюся на equipment_type
        detection = Detection(
            id=uuid.uuid4(),
            photo_id=photo_id,
            equipment_type_id=eq_type_id,
            bbox=[0.1, 0.1, 0.9, 0.9],
            score=0.9,
            model_version="v1.0",
        )
        session.add(detection)
        await session.commit()

        # Пытаемся удалить equipment_type, на который ещё ссылается detection
        # С PRAGMA foreign_keys=ON это должно вызвать IntegrityError
        await session.delete(eq_type)

        with pytest.raises(IntegrityError):
            await session.commit()

    # Восстанавливаем PRAGMA для других тестов
    async with engine.connect() as conn:
        await conn.exec_driver_sql("PRAGMA foreign_keys=OFF")


@pytest.mark.asyncio
async def test_processing_status_default_is_pending(engine: AsyncEngine, container) -> None:
    """processing_status по умолчанию = PENDING."""
    maker = await container.get(async_sessionmaker[AsyncSession])

    async with maker() as session:
        owner_id = uuid.uuid4()
        owner = User(id=owner_id, full_name="Test User")
        session.add(owner)

        site_id = uuid.uuid4()
        site = Site(id=site_id, name="Site", owner_id=owner_id)
        session.add(site)

        # Создаём фото без явного указания processing_status
        photo = Photo(
            id=uuid.uuid4(),
            site_id=site_id,
            storage_key="s3://photo.jpg",
            original_name="photo.jpg",
            width=640,
            height=480,
        )
        session.add(photo)
        await session.commit()

        fetched = await session.get(Photo, photo.id)
        assert fetched is not None
        assert fetched.processing_status == ProcessingStatus.PENDING.value
