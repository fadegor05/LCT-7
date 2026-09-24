"""ORM-модели методологии проверки оборудования на объекте строительства."""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    JSON,
    CheckConstraint,
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


class Obligation(StrEnum):
    """Обязательность требования по оборудованию."""

    NORMATIVE = "normative"
    LOGICAL = "logical"
    AUXILIARY = "auxiliary"


class EquipmentType(Base):
    """Тип оборудования (таблица equipment_types).

    Содержит справочную информацию о видах строительного оборудования.
    """

    __tablename__ = "equipment_types"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    synonyms: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)


class MethodologyRule(Base):
    """Правило методологии проверки оборудования (таблица methodology_rules).

    Привязано к объекту/этапу. Содержит информацию о проверяемости этапа.
    Может быть либо привязано к конкретному этапу (site_id + stage_id),
    либо быть базовым правилом (site_id=None + stage_key).
    """

    __tablename__ = "methodology_rules"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("sites.id", ondelete="CASCADE"), nullable=True, index=True
    )
    stage_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("schedule_stages.id", ondelete="CASCADE"), nullable=True, index=True
    )
    stage_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_verifiable: Mapped[bool] = mapped_column(default=True, nullable=False)
    unverifiable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "is_verifiable OR unverifiable_reason IS NOT NULL",
            name="ck_methodology_rules_reason",
        ),
        UniqueConstraint("site_id", "stage_id", name="uq_methodology_rules_site_stage"),
        CheckConstraint(
            "(site_id IS NULL AND stage_key IS NOT NULL) "
            "OR (site_id IS NOT NULL AND stage_id IS NOT NULL)",
            name="ck_methodology_rules_scope",
        ),
    )


class EquipmentSet(Base):
    """Набор требований по оборудованию (таблица equipment_sets).

    Принадлежит правилу методологии и содержит требования по конкретным типам оборудования.
    """

    __tablename__ = "equipment_sets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    rule_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("methodology_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class EquipmentRequirement(Base):
    """Требование по конкретному типу оборудования (таблица equipment_requirements).

    Входит в набор и задаёт минимальное количество, обязательность и источник требования.
    """

    __tablename__ = "equipment_requirements"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    set_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipment_sets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equipment_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipment_types.id"), nullable=False
    )
    min_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    obligation: Mapped[str] = mapped_column(String(16), nullable=False)
    gesn_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_note: Mapped[str | None] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        CheckConstraint("min_count >= 1", name="ck_equipment_requirements_min_count"),
        CheckConstraint(
            "gesn_code IS NOT NULL OR source_note IS NOT NULL",
            name="ck_equipment_requirements_source",
        ),
    )
