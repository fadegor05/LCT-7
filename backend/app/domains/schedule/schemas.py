"""Pydantic-схемы для графика выполнения работ."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator


class StageRead(BaseModel):
    """Чтение этапа графика."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    position: int
    planned_start: date | None
    planned_end: date | None
    dates_source: str

    @field_validator("id", mode="before")
    @classmethod
    def convert_id(cls, v):
        if isinstance(v, uuid.UUID):
            return str(v)
        return v


class IssueRead(BaseModel):
    """Чтение ошибки при импорте."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    row_number: int
    raw_row: str
    reason: str

    @field_validator("id", mode="before")
    @classmethod
    def convert_id(cls, v):
        if isinstance(v, uuid.UUID):
            return str(v)
        return v


class ScheduleReport(BaseModel):
    """Отчёт об импорте графика."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    site_id: uuid.UUID
    source_filename: str
    imported_at: datetime
    rows_total: int
    rows_parsed: int
    stages_with_dates: int
    stages_without_dates: int
    parse_method: str
    stages: list[StageRead]
    issues: list[IssueRead]


class StageDatesUpdate(BaseModel):
    """Частичное обновление дат этапа."""

    planned_start: date | None = None
    planned_end: date | None = None
