"""HTTP-контракт для фотографий и детекций."""

import io
import uuid
from datetime import date, timedelta

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.datastructures import UploadFile

from app.adapters.ml.base import (
    DetectionResult,
    DetectorError,
    RawDetection,
)
from app.core.settings import Settings
from app.domains.methodology.models import EquipmentType
from app.domains.user.service import UserService
from tests.fakes import FakeDetector


async def seed_stand_user(container: AsyncContainer) -> None:
    """Создать стендового пользователя."""
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


def create_jpeg_image(width: int = 200, height: int = 200) -> bytes:
    """Создать JPEG изображение."""
    img = Image.new("RGB", (width, height), color="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def create_png_image(width: int = 200, height: int = 200) -> bytes:
    """Создать PNG изображение."""
    img = Image.new("RGB", (width, height), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestPhotoRouter:
    """Тесты HTTP маршрутов фотографий."""

    @pytest.mark.asyncio
    async def test_post_upload_single_file_with_201(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """POST /photos с одним файлом возвращает 201 и UploadReport."""
        await seed_stand_user(container)

        # Создаём сайт
        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Загружаем файл
        jpeg_data = create_jpeg_image()
        response = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        assert response.status_code == 201
        data = response.json()
        assert data["uploaded"] == 1
        assert data["failed"] == 0
        assert len(data["items"]) == 1
        assert data["items"][0]["photo"] is not None
        assert data["items"][0]["error"] is None

    @pytest.mark.asyncio
    async def test_post_upload_multiple_files_with_201(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """POST /photos с несколькими файлами возвращает 201."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        jpeg_data = create_jpeg_image()
        png_data = create_png_image()

        response = await client.post(
            f"/sites/{site_id}/photos",
            files=[
                ("files", ("test1.jpg", jpeg_data, "image/jpeg")),
                ("files", ("test2.png", png_data, "image/png")),
            ],
        )

        assert response.status_code == 201
        data = response.json()
        assert data["uploaded"] == 2
        assert data["failed"] == 0

    @pytest.mark.asyncio
    async def test_post_upload_empty_list_with_422(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """POST /photos с пустым списком возвращает 422."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        response = await client.post(f"/sites/{site_id}/photos", files=[])

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_post_upload_oversized_single_file_with_error(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """POST /photos с одним слишком большим файлом возвращает failed=1."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Создаём огромный файл (больше чем max_upload_bytes)
        # max_upload_mb по умолчанию 50, так что max_upload_bytes = 50*1024*1024
        # Мы создадим файл чуть больше этого
        async with container() as request_container:
            settings = await request_container.get(Settings)
            max_bytes = settings.storage.max_upload_bytes

        # Создаём файл на max_bytes + 1 байт
        huge_data = b"X" * (max_bytes + 1)

        response = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("huge.jpg", huge_data, "image/jpeg"))],
        )

        assert response.status_code == 201
        data = response.json()
        assert data["failed"] == 1
        assert data["uploaded"] == 0
        assert "слишком большой" in data["items"][0]["error"].lower()

    @pytest.mark.asyncio
    async def test_get_list_photos_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /photos возвращает 200 и список."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Загружаем файл
        jpeg_data = create_jpeg_image()
        await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        # Получаем список
        response = await client.get(f"/sites/{site_id}/photos")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["original_name"] == "test.jpg"

    @pytest.mark.asyncio
    async def test_get_list_photos_with_undated_filter(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /photos?undated=true возвращает только photos без даты."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Загружаем файлы
        jpeg_data = create_jpeg_image()
        await client.post(
            f"/sites/{site_id}/photos",
            files=[
                ("files", ("test1.jpg", jpeg_data, "image/jpeg")),
                ("files", ("test2.jpg", jpeg_data, "image/jpeg")),
            ],
        )

        # Получаем undated список
        response = await client.get(f"/sites/{site_id}/photos?undated=true")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_photo_detail_with_200(
        self, client: AsyncClient, container: AsyncContainer, detector: FakeDetector
    ) -> None:
        """GET /photos/{id} возвращает 200 и PhotoDetail."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Конфигурируем детектор
        detector.result = DetectionResult(
            model_version="v1",
            detections=[RawDetection(bbox=[0.1, 0.1, 0.9, 0.9], class_ours="COMP_1", conf=0.95)],
        )

        # Создаём EquipmentType
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            equipment = EquipmentType(id=uuid.uuid4(), code="COMP_1", title="Компрессор")
            session.add(equipment)
            await session.commit()

        # Загружаем файл
        jpeg_data = create_jpeg_image()
        upload_resp = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        photo_id = upload_resp.json()["items"][0]["photo"]["id"]

        # Получаем детали
        response = await client.get(f"/sites/{site_id}/photos/{photo_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == photo_id
        assert data["original_name"] == "test.jpg"
        assert "detections" in data
        assert isinstance(data["detections"], list)

    @pytest.mark.asyncio
    async def test_get_photo_nonexistent_with_404(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /photos/{nonexistent_id} возвращает 404."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        fake_id = uuid.uuid4()
        response = await client.get(f"/sites/{site_id}/photos/{fake_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_patch_photo_date_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """PATCH /photos/{id}/date обновляет дату."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Загружаем файл
        jpeg_data = create_jpeg_image()
        upload_resp = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        photo_id = upload_resp.json()["items"][0]["photo"]["id"]

        # Обновляем дату
        new_date = date(2024, 1, 15)
        response = await client.patch(
            f"/sites/{site_id}/photos/{photo_id}/date",
            json={"captured_on": str(new_date)},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["captured_on"] == str(new_date)

    @pytest.mark.asyncio
    async def test_patch_photo_date_future_with_422(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """PATCH /photos/{id}/date с будущей датой возвращает 422."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Загружаем файл
        jpeg_data = create_jpeg_image()
        upload_resp = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        photo_id = upload_resp.json()["items"][0]["photo"]["id"]

        # Пытаемся установить будущую дату
        future_date = date.today() + timedelta(days=1)
        response = await client.patch(
            f"/sites/{site_id}/photos/{photo_id}/date",
            json={"captured_on": str(future_date)},
        )

        assert response.status_code == 422
        # Строка для интерфейса, а не список ошибок pydantic (bug-reports/003)
        assert response.json()["detail"] == "Дата не может быть в будущем"

    @pytest.mark.asyncio
    async def test_get_photo_image_with_200(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /photos/{id}/image возвращает 200 с изображением."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Загружаем файл
        jpeg_data = create_jpeg_image()
        upload_resp = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        photo_id = upload_resp.json()["items"][0]["photo"]["id"]

        # Получаем изображение
        response = await client.get(f"/sites/{site_id}/photos/{photo_id}/image")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("image/")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "Cache-Control" in response.headers
        assert response.content == jpeg_data

    @pytest.mark.asyncio
    async def test_get_photo_image_nosniff_header(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /photos/{id}/image имеет X-Content-Type-Options: nosniff."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        jpeg_data = create_jpeg_image()
        upload_resp = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        photo_id = upload_resp.json()["items"][0]["photo"]["id"]

        response = await client.get(f"/sites/{site_id}/photos/{photo_id}/image")

        assert response.status_code == 200
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_get_annotated_image_with_200(
        self, client: AsyncClient, container: AsyncContainer, detector: FakeDetector
    ) -> None:
        """GET /photos/{id}/annotated возвращает 200 с PNG."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Конфигурируем детектор
        detector.result = DetectionResult(
            model_version="v1",
            detections=[RawDetection(bbox=[0.2, 0.2, 0.8, 0.8], class_ours="COMP_1", conf=0.95)],
        )

        # Создаём EquipmentType
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            equipment = EquipmentType(id=uuid.uuid4(), code="COMP_1", title="Компрессор")
            session.add(equipment)
            await session.commit()

        # Загружаем файл
        jpeg_data = create_jpeg_image()
        upload_resp = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        photo_id = upload_resp.json()["items"][0]["photo"]["id"]

        # Получаем аннотированное изображение
        response = await client.get(f"/sites/{site_id}/photos/{photo_id}/annotated")

        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        # Проверяем что это валидный PNG
        img = Image.open(io.BytesIO(response.content))
        assert img.format == "PNG"

    @pytest.mark.asyncio
    async def test_post_detect_with_200(
        self, client: AsyncClient, container: AsyncContainer, detector: FakeDetector
    ) -> None:
        """POST /photos/{id}/detect переобнаруживает оборудование."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Конфигурируем детектор для исходной детекции
        detector.result = DetectionResult(
            model_version="v1",
            detections=[RawDetection(bbox=[0.1, 0.1, 0.9, 0.9], class_ours="COMP_1", conf=0.95)],
        )

        # Создаём EquipmentType
        async with container() as request_container:
            session = await request_container.get(AsyncSession)
            equipment = EquipmentType(id=uuid.uuid4(), code="COMP_1", title="Компрессор")
            session.add(equipment)
            await session.commit()

        # Загружаем файл
        jpeg_data = create_jpeg_image()
        upload_resp = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        photo_id = upload_resp.json()["items"][0]["photo"]["id"]

        # Переобнаруживаем
        response = await client.post(f"/sites/{site_id}/photos/{photo_id}/detect")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == photo_id

    @pytest.mark.asyncio
    async def test_post_detect_disabled_with_409(
        self, client: AsyncClient, container: AsyncContainer, detector: FakeDetector
    ) -> None:
        """POST /photos/{id}/detect когда детектор отключен возвращает 409."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Конфигурируем детектор как отключенный
        detector.disabled = True

        # Загружаем файл
        jpeg_data = create_jpeg_image()
        upload_resp = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        photo_id = upload_resp.json()["items"][0]["photo"]["id"]

        # Пытаемся переобнаружить
        response = await client.post(f"/sites/{site_id}/photos/{photo_id}/detect")

        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_post_detect_error_with_502(
        self, client: AsyncClient, container: AsyncContainer, detector: FakeDetector
    ) -> None:
        """POST /photos/{id}/detect когда детектор ошибается возвращает 502."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Конфигурируем детектор на ошибку
        detector.error = DetectorError("Service unavailable")

        # Загружаем файл
        jpeg_data = create_jpeg_image()
        upload_resp = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        photo_id = upload_resp.json()["items"][0]["photo"]["id"]

        # Пытаемся переобнаружить
        response = await client.post(f"/sites/{site_id}/photos/{photo_id}/detect")

        assert response.status_code == 502

    @pytest.mark.asyncio
    async def test_cascade_delete_photos_on_site_deletion(
        self, engine, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """DELETE /sites/{id} удаляет сайт и его фотографии (каскад)."""
        # Включаем FK pragma на общем соединении (StaticPool)
        async with engine.connect() as conn:
            await conn.exec_driver_sql("PRAGMA foreign_keys=ON")

        await seed_stand_user(container)

        # Создаём сайт
        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        # Загружаем фотографии
        jpeg_data = create_jpeg_image()
        await client.post(
            f"/sites/{site_id}/photos",
            files=[
                ("files", ("test1.jpg", jpeg_data, "image/jpeg")),
                ("files", ("test2.jpg", jpeg_data, "image/jpeg")),
            ],
        )

        # Удаляем сайт
        response = await client.delete(f"/sites/{site_id}")
        assert response.status_code == 204

        # Проверяем что фотографии удалены (используем PRAGMA foreign_keys=ON)
        from sqlalchemy import text

        async with engine.begin() as conn:
            # Проверяем что photos пуста
            result = await conn.execute(text("SELECT COUNT(*) FROM photos"))
            photo_count = result.scalar() or 0
            assert photo_count == 0

            # Проверяем что detections пуста
            result = await conn.execute(text("SELECT COUNT(*) FROM detections"))
            detection_count = result.scalar() or 0
            assert detection_count == 0

    @pytest.mark.asyncio
    async def test_get_foreign_site_photo_with_404(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /photos/{id} от чужого сайта возвращает 404."""
        await seed_stand_user(container)

        # Создаём два сайта
        site1_resp = await client.post("/sites", json={"name": "Site 1"})
        site1_id = site1_resp.json()["id"]

        site2_resp = await client.post("/sites", json={"name": "Site 2"})
        site2_id = site2_resp.json()["id"]

        # Загружаем фотографию в сайт 1
        jpeg_data = create_jpeg_image()
        upload_resp = await client.post(
            f"/sites/{site1_id}/photos",
            files=[("files", ("test.jpg", jpeg_data, "image/jpeg"))],
        )

        photo_id = upload_resp.json()["items"][0]["photo"]["id"]

        # Пытаемся получить фотографию из сайта 2
        response = await client.get(f"/sites/{site2_id}/photos/{photo_id}")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_invalid_photo_uuid_with_422(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """GET /photos/{invalid_uuid} возвращает 422."""
        await seed_stand_user(container)

        site_resp = await client.post("/sites", json={"name": "Test Site"})
        site_id = site_resp.json()["id"]

        response = await client.get(f"/sites/{site_id}/photos/not-a-uuid")

        assert response.status_code == 422


async def _create_site(client: AsyncClient) -> str:
    site_resp = await client.post("/sites", json={"name": "Test Site"})
    return site_resp.json()["id"]


async def _seed_equipment(container: AsyncContainer, code: str = "COMP_1") -> None:
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(EquipmentType(id=uuid.uuid4(), code=code, title="Компрессор"))
        await session.commit()


class TestPhotoRouterGuards:
    """Лимиты роутера, реальная отрисовка рамок и правила переобработки."""

    @pytest.mark.asyncio
    async def test_post_upload_too_many_files_413_before_processing(
        self,
        client: AsyncClient,
        container: AsyncContainer,
        detector: FakeDetector,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Пачка длиннее max_batch_files -> 413 целиком, файлы не читаются и не обрабатываются."""
        await seed_stand_user(container)
        site_id = await _create_site(client)
        settings = await container.get(Settings)
        monkeypatch.setattr(settings.storage, "max_batch_files", 2)

        reads: list[int] = []
        original_read = UploadFile.read

        async def counting_read(self: UploadFile, size: int = -1) -> bytes:
            reads.append(size)
            return await original_read(self, size)

        monkeypatch.setattr(UploadFile, "read", counting_read)

        files = [("files", (f"p{i}.jpg", create_jpeg_image(), "image/jpeg")) for i in range(3)]
        response = await client.post(f"/sites/{site_id}/photos", files=files)

        assert response.status_code == 413
        assert reads == [], "файлы не должны читаться до проверки размера пачки"
        assert detector.calls == []
        listing = await client.get(f"/sites/{site_id}/photos")
        assert listing.json() == []

    @pytest.mark.asyncio
    async def test_post_upload_batch_at_limit_is_accepted(
        self,
        client: AsyncClient,
        container: AsyncContainer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ровно max_batch_files файлов принимается (граница не сдвинута)."""
        await seed_stand_user(container)
        site_id = await _create_site(client)
        settings = await container.get(Settings)
        monkeypatch.setattr(settings.storage, "max_batch_files", 2)

        files = [("files", (f"p{i}.jpg", create_jpeg_image(), "image/jpeg")) for i in range(2)]
        response = await client.post(f"/sites/{site_id}/photos", files=files)

        assert response.status_code == 201
        assert response.json()["uploaded"] == 2

    @pytest.mark.asyncio
    async def test_get_annotated_draws_box_pixels(
        self, client: AsyncClient, container: AsyncContainer, detector: FakeDetector
    ) -> None:
        """/annotated рисует рамку: пиксели на границе бокса отличаются от оригинала."""
        await seed_stand_user(container)
        site_id = await _create_site(client)
        await _seed_equipment(container)
        detector.result = DetectionResult(
            model_version="v1",
            detections=[RawDetection(bbox=(0.25, 0.25, 0.75, 0.75), class_ours="COMP_1", conf=0.9)],
        )
        upload = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("a.jpg", create_jpeg_image(), "image/jpeg"))],
        )
        photo_id = upload.json()["items"][0]["photo"]["id"]

        original = Image.open(
            io.BytesIO((await client.get(f"/sites/{site_id}/photos/{photo_id}/image")).content)
        ).convert("RGB")
        annotated = Image.open(
            io.BytesIO((await client.get(f"/sites/{site_id}/photos/{photo_id}/annotated")).content)
        ).convert("RGB")

        assert annotated.size == original.size
        # левая граница бокса: x = 0.25 * 200 = 50
        assert any(
            annotated.getpixel((x, 100)) != original.getpixel((x, 100)) for x in range(46, 56)
        )
        # угол кадра далеко от бокса и подписи остаётся как в оригинале
        assert annotated.getpixel((190, 190)) == original.getpixel((190, 190))

    @pytest.mark.asyncio
    async def test_post_detect_same_model_version_keeps_detection_ids(
        self, client: AsyncClient, container: AsyncContainer, detector: FakeDetector
    ) -> None:
        """Переобработка той же model_version не трогает существующие детекции."""
        await seed_stand_user(container)
        site_id = await _create_site(client)
        await _seed_equipment(container)
        detector.result = DetectionResult(
            model_version="v1",
            detections=[RawDetection(bbox=(0.1, 0.1, 0.5, 0.5), class_ours="COMP_1", conf=0.9)],
        )
        upload = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("a.jpg", create_jpeg_image(), "image/jpeg"))],
        )
        photo_id = upload.json()["items"][0]["photo"]["id"]
        before = (await client.get(f"/sites/{site_id}/photos/{photo_id}")).json()["detections"]
        assert len(before) == 1

        response = await client.post(f"/sites/{site_id}/photos/{photo_id}/detect")

        assert response.status_code == 200
        after = response.json()["detections"]
        assert [d["id"] for d in after] == [d["id"] for d in before]

    @pytest.mark.asyncio
    async def test_post_detect_new_model_version_replaces_detections(
        self, client: AsyncClient, container: AsyncContainer, detector: FakeDetector
    ) -> None:
        """Другая model_version заменяет все детекции кадра новыми."""
        await seed_stand_user(container)
        site_id = await _create_site(client)
        await _seed_equipment(container)
        detector.result = DetectionResult(
            model_version="v1",
            detections=[RawDetection(bbox=(0.1, 0.1, 0.5, 0.5), class_ours="COMP_1", conf=0.9)],
        )
        upload = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("a.jpg", create_jpeg_image(), "image/jpeg"))],
        )
        photo_id = upload.json()["items"][0]["photo"]["id"]
        before = (await client.get(f"/sites/{site_id}/photos/{photo_id}")).json()["detections"]

        detector.result = DetectionResult(
            model_version="v2",
            detections=[
                RawDetection(bbox=(0.1, 0.1, 0.4, 0.4), class_ours="COMP_1", conf=0.8),
                RawDetection(bbox=(0.5, 0.5, 0.9, 0.9), class_ours="COMP_1", conf=0.7),
            ],
        )
        response = await client.post(f"/sites/{site_id}/photos/{photo_id}/detect")

        assert response.status_code == 200
        after = response.json()["detections"]
        assert len(after) == 2
        assert {d["model_version"] for d in after} == {"v2"}
        assert not {d["id"] for d in after} & {d["id"] for d in before}


class TestPhotoRouterDetectBacklog:
    """Тесты для POST /sites/{id}/photos/detect."""

    @pytest.mark.asyncio
    async def test_detect_backlog_endpoint_exists(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """POST /detect endpoint returns 200 with backlog report."""
        await seed_stand_user(container)
        site_resp = await client.post("/sites", json={"name": "Test"})
        site_id = site_resp.json()["id"]
        response = await client.post(f"/sites/{site_id}/photos/detect")
        assert response.status_code == 200
        data = response.json()
        assert "processed" in data
        assert "done" in data
        assert "failed" in data
        assert "skipped" in data

    @pytest.mark.asyncio
    async def test_detect_backlog_invalid_status_422(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """POST /detect?status=bogus → 422."""
        await seed_stand_user(container)
        site_resp = await client.post("/sites", json={"name": "Test"})
        site_id = site_resp.json()["id"]
        response = await client.post(f"/sites/{site_id}/photos/detect?status=bogus")
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_redetect_endpoint_still_works(
        self, client: AsyncClient, container: AsyncContainer
    ) -> None:
        """POST /sites/{id}/photos/{photo_id}/detect still works (not shadowed)."""
        await seed_stand_user(container)
        site_resp = await client.post("/sites", json={"name": "Test"})
        site_id = site_resp.json()["id"]
        jpeg_data = create_jpeg_image()
        upload = await client.post(
            f"/sites/{site_id}/photos",
            files=[("files", ("a.jpg", jpeg_data, "image/jpeg"))],
        )
        photo_id = upload.json()["items"][0]["photo"]["id"]
        response = await client.post(f"/sites/{site_id}/photos/{photo_id}/detect")
        assert response.status_code == 200
        assert "detections" in response.json()
