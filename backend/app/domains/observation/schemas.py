"""Pydantic-схемы для наблюдений."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ObservedEquipmentRead(BaseModel):
    """Чтение наблюдаемой техники."""

    model_config = ConfigDict(from_attributes=True)

    equipment_type_id: uuid.UUID
    equipment_code: str
    equipment_title: str
    count_min: int
    activity: str
    activity_basis: str | None = None
    confidence: str


class ObservationRead(BaseModel):
    """Чтение наблюдения."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    observed_on: date
    photo_count: int
    observability: str
    observability_notes: str | None
    recomputed_at: datetime
    equipment: list[ObservedEquipmentRead]
