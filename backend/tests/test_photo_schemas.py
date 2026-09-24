"""Pydantic-схемы для photo домена: PhotoRead, DetectionRead, DateUpdate, и т.д."""

import uuid
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.domains.photo.models import Detection, Photo, ProcessingStatus
from app.domains.photo.schemas import (
    DateUpdate,
    DetectionRead,
    PhotoDetail,
    PhotoRead,
    UploadItem,
    UploadReport,
)


class TestPhotoRead:
    """Тесты PhotoRead schema."""

    def test_photo_read_from_orm_object(self) -> None:
        """PhotoRead корректно создаётся из ORM объекта Photo."""
        site_id = uuid.uuid4()
        photo_id = uuid.uuid4()
        photo = Photo(
            id=photo_id,
            site_id=site_id,
            storage_key="test.jpg",
            original_name="photo.jpg",
            width=800,
            height=600,
            captured_on=date(2025, 1, 15),
            date_source="metadata",
            processing_status=ProcessingStatus.DONE.value,
            uploaded_at=datetime(2025, 1, 10, tzinfo=UTC),
        )

        schema = PhotoRead.model_validate(photo)

        assert schema.id == photo_id
        assert schema.site_id == site_id
        assert schema.original_name == "photo.jpg"
        assert schema.width == 800
        assert schema.height == 600
        assert schema.captured_on == date(2025, 1, 15)
        assert schema.date_source == "metadata"
        assert schema.processing_status == ProcessingStatus.DONE.value
        assert schema.uploaded_at == datetime(2025, 1, 10, tzinfo=UTC)

    def test_photo_read_without_captured_on(self) -> None:
        """PhotoRead правильно обрабатывает None для captured_on и date_source."""
        photo = Photo(
            id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            storage_key="test.jpg",
            original_name="photo.jpg",
            width=800,
            height=600,
            captured_on=None,
            date_source=None,
            processing_status=ProcessingStatus.PENDING.value,
            uploaded_at=datetime(2025, 1, 10, tzinfo=UTC),
        )

        schema = PhotoRead.model_validate(photo)

        assert schema.captured_on is None
        assert schema.date_source is None


class TestDetectionRead:
    """Тесты DetectionRead schema."""

    def test_detection_read_from_orm_object(self) -> None:
        """DetectionRead может быть создана из Detection ORM объекта.

        Примечание: equipment_code и equipment_title должны быть добавлены в schema
        при создании из ORM (обычно через join с EquipmentType).
        """
        detection_id = uuid.uuid4()
        photo_id = uuid.uuid4()
        equipment_type_id = uuid.uuid4()

        detection = Detection(
            id=detection_id,
            photo_id=photo_id,
            equipment_type_id=equipment_type_id,
            bbox=[0.1, 0.2, 0.3, 0.4],
            score=0.95,
            model_version="yoloe-26s.pt",
        )

        # Добавляем equipment_code и equipment_title вручную (в реальности из join)
        object.__setattr__(detection, "equipment_code", "CRANE_1")
        object.__setattr__(detection, "equipment_title", "Crane Type A")

        schema = DetectionRead.model_validate(detection)

        assert schema.id == detection_id
        assert schema.equipment_type_id == equipment_type_id
        assert schema.equipment_code == "CRANE_1"
        assert schema.equipment_title == "Crane Type A"
        assert schema.bbox == [0.1, 0.2, 0.3, 0.4]
        assert schema.score == 0.95
        assert schema.model_version == "yoloe-26s.pt"


