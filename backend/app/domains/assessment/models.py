"""ORM-модели расчёта статусов этапов и отклонений от плана."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class StageStatusValue(StrEnum):
    """Статус выполнения этапа работ."""

    AHEAD = "ahead"
    ON_TRACK = "on_track"
    BEHIND = "behind"
    NOT_STARTED = "not_started"
    NOT_OBSERVED = "not_observed"
    NOT_CHECKED = "not_checked"


class DeviationType(StrEnum):
    """Тип обнаруженного отклонения от плана."""

    MISSING_EQUIPMENT = "missing_equipment"
    MISSING_LOGICAL_EQUIPMENT = "missing_logical_equipment"
    STAGE_MISMATCH = "stage_mismatch"
    STALE_DATA = "stale_data"
    IDLE = "idle"
    EXTRA_EQUIPMENT = "extra_equipment"
    OUT_OF_ZONE = "out_of_zone"
    NO_PROGRESS = "no_progress"
    BEHIND_SCHEDULE = "behind_schedule"
    # Маркер этапа виден, а машины его комплекта нет на последних датах (clean-mvp)
    INCOMPLETE_KIT = "incomplete_kit"


class Severity(StrEnum):
    """Уровень серьёзности отклонения."""

    CRITICAL = "critical"
    ATTENTION = "attention"


class StageStatus(Base):
    """Рассчитанный статус этапа работ (таблица stage_statuses)."""

    __tablename__ = "stage_statuses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    stage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("schedule_stages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    delay_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # delay_days — нижняя граница («от N дней»): этап не начат, конец сдвига неизвестен
    delay_open: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    # Сдвиг интервалом («14–74 дня», «до 63»): None — граница неизвестна
    delay_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delay_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Факт по маркеру и маркеры этапа (названия техники) — для «Этапов» на обзоре
    start_fact: Mapped[date | None] = mapped_column(Date(), nullable=True)
    marker_names: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class SiteSummary(Base):
    """Итог по объекту из последнего пересчёта (таблица site_summaries).

    Считается вместе со статусами этапов, по той же опорной дате: итог на чтении из одних
    статусов не видел устаревших данных и наблюдаемости последнего дня.
    """

    __tablename__ = "site_summaries"

    site_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(String(24), nullable=False)
    delay_days_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delay_days_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("schedule_stages.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    # Опорная дата расчёта: «данные на» на экранах
    as_of: Mapped[date | None] = mapped_column(Date(), nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Deviation(Base):
    """Обнаруженное отклонение от плана/методологии/наблюдений (таблица deviations)."""

    __tablename__ = "deviations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("schedule_stages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    is_hypothesis: Mapped[bool] = mapped_column(nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    period_start: Mapped[date] = mapped_column(Date(), nullable=False)
    period_end: Mapped[date] = mapped_column(Date(), nullable=False)
    expected: Mapped[str] = mapped_column(Text, nullable=False)
    observed: Mapped[str] = mapped_column(Text, nullable=False)
    limits_text: Mapped[str] = mapped_column(Text, nullable=False)
    rule_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("methodology_rules.id", ondelete="SET NULL"), nullable=True
    )
    # Заголовок строки списка («Буровая установка: техника этапа «Сваи»»)
    title: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Машина отклонения — по её рамкам выбраны доказательства
    equipment_type_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    # Возможная причина: отстающий этап, чья техника ещё на площадке
    cause_stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("schedule_stages.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class DeviationEvidence(Base):
    """Доказательство отклонения: фотография и детекция (таблица deviation_evidence)."""

    __tablename__ = "deviation_evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    deviation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("deviations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    photo_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("photos.id", ondelete="CASCADE"), nullable=False
    )
    detection_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("detections.id", ondelete="SET NULL"), nullable=True
    )
    # Подпись под снимком: «К-2 · свайное поле: Буровая установка»
    caption: Mapped[str | None] = mapped_column(String(300), nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "deviation_id",
            "photo_id",
            "detection_id",
            name="uq_deviation_evidence_dev_photo_detection",
        ),
    )


class StatusBasis(Base):
    """Наблюдение, послужившее основанием для статуса этапа (таблица status_basis)."""

    __tablename__ = "status_basis"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    status_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("stage_statuses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("observations.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("status_id", "observation_id", name="uq_status_basis_status_observation"),
    )
