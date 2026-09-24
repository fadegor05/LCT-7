"""Pydantic v2 схемы для методологии проверки оборудования."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domains.methodology.models import Obligation


class EquipmentTypeRead(BaseModel):
    """Чтение типа оборудования."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    code: str
    title: str
    synonyms: list[str]


class RequirementIn(BaseModel):
    """Входные данные для требования по оборудованию.

    Требует либо gesn_code, либо source_note (но не оба пусты).
    """

    equipment_type_id: uuid.UUID
    min_count: int = Field(1, ge=1)
    obligation: Obligation
    gesn_code: str | None = Field(None, max_length=64)
    source_note: str | None = Field(None, max_length=500)

    @field_validator("gesn_code", "source_note", mode="before")
    @classmethod
    def normalize_empty_strings(cls, v):
        """Нормализовать пустые/только пробелы строки в None."""
        if isinstance(v, str):
            v_stripped = v.strip()
            return v_stripped if v_stripped else None
        return v

    @model_validator(mode="after")
    def check_source_provided(self):
        """Убедиться, что либо gesn_code, либо source_note непусты."""
        if not self.gesn_code and not self.source_note:
            raise ValueError(
                "Either gesn_code or source_note must be provided "
                "(not both empty or whitespace-only)"
            )
        return self


class SetWrite(BaseModel):
    """Запись набора требований (для создания и замены)."""

    requirements: list[RequirementIn] = Field(min_length=1)


class RuleUpdate(BaseModel):
    """Обновление правила проверяемости."""

    is_verifiable: bool
    unverifiable_reason: str | None = None

    @model_validator(mode="after")
    def validate_unverifiable_reason(self):
        """Если is_verifiable=False, reason должна быть непуста. Если True, очистить reason."""
        if not self.is_verifiable:  # is_verifiable is False
            if not self.unverifiable_reason or not self.unverifiable_reason.strip():
                raise ValueError(
                    "When is_verifiable is False, unverifiable_reason must be "
                    "non-empty (and not only whitespace)"
                )
        else:  # is_verifiable is True
            # Clear reason when is_verifiable is True
            self.unverifiable_reason = None
        return self


class RequirementRead(BaseModel):
    """Чтение требования по оборудованию."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    equipment_type: EquipmentTypeRead
    min_count: int
    obligation: Obligation
    gesn_code: str | None
    source_note: str | None


class SetRead(BaseModel):
    """Чтение набора требований."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    requirements: list[RequirementRead]


class RuleRead(BaseModel):
    """Чтение правила методологии."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage_id: uuid.UUID | None
    stage_name: str | None
    is_verifiable: bool
    unverifiable_reason: str | None
    updated_at: datetime
    sets: list[SetRead]