class TestPhotoDetail:
    """Тесты PhotoDetail schema (Photo с Detections)."""

    def test_photo_detail_structure(self) -> None:
        """PhotoDetail содержит PhotoRead + list[DetectionRead]."""
        photo_id = uuid.uuid4()
        site_id = uuid.uuid4()

        # Создаём PhotoRead-like данные
        photo_data = {
            "id": photo_id,
            "site_id": site_id,
            "original_name": "photo.jpg",
            "width": 800,
            "height": 600,
            "captured_on": date(2025, 1, 15),
            "date_source": "metadata",
            "processing_status": ProcessingStatus.DONE.value,
            "uploaded_at": datetime(2025, 1, 10, tzinfo=UTC),
            "detections": [
                {
                    "id": uuid.uuid4(),
                    "equipment_type_id": uuid.uuid4(),
                    "equipment_code": "CRANE_1",
                    "equipment_title": "Crane A",
                    "bbox": [0.1, 0.2, 0.3, 0.4],
                    "score": 0.95,
                    "model_version": "yoloe-26s.pt",
                }
            ],
        }

        schema = PhotoDetail.model_validate(photo_data)

        assert schema.id == photo_id
        assert schema.original_name == "photo.jpg"
        assert len(schema.detections) == 1
        assert schema.detections[0].equipment_code == "CRANE_1"


class TestUploadItem:
    """Тесты UploadItem schema."""

    def test_upload_item_with_photo(self) -> None:
        """UploadItem с успешной загрузкой (photo не None, error = None)."""
        photo_id = uuid.uuid4()
        item_data = {
            "filename": "photo.jpg",
            "photo": {
                "id": photo_id,
                "site_id": uuid.uuid4(),
                "original_name": "photo.jpg",
                "width": 800,
                "height": 600,
                "captured_on": None,
                "date_source": None,
                "processing_status": ProcessingStatus.PENDING.value,
                "uploaded_at": datetime(2025, 1, 10, tzinfo=UTC),
            },
            "error": None,
        }

        item = UploadItem.model_validate(item_data)

        assert item.filename == "photo.jpg"
        assert item.photo is not None
        assert item.photo.id == photo_id
        assert item.error is None

    def test_upload_item_with_error(self) -> None:
        """UploadItem с ошибкой (photo = None, error не None)."""
        item_data = {
            "filename": "photo.jpg",
            "photo": None,
            "error": "Invalid image format",
        }

        item = UploadItem.model_validate(item_data)

        assert item.filename == "photo.jpg"
        assert item.photo is None
        assert item.error == "Invalid image format"


class TestUploadReport:
    """Тесты UploadReport schema."""

    def test_upload_report_shape(self) -> None:
        """UploadReport содержит items, uploaded, failed."""
        report_data = {
            "items": [
                {
                    "filename": "photo1.jpg",
                    "photo": {
                        "id": uuid.uuid4(),
                        "site_id": uuid.uuid4(),
                        "original_name": "photo1.jpg",
                        "width": 800,
                        "height": 600,
                        "captured_on": None,
                        "date_source": None,
                        "processing_status": ProcessingStatus.PENDING.value,
                        "uploaded_at": datetime(2025, 1, 10, tzinfo=UTC),
                    },
                    "error": None,
                },
                {
                    "filename": "photo2.jpg",
                    "photo": None,
                    "error": "Corrupted file",
                },
            ],
            "uploaded": 1,
            "failed": 1,
        }

        report = UploadReport.model_validate(report_data)

        assert len(report.items) == 2
        assert report.uploaded == 1
        assert report.failed == 1
        assert report.items[0].photo is not None
        assert report.items[1].error is not None


class TestDateUpdate:
    """Тесты DateUpdate schema с валидацией."""

    def test_date_update_with_today_is_valid(self) -> None:
        """DateUpdate с датой равной today() считается валидной."""
        today = date.today()
        schema = DateUpdate(captured_on=today)
        assert schema.captured_on == today

    def test_date_update_with_past_date_is_valid(self) -> None:
        """DateUpdate с датой в прошлом считается валидной."""
        past_date = date(2020, 1, 1)
        schema = DateUpdate(captured_on=past_date)
        assert schema.captured_on == past_date

    def test_date_update_with_future_date_raises_validation_error(self) -> None:
        """DateUpdate с датой в будущем выбрасывает ValidationError."""
        from datetime import timedelta

        tomorrow = date.today() + timedelta(days=1)

        with pytest.raises(ValidationError) as exc_info:
            DateUpdate(captured_on=tomorrow)

        # Проверяем, что ошибка содержит сообщение о будущей дате
        assert "cannot be in the future" in str(exc_info.value).lower()
