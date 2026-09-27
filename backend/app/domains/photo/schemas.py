"""Pydantic-схемы для фотографий и детекций."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator


class DetectionRead(BaseModel):
    """Чтение детекции оборудования на фотографии."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    equipment_type_id: uuid.UUID
    equipment_code: str
    equipment_title: str
    bbox: list[float]
    score: float
    model_version: str


class PhotoRead(BaseModel):
    """Чтение фотографии."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    original_name: str
    width: int
    height: int
    captured_on: date | None
    date_source: str | None
    processing_status: str
    uploaded_at: datetime


class PhotoDetail(PhotoRead):
    """Чтение фотографии с детекциями."""

    detections: list[DetectionRead]


class UploadItem(BaseModel):
    """Результат загрузки одного файла."""

    filename: str
    photo: PhotoRead | None = None
    error: str | None = None


class UploadReport(BaseModel):
    """Отчёт о загрузке фотографий."""

    items: list[UploadItem]
    uploaded: int
    failed: int


class DateUpdate(BaseModel):
    """Обновление даты съёмки фотографии."""

    captured_on: date

    @field_validator("captured_on")
    @classmethod
    def reject_future_date(cls, v: date) -> date:
        """Отклонить дату в будущем."""
        from datetime import date as date_cls

        today = date_cls.today()
        if v > today:
            raise ValueError("captured_on cannot be in the future")
        return v


class DetectBacklogReport(BaseModel):
    """Отчёт о детекции заблокированных фотографий."""

    processed: int
    done: int
    failed: int
    skipped: int
