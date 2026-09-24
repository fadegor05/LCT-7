"""ORM-модели фотографий и детекций оборудования на объекте строительства."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DateSource(StrEnum):
    """Источник даты съёмки фотографии."""

    CHANNEL = "channel"
    METADATA = "metadata"
    STAMP = "stamp"
    NEIGHBOURS = "neighbours"
    MANUAL = "manual"


class ProcessingStatus(StrEnum):
    """Статус обработки фотографии."""

    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class Photo(Base):
    """Фотография с объекта строительства (таблица photos).

    Содержит метаинформацию о фотографии, дату съёмки и статус обработки.
    Привязана к объекту строительства (site_id).
    """

    __tablename__ = "photos"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    original_name: Mapped[str] = mapped_column(String(255), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    captured_on: Mapped[date | None] = mapped_column(Date(), nullable=True)
    date_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(16), default=ProcessingStatus.PENDING.value, nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_photos_site_id_captured_on", "site_id", "captured_on"),)


class Detection(Base):
    """Детекция оборудования на фотографии (таблица detections).

    Результат работы модели детекции — содержит информацию о найденном оборудовании
    на фотографии: его тип, расположение (bbox) и уверенность модели.
    """

    __tablename__ = "detections"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    photo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equipment_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipment_types.id"), nullable=False, index=True
    )
    bbox: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
