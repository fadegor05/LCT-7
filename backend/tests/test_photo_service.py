"""PhotoService тесты: upload_batch, list_photos, get_photo, set_date, get_image, redetect."""

import io
import uuid
from datetime import UTC, date, timedelta
from typing import cast

import pytest
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.ml.base import DetectionResult, DetectorClient, DetectorError, RawDetection
from app.core.settings import Settings
from app.domains.methodology.models import EquipmentType
from app.domains.photo.models import DateSource, Photo, ProcessingStatus
from app.domains.photo.service import PhotoService, UploadInput
from app.domains.site.models import Site
from app.domains.user.models import User
from app.domains.user.service import UserService
from app.plugins.exceptions import AppError
from tests.fakes import FakeDetector


async def seed_user(container) -> None:
    """Создаёт стендового пользователя."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


def create_jpeg_image(width: int = 100, height: int = 100) -> bytes:
    """Создать JPEG изображение в памяти."""
    img = Image.new("RGB", (width, height), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


def create_png_image(width: int = 100, height: int = 100) -> bytes:
    """Создать PNG изображение в памяти."""
    img = Image.new("RGB", (width, height), color="blue")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def create_tiny_png() -> bytes:
    """Создать минималистичное PNG 1x1 (69 байт) для тестирования размера."""
    img = Image.new("RGB", (1, 1), color="red")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def create_webp_image(width: int = 100, height: int = 100) -> bytes:
    """Создать WEBP изображение в памяти."""
    img = Image.new("RGB", (width, height), color="green")
    buffer = io.BytesIO()
    img.save(buffer, format="WEBP")
    return buffer.getvalue()


def create_gif_image() -> bytes:
    """Создать GIF изображение в памяти (неподдерживаемый формат)."""
    img = Image.new("RGB", (100, 100), color="yellow")
    buffer = io.BytesIO()
    img.save(buffer, format="GIF")
    return buffer.getvalue()


def create_jpeg_with_exif_date(date_value: date) -> bytes:
    """Создать JPEG с EXIF DateTimeOriginal."""
    img = Image.new("RGB", (100, 100), color="red")
    exif = Image.Exif()
    # DateTimeOriginal IFD tag 0x9003
    datetime_str = date_value.strftime("%Y:%m:%d 12:00:00")
    exif_ifd = exif.get_ifd(0x8769)
    exif_ifd[0x9003] = datetime_str
    exif[0x8769] = exif_ifd

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", exif=exif)
    return buffer.getvalue()


class TestPhotoServiceUpload:
    """Тесты upload_batch."""

    @pytest.mark.asyncio
    async def test_upload_batch_happy_path_mixed_sources(self, container, detector) -> None:
        """Загрузить 3 файла: EXIF, none, none -> sources metadata/neighbours."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)

            # Создаём EquipmentType для детектора
            equipment = EquipmentType(id=uuid.uuid4(), code="crane", title="Кран")
            session.add(equipment)
            await session.commit()

            owner_id = owner.id

        # Подготавливаем файлы
        date_with_exif = date(2025, 1, 15)
        files = [
            UploadInput(
                filename="photo1.jpg",
                content=create_jpeg_with_exif_date(date_with_exif),
                content_type="image/jpeg",
            ),
            UploadInput(
                filename="photo2.jpg",
                content=create_jpeg_image(),
                content_type="image/jpeg",
            ),
            UploadInput(
                filename="photo3.jpg",
                content=create_jpeg_image(),
                content_type="image/jpeg",
            ),
        ]

        # Загружаем
        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.result = None  # Reset to default
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        # Проверяем результаты
        assert report.uploaded == 3
        assert report.failed == 0
        assert len(report.items) == 3

        # Проверяем источники дат
        assert report.items[0].photo.date_source == DateSource.METADATA.value
        assert report.items[0].photo.captured_on == date_with_exif
        assert report.items[1].photo.date_source == DateSource.NEIGHBOURS.value
        assert report.items[1].photo.captured_on == date_with_exif
        assert report.items[2].photo.date_source == DateSource.NEIGHBOURS.value
        assert report.items[2].photo.captured_on == date_with_exif

    @pytest.mark.asyncio
    async def test_upload_batch_no_dated_photos_stay_undated(self, container) -> None:
        """Загрузить батч без датированных фото -> остаются undated."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo1.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
            UploadInput(
                filename="photo2.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        assert report.uploaded == 2
        assert all(item.photo.captured_on is None for item in report.items)

        # Проверяем через list_photos(undated=True)
        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            undated_list = await service.list_photos(site_id, undated=True)
            assert len(undated_list) == 2

    @pytest.mark.asyncio
    async def test_upload_batch_per_file_errors_dont_abort(self, container) -> None:
        """Ошибки в файлах не прерывают батч: corrupt, unsupported, empty, oversized."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="good.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
            UploadInput(filename="corrupt.jpg", content=b"not an image", content_type="image/jpeg"),
            UploadInput(
                filename="unsupported.gif",
                content=create_gif_image(),
                content_type="image/gif",
            ),
            UploadInput(filename="empty.jpg", content=b"", content_type="image/jpeg"),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        assert report.uploaded == 1
        assert report.failed == 3
        assert report.items[0].photo is not None
        assert report.items[1].error is not None
        assert report.items[2].error is not None
        assert report.items[3].error is not None

    @pytest.mark.asyncio
    async def test_upload_batch_empty_list_422(self, container) -> None:
        """Пустой список -> 422."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            with pytest.raises(AppError) as exc_info:
                await service.upload_batch(site_id, [])

            assert exc_info.value.status_code == 422

    @pytest.mark.asyncio
    async def test_upload_batch_too_many_files_413(self, container) -> None:
        """Слишком много файлов -> 413."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        # Создаём 51 файл (лимит 50)
        files = [
            UploadInput(
                filename=f"photo{i}.jpg",
                content=create_jpeg_image(),
                content_type="image/jpeg",
            )
            for i in range(51)
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            with pytest.raises(AppError) as exc_info:
                await service.upload_batch(site_id, files)

            assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_upload_batch_foreign_site_404(self, container) -> None:
        """Чужой сайт -> 404."""
        await seed_user(container)

        site_id = uuid.uuid4()
        other_owner_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=other_owner_id, full_name="Other Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            # Устанавливаем другого пользователя
            service._guard._current_user = type("obj", (object,), {"id": uuid.uuid4()})()

            with pytest.raises(AppError) as exc_info:
                await service.upload_batch(site_id, files)

            assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_batch_storage_key_uses_detected_extension(self, container) -> None:
        """Storage key использует обнаруженное расширение, не от клиента."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        # PNG файл с расширением .exe в имени
        png_content = create_png_image()
        files = [
            UploadInput(filename="evil.exe", content=png_content, content_type="image/png"),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        assert report.uploaded == 1
        photo_id = report.items[0].photo.id

        # Проверяем storage key
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            from app.domains.photo.repository import PhotoRepository

            repo = PhotoRepository(session)
            photo = await repo.get(photo_id)

        assert photo is not None
        assert photo.storage_key.endswith(".png")


class TestPhotoServiceList:
    """Тесты list_photos."""

    @pytest.mark.asyncio
    async def test_list_photos_basic(self, container) -> None:
        """Список всех фото."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        # Загружаем фото
        files = [
            UploadInput(
                filename="photo1.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
            UploadInput(
                filename="photo2.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            await service.upload_batch(site_id, files)

        # Получаем список
        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photos = await service.list_photos(site_id)

        assert len(photos) == 2

    @pytest.mark.asyncio
    async def test_list_photos_undated_filter(self, container) -> None:
        """Фильтр undated=True возвращает только undated."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo1.jpg",
                content=create_jpeg_with_exif_date(date(2025, 1, 1)),
                content_type="image/jpeg",
            ),
            UploadInput(
                filename="photo2.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            await service.upload_batch(site_id, files)

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            undated = await service.list_photos(site_id, undated=True)

        assert len(undated) == 1
        assert undated[0].captured_on is None


class TestPhotoServiceGet:
    """Тесты get_photo."""

    @pytest.mark.asyncio
    async def test_get_photo_with_detections(self, container, detector) -> None:
        """Получить фото с детекциями и обогащением."""
        await seed_user(container)

        site_id = uuid.uuid4()
        equipment_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)

            # Создаём EquipmentType
            equipment = EquipmentType(id=equipment_id, code="crane", title="Кран")
            session.add(equipment)
            await session.commit()
            owner_id = owner.id

        # Загружаем фото с детектором
        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            # Настраиваем детектор перед загрузкой
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.result = DetectionResult(
                model_version="v1",
                detections=[
                    RawDetection(class_ours="crane", conf=0.95, bbox=(0.1, 0.2, 0.3, 0.4)),
                ],
            )
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        # Получаем фото
        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photo_detail = await service.get_photo(site_id, photo_id)

        assert photo_detail.id == photo_id
        assert len(photo_detail.detections) == 1
        assert photo_detail.detections[0].equipment_code == "crane"
        assert photo_detail.detections[0].equipment_title == "Кран"

    @pytest.mark.asyncio
    async def test_get_photo_other_site_404(self, container) -> None:
        """Фото из другого сайта -> 404."""
        await seed_user(container)

        site1_id = uuid.uuid4()
        site2_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site1 = Site(id=site1_id, name="Site 1", owner_id=owner.id)
            site2 = Site(id=site2_id, name="Site 2", owner_id=owner.id)
            session.add(site1)
            session.add(site2)
            await session.commit()
            owner_id = owner.id

        # Загружаем фото в site1
        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site1_id, files)

        photo_id = report.items[0].photo.id

        # Пытаемся получить из site2
        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            with pytest.raises(AppError) as exc_info:
                await service.get_photo(site2_id, photo_id)

            assert exc_info.value.status_code == 404


class TestPhotoServiceSetDate:
    """Тесты set_date."""

    @pytest.mark.asyncio
    async def test_set_date_manual(self, container) -> None:
        """Установить дату вручную."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        # Загружаем фото без даты
        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        # Устанавливаем дату
        new_date = date(2025, 1, 15)
        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photo_read = await service.set_date(site_id, photo_id, new_date)

        assert photo_read.captured_on == new_date
        assert photo_read.date_source == DateSource.MANUAL.value

    @pytest.mark.asyncio
    async def test_set_date_future_date_422(self, container) -> None:
        """Будущая дата -> 422."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        # Устанавливаем будущую дату
        future_date = date.today() + timedelta(days=1)
        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            with pytest.raises(AppError) as exc_info:
                await service.set_date(site_id, photo_id, future_date)

            assert exc_info.value.status_code == 422


class TestPhotoServiceGetImage:
    """Тесты get_image."""

    @pytest.mark.asyncio
    async def test_get_image_bytes_and_content_type(self, container) -> None:
        """Получить байты и MIME-тип изображения."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        # Загружаем JPEG
        jpeg_content = create_jpeg_image()
        files = [
            UploadInput(filename="photo.jpg", content=jpeg_content, content_type="image/jpeg"),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        # Получаем изображение
        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            content, content_type = await service.get_image(site_id, photo_id)

        assert content == jpeg_content
        assert content_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_get_image_missing_file_404(self, container, storage) -> None:
        """Получить изображение, когда файл удален из storage -> 404."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        # Получаем storage_key из БД
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            from app.domains.photo.repository import PhotoRepository

            repo = PhotoRepository(session)
            photo = await repo.get(photo_id)
            storage_key = photo.storage_key

        # Удаляем файл из storage
        await storage.delete(storage_key)

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            with pytest.raises(AppError) as exc_info:
                await service.get_image(site_id, photo_id)

            assert exc_info.value.status_code == 404


class TestPhotoServiceSetDateExtra:
    """Дополнительные тесты set_date."""

    @pytest.mark.asyncio
    async def test_set_date_foreign_site_404(self, container) -> None:
        """Установить дату для фото чужого сайта -> 404."""
        await seed_user(container)

        site_id = uuid.uuid4()
        other_site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            with pytest.raises(AppError) as exc_info:
                await service.set_date(other_site_id, photo_id, date(2025, 1, 15))

            assert exc_info.value.status_code == 404


class TestPhotoServiceGetPhotoExtra:
    """Дополнительные тесты get_photo."""

    @pytest.mark.asyncio
    async def test_get_photo_unknown_equipment_type(self, container, detector) -> None:
        """Получить фото с детекцией несуществующего типа оборудования."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.result = DetectionResult(
                model_version="v1",
                detections=[
                    RawDetection(class_ours="unknown", conf=0.95, bbox=(0.1, 0.2, 0.3, 0.4)),
                ],
            )
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photo_detail = await service.get_photo(site_id, photo_id)

        assert len(photo_detail.detections) == 0


class TestPhotoServiceNeighboursDating:
    """Тесты NEIGHBOURS дейтинга."""

    @pytest.mark.asyncio
    async def test_neighbours_chain_never_occurs(self, container) -> None:
        """Neighbour-датированные фото не служат источником для других."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="dated.jpg",
                content=create_jpeg_with_exif_date(date(2025, 1, 15)),
                content_type="image/jpeg",
            ),
            UploadInput(
                filename="undated1.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
            UploadInput(
                filename="undated2.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        # Оба undated получают дату от dated (индекс 0), не цепляются друг от друга
        assert report.items[1].photo.date_source == DateSource.NEIGHBOURS.value
        assert report.items[1].photo.captured_on == date(2025, 1, 15)
        assert report.items[2].photo.date_source == DateSource.NEIGHBOURS.value
        assert report.items[2].photo.captured_on == date(2025, 1, 15)

    @pytest.mark.asyncio
    async def test_neighbours_nearest_by_position_earlier_on_tie(self, container) -> None:
        """Neighbour выбирает ближайшее по позиции, на tie предпочитает более раннее."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        date1 = date(2025, 1, 10)
        date2 = date(2025, 1, 20)
        files = [
            UploadInput(
                filename="dated1.jpg",
                content=create_jpeg_with_exif_date(date1),
                content_type="image/jpeg",
            ),
            UploadInput(
                filename="undated.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
            UploadInput(
                filename="dated2.jpg",
                content=create_jpeg_with_exif_date(date2),
                content_type="image/jpeg",
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        # undated на позиции 1 равноудален от 0 и 2, должен выбрать раннее (0)
        assert report.items[1].photo.captured_on == date1


class TestPhotoServiceUploadExtra:
    """Дополнительные тесты upload_batch."""

    @pytest.mark.asyncio
    async def test_upload_batch_multiple_detections(self, container, detector) -> None:
        """Загрузить фото с несколькими детекциями."""
        await seed_user(container)

        site_id = uuid.uuid4()
        equipment_id1 = uuid.uuid4()
        equipment_id2 = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)

            equipment1 = EquipmentType(id=equipment_id1, code="crane", title="Кран")
            equipment2 = EquipmentType(id=equipment_id2, code="excavator", title="Экскаватор")
            session.add(equipment1)
            session.add(equipment2)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.result = DetectionResult(
                model_version="v1",
                detections=[
                    RawDetection(class_ours="crane", conf=0.95, bbox=(0.1, 0.2, 0.3, 0.4)),
                    RawDetection(class_ours="excavator", conf=0.85, bbox=(0.5, 0.6, 0.7, 0.8)),
                ],
            )
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photo_detail = await service.get_photo(site_id, photo_id)

        assert len(photo_detail.detections) == 2
        assert photo_detail.detections[0].equipment_code == "crane"
        assert photo_detail.detections[1].equipment_code == "excavator"

    @pytest.mark.asyncio
    async def test_upload_batch_empty_detections_list(self, container, detector) -> None:
        """Детектор возвращает пустой список детекций -> статус done."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.result = DetectionResult(model_version="v1", detections=[])
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        assert report.uploaded == 1
        assert report.items[0].photo.processing_status == ProcessingStatus.DONE.value

    @pytest.mark.asyncio
    async def test_upload_batch_unknown_equipment_class(self, container, detector) -> None:
        """Неизвестный класс оборудования -> пропускается без ошибки."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.result = DetectionResult(
                model_version="v1",
                detections=[
                    RawDetection(class_ours="unknown_class", conf=0.95, bbox=(0.1, 0.2, 0.3, 0.4)),
                ],
            )
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        assert report.uploaded == 1
        photo_id = report.items[0].photo.id

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photo_detail = await service.get_photo(site_id, photo_id)

        assert len(photo_detail.detections) == 0

    @pytest.mark.asyncio
    async def test_detector_generic_error(self, container, detector) -> None:
        """Детектор выбрасывает общее исключение -> статус failed."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.error = RuntimeError("Generic detector error")
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        assert report.uploaded == 1
        photo_id = report.items[0].photo.id

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            from app.domains.photo.repository import PhotoRepository

            repo = PhotoRepository(session)
            photo = await repo.get(photo_id)

        assert photo.processing_status == ProcessingStatus.FAILED.value


class TestPhotoServiceRedetect:
    """Тесты redetect."""

    @pytest.mark.asyncio
    async def test_redetect_same_model_version_keeps_rows(self, container, detector) -> None:
        """Переобнаружение с тем же model_version -> сохраняет существующие детекции."""
        await seed_user(container)

        site_id = uuid.uuid4()
        equipment_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)

            equipment = EquipmentType(id=equipment_id, code="crane", title="Кран")
            session.add(equipment)
            await session.commit()
            owner_id = owner.id

        # Загружаем с детекцией
        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.result = DetectionResult(
                model_version="v1",
                detections=[
                    RawDetection(class_ours="crane", conf=0.95, bbox=(0.1, 0.2, 0.3, 0.4)),
                ],
            )
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        # Получаем исходные детекции
        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photo_detail1 = await service.get_photo(site_id, photo_id)

        original_det_id = photo_detail1.detections[0].id

        # Переобнаруживаем с тем же model_version
        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.result = DetectionResult(
                model_version="v1",
                detections=[
                    RawDetection(class_ours="crane", conf=0.90, bbox=(0.2, 0.3, 0.4, 0.5)),
                ],
            )
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photo_detail2 = await service.redetect(site_id, photo_id)

        # ID детекции должны остаться прежними
        assert photo_detail2.detections[0].id == original_det_id

    @pytest.mark.asyncio
    async def test_redetect_different_model_version_replaces_rows(
        self, container, detector
    ) -> None:
        """Переобнаружение с другим model_version -> заменяет все детекции."""
        await seed_user(container)

        site_id = uuid.uuid4()
        equipment_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)

            equipment = EquipmentType(id=equipment_id, code="crane", title="Кран")
            session.add(equipment)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.result = DetectionResult(
                model_version="v1",
                detections=[
                    RawDetection(class_ours="crane", conf=0.95, bbox=(0.1, 0.2, 0.3, 0.4)),
                ],
            )
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photo_detail1 = await service.get_photo(site_id, photo_id)

        original_det_id = photo_detail1.detections[0].id

        # Переобнаруживаем с другим model_version
        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.result = DetectionResult(
                model_version="v2",
                detections=[
                    RawDetection(class_ours="crane", conf=0.92, bbox=(0.15, 0.25, 0.35, 0.45)),
                ],
            )
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photo_detail2 = await service.redetect(site_id, photo_id)

        # ID детекции должны измениться
        assert photo_detail2.detections[0].id != original_det_id

    @pytest.mark.asyncio
    async def test_redetect_detector_disabled_409(self, container, detector) -> None:
        """Детектор отключен (None) -> 409."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        # Переобнаруживаем с отключенным детектором
        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.result = None
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            with pytest.raises(AppError) as exc_info:
                await service.redetect(site_id, photo_id)

            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_redetect_detector_error_502(self, container, detector) -> None:
        """Ошибка детектора -> 502, данные не изменяются."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        photo_id = report.items[0].photo.id

        # Переобнаруживаем с ошибкой
        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.error = DetectorError("Service unavailable")
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            with pytest.raises(AppError) as exc_info:
                await service.redetect(site_id, photo_id)

            assert exc_info.value.status_code == 502


class TestPhotoServiceStorageErrors:
    """Тесты для ошибок хранилища и других граничных случаев."""

    @pytest.mark.asyncio
    async def test_upload_storage_put_error_creates_no_photo(self, container, storage) -> None:
        """storage.put выбрасывает StorageError -> нет фото в БД."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        from app.adapters.storage.base import StorageError

        async with container() as request_container:
            # Оборачиваем storage.put чтобы выбросить ошибку
            service = await request_container.get(PhotoService)

            async def failing_put(key, content, content_type):
                raise StorageError("Storage unavailable SECRET_SQL_TEXT")

            service._storage.put = failing_put
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        assert report.failed == 1
        assert report.items[0].error is not None
        assert report.items[0].photo is None
        assert "SECRET_SQL_TEXT" not in report.items[0].error

        # Проверяем что в БД нет фото
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            from sqlalchemy import select

            from app.domains.photo.models import Photo

            result = await session.execute(select(Photo).where(Photo.site_id == site_id))
            photos = result.scalars().all()
            assert len(photos) == 0

    @pytest.mark.asyncio
    async def test_upload_commit_failure_removes_stored_object(self, container, storage) -> None:
        """Ошибка commit после storage.put -> удаляет файл из storage."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        captured_key = None

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            original_put = service._storage.put

            async def capturing_put(key, content, content_type):
                nonlocal captured_key
                captured_key = key
                await original_put(key, content, content_type)

            service._storage.put = capturing_put

            # Оборачиваем commit чтобы выбросить ошибку
            original_commit = service._session.commit

            call_count = 0

            async def failing_commit():
                nonlocal call_count
                call_count += 1
                if call_count > 0:
                    raise RuntimeError("Database connection lost SECRET_SQL_TEXT")
                await original_commit()

            service._session.commit = failing_commit
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        assert report.failed == 1
        assert report.items[0].error is not None
        assert captured_key is not None
        assert "SECRET_SQL_TEXT" not in report.items[0].error

        # Проверяем что файл удален из storage
        exists = await storage.exists(captured_key)
        assert not exists

    @pytest.mark.asyncio
    async def test_upload_detector_none_leaves_photo_pending(self, container) -> None:
        """Детектор отключен (None) -> статус PENDING, нет детекций."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="photo.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.disabled = True
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        assert report.uploaded == 1
        assert report.items[0].photo.processing_status == ProcessingStatus.PENDING.value

        # Проверяем что нет детекций
        photo_id = report.items[0].photo.id
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            from app.domains.photo.repository import DetectionRepository

            repo = DetectionRepository(session)
            detections = await repo.list_by_photo(photo_id)
            assert len(detections) == 0

    @pytest.mark.asyncio
    async def test_upload_detector_error_marks_failed_but_keeps_photo(
        self, container, detector
    ) -> None:
        """Детектор выбрасывает DetectorError -> FAILED статус, дата сохранена."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        test_date = date(2025, 1, 15)
        files = [
            UploadInput(
                filename="photo.jpg",
                content=create_jpeg_with_exif_date(test_date),
                content_type="image/jpeg",
            ),
        ]

        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            detector_inst.error = DetectorError("Detector unavailable")
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        assert report.uploaded == 1
        assert report.items[0].photo.processing_status == ProcessingStatus.FAILED.value
        assert report.items[0].photo.captured_on == test_date

    @pytest.mark.asyncio
    async def test_upload_oversized_file_is_a_file_error(self, container, monkeypatch) -> None:
        """Файл слишком большой -> ошибка размера, батч продолжается с остальными."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        # Подготавливаем: нормальное PNG (289 байт) и крошечное PNG (69 байт)
        # Устанавливаем лимит 100 байт для теста
        files = [
            UploadInput(
                filename="oversized.png",
                content=create_png_image(),  # 289 bytes > 100 byte limit
                content_type="image/png",
            ),
            UploadInput(
                filename="tiny.png",
                content=create_tiny_png(),  # 69 bytes < 100 byte limit
                content_type="image/png",
            ),
        ]

        async with container() as request_container:
            settings = await request_container.get(Settings)
            service = await request_container.get(PhotoService)
            # Лимит ~100 байт: max_upload_mb дробное, monkeypatch откатит значение после теста
            # (Settings общий на процесс из lru_cache, править его без отката нельзя).
            monkeypatch.setattr(settings.storage, "max_upload_mb", 100 / (1024 * 1024))
            assert settings.storage.max_upload_bytes in (99, 100)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        # Первый файл должен быть отклонён по размеру
        assert report.uploaded == 1
        assert report.failed == 1
        assert "слишком большой" in report.items[0].error.lower()
        assert report.items[0].photo is None
        # Второй файл должен быть загружен успешно
        assert report.items[1].photo is not None

    @pytest.mark.asyncio
    async def test_upload_original_name_is_basename(self, container) -> None:
        """Filename с path parts -> сохраняется только basename."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(
                filename="../../etc/x.png",
                content=create_png_image(),
                content_type="image/png",
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        assert report.uploaded == 1
        assert report.items[0].photo.original_name == "x.png"

        # Проверяем что storage_key не содержит ".."
        photo_id = report.items[0].photo.id
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            from app.domains.photo.repository import PhotoRepository

            repo = PhotoRepository(session)
            photo = await repo.get(photo_id)
            assert ".." not in photo.storage_key
            assert "etc" not in photo.storage_key

    @pytest.mark.asyncio
    async def test_list_photos_ordered_by_upload_time(self, container) -> None:
        """list_photos возвращает фото в порядке uploaded_at."""
        from datetime import datetime

        from sqlalchemy import update

        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        # Первая загрузка
        files1 = [
            UploadInput(
                filename="photo1.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report1 = await service.upload_batch(site_id, files1)

        photo1_id = report1.items[0].photo.id

        # Вторая загрузка
        files2 = [
            UploadInput(
                filename="photo2.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report2 = await service.upload_batch(site_id, files2)

        photo2_id = report2.items[0].photo.id

        # Устанавливаем явно разные uploaded_at значения
        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            # photo1 - более старое
            await session.execute(
                update(Photo)
                .where(Photo.id == photo1_id)
                .values(uploaded_at=datetime(2026, 1, 1, tzinfo=UTC))
            )
            # photo2 - более новое
            await session.execute(
                update(Photo)
                .where(Photo.id == photo2_id)
                .values(uploaded_at=datetime(2026, 1, 2, tzinfo=UTC))
            )
            await session.commit()

        # Проверяем порядок (по uploaded_at)
        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photos = await service.list_photos(site_id)

        assert len(photos) == 2
        assert photos[0].id == photo1_id
        assert photos[1].id == photo2_id

        # Обратная проверка: меняем timestamps - должен измениться порядок
        async with container() as request_container:
            session = await request_container.get(AsyncSession)

            # photo1 - более новое
            await session.execute(
                update(Photo)
                .where(Photo.id == photo1_id)
                .values(uploaded_at=datetime(2026, 2, 2, tzinfo=UTC))
            )
            # photo2 - более старое
            await session.execute(
                update(Photo)
                .where(Photo.id == photo2_id)
                .values(uploaded_at=datetime(2026, 2, 1, tzinfo=UTC))
            )
            await session.commit()

        # Проверяем что порядок изменился
        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            photos_reversed = await service.list_photos(site_id)

        assert len(photos_reversed) == 2
        assert photos_reversed[0].id == photo2_id
        assert photos_reversed[1].id == photo1_id

    @pytest.mark.asyncio
    async def test_upload_corrupt_unsupported_empty_are_separate_errors(self, container) -> None:
        """Три разных типа ошибок -> три разных сообщения об ошибке."""
        await seed_user(container)

        site_id = uuid.uuid4()
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)
            await session.commit()
            owner_id = owner.id

        files = [
            UploadInput(filename="corrupt.jpg", content=b"not an image", content_type="image/jpeg"),
            UploadInput(
                filename="unsupported.gif", content=create_gif_image(), content_type="image/gif"
            ),
            UploadInput(filename="empty.jpg", content=b"", content_type="image/jpeg"),
            UploadInput(
                filename="valid.jpg", content=create_jpeg_image(), content_type="image/jpeg"
            ),
        ]

        async with container() as request_container:
            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()
            report = await service.upload_batch(site_id, files)

        assert report.uploaded == 1
        assert report.failed == 3

        # Проверяем что ошибки разные
        error1 = report.items[0].error
        error2 = report.items[1].error
        error3 = report.items[2].error

        assert error1 is not None
        assert error2 is not None
        assert error3 is not None
        assert error1 != error2
        assert error2 != error3
        assert error1 != error3

    @pytest.mark.asyncio
    async def test_upload_batch_triggers_observation_recalculator_hook(
        self, container, detector
    ) -> None:
        """upload_batch with dated photos triggers observation recalculation end-to-end.

        Это доказывает, что hook photo → observation действительно срабатывает через
        реальный LiveObservationRecalculator, когда ObservationProvider подключён.
        """
        await seed_user(container)

        site_id = uuid.uuid4()
        observation_date = date(2025, 1, 15)

        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            owner = User(id=uuid.uuid4(), full_name="Owner")
            session.add(owner)
            site = Site(id=site_id, name="Test Site", owner_id=owner.id)
            session.add(site)

            # Создаём EquipmentType для детектора
            equipment = EquipmentType(id=uuid.uuid4(), code="crane", title="Кран")
            session.add(equipment)
            await session.commit()

            owner_id = owner.id
            equipment_id = equipment.id

        # Создаём файл с EXIF датой
        files = [
            UploadInput(
                filename="photo1.jpg",
                content=create_jpeg_with_exif_date(observation_date),
                content_type="image/jpeg",
            ),
        ]

        # Загружаем файл
        async with container() as request_container:
            detector_inst = cast(FakeDetector, await request_container.get(DetectorClient))
            # Конфигурируем детектор для возврата одного detection
            detector_inst.result = DetectionResult(
                model_version="v1",
                detections=[RawDetection(bbox=[0.1, 0.1, 0.9, 0.9], class_ours="crane", conf=0.95)],
            )

            service = await request_container.get(PhotoService)
            service._guard._current_user = type("obj", (object,), {"id": owner_id})()

            report = await service.upload_batch(site_id, files)

        assert report.uploaded == 1

        # Теперь проверяем, что наблюдение было автоматически создано
        # путём запроса ObservationRepository из ТОГОже контейнера
        async with container() as request_container:
            from app.domains.observation.repository import ObservationRepository

            obs_repo = await request_container.get(ObservationRepository)
            observation = await obs_repo.get_by_site_and_date(site_id, observation_date)

        # Наблюдение должно существовать (доказывает, что hook сработал)
        assert observation is not None
        assert observation.site_id == site_id
        assert observation.observed_on == observation_date
        # photo_count должен быть 1 (у нас загруз 1 файл)
        assert observation.photo_count == 1
        # Наблюдаемость должна быть medium (1 фото >= min_photos_medium=1, но < min_photos_high=3)
        assert observation.observability == "medium"
