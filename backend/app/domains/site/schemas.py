"""Pydantic-схемы объектов строительства."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ObjectType = Literal["housing", "education", "health", "other"]


def _check_workdays(value: list[int] | None) -> list[int] | None:
    """Дни недели 0–6 без повторов, хотя бы один; храним по порядку."""
    if value is None:
        return None
    if not value or any(d not in range(7) for d in value) or len(set(value)) != len(value):
        raise ValueError("рабочие дни — числа 0–6 (пн–вс) без повторов, хотя бы один день")
    return sorted(value)


class SiteCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    object_type: ObjectType = "other"
    workdays: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])

    _workdays = field_validator("workdays")(_check_workdays)


class SiteUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=255)
    address: str | None = Field(default=None, max_length=500)
    object_type: ObjectType | None = None
    workdays: list[int] | None = None

    _workdays = field_validator("workdays")(_check_workdays)


class SiteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str | None
    object_type: str = "other"
    workdays: list[int] = [0, 1, 2, 3, 4]
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
