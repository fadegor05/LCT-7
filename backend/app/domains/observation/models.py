"""ORM-модели наблюдений: сведённая за дату картина по стройке."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
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


class Observability(StrEnum):
    """Наблюдаемость стройки за дату."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Activity(StrEnum):
    """Активность техники в наблюдении."""

    WORKS = "works"
    IDLE = "idle"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    """Уверенность вывода."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Observation(Base):
    """Картина по стройке за одну дату (таблица observations)."""

    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    observed_on: Mapped[date] = mapped_column(Date(), nullable=False)
    photo_count: Mapped[int] = mapped_column(Integer, nullable=False)
    observability: Mapped[str] = mapped_column(String(16), nullable=False)
    observability_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recomputed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("site_id", "observed_on", name="uq_observations_site_date"),)


class ObservedEquipment(Base):
    """Техника, зафиксированная в наблюдении (таблица observed_equipment)."""

    __tablename__ = "observed_equipment"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("observations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equipment_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipment_types.id"), nullable=False
    )
    count_min: Mapped[int] = mapped_column(Integer, nullable=False)
    activity: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "observation_id", "equipment_type_id", name="uq_observed_equipment_obs_type"
        ),
        CheckConstraint("count_min >= 1", name="ck_observed_equipment_count_min"),
    )
