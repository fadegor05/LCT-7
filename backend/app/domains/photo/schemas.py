"""Pydantic-схемы для фотографий и детекций."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


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
    # Центр нижней кромки в рабочей зоне камеры снимка; None — камеры или зоны нет
    in_zone: bool | None = None


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
    camera_id: uuid.UUID | None = None
    # Местное время съёмки; дата-подсказка для ручного ввода; проверка серии штампов
    captured_at: datetime | None = None
    date_hint: date | None = None
    time_check: str | None = None
    # Сводка кадра для подписи в ленте (clean-mvp): какая техника на нём, есть ли машина
    # за контуром зоны камеры, служит ли он снимком-доказательством отклонения
    machines: list[str] = []
    out_of_zone: bool = False
    evidence: bool = False


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
    """Обновление даты съёмки фотографии.

    Дату из будущего отклоняет PhotoService.set_date: там русский текст для
    интерфейса. Проверка в схеме отдавала бы пользователю сообщение pydantic.
    """

    captured_on: date


class DetectBacklogReport(BaseModel):
    """Отчёт о детекции заблокированных фотографий."""

    processed: int
    done: int
    failed: int
    skipped: int
