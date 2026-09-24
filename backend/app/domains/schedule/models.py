"""ORM-модели графика выполнения работ на объекте строительства."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DatesSource(StrEnum):
    """Источник дат этапов графика."""

    FILE = "file"
    MANUAL = "manual"


class Schedule(Base):
    """График выполнения работ (таблица schedules).

    Привязан к объекту строительства (site_id) уникально.
    Хранит метаинформацию об импорте файла графика.
    """

    __tablename__ = "schedules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    rows_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rows_parsed: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ScheduleStage(Base):
    """Этап графика выполнения работ (таблица schedule_stages).

    Принадлежит графику (schedule_id). Содержит плановые даты начала и окончания работ.
    """

    __tablename__ = "schedule_stages"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    planned_start: Mapped[date | None] = mapped_column(Date(), nullable=True)
    planned_end: Mapped[date | None] = mapped_column(Date(), nullable=True)
    dates_source: Mapped[str] = mapped_column(
        String(16), default=DatesSource.FILE.value, nullable=False
    )


class ScheduleImportIssue(Base):
    """Ошибка при импорте графика (таблица schedule_import_issues).

    Хранит строки с ошибками при разборе файла графика.
    """

    __tablename__ = "schedule_import_issues"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_row: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
