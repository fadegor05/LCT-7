"""Pydantic-схемы для статусов этапов и отклонений."""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class StageStatusRead(BaseModel):
    """Статус этапа для чтения.

    stage_name и position берутся из ScheduleStage (не из самого StageStatus),
    поэтому эта схема собирается вручную в сервисе, не через from_attributes.
    """

    stage_id: uuid.UUID
    stage_name: str
    position: int
    status: str | None  # None = этап ещё не начался (нет строки в таблице)
    delay_days: int | None
    # delay_days — нижняя граница («от N дней»): этап не начат
    delay_open: bool = False
    # Сдвиг интервалом: None — граница неизвестна («до N», «от N»)
    delay_min: int | None = None
    delay_max: int | None = None
    confidence: str | None
    confidence_reason: str | None
    computed_at: datetime | None


class DeviationEvidenceRead(BaseModel):
    """Доказательство отклонения для чтения."""

    model_config = ConfigDict(from_attributes=True)

    photo_id: uuid.UUID
    detection_id: uuid.UUID | None
    # Подпись под снимком: «К-2 · свайное поле: Буровая установка»
    caption: str | None = None


class DeviationRead(BaseModel):
    """Отклонение для чтения."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    stage_id: uuid.UUID | None
    type: str
    is_hypothesis: bool
    severity: str
    confidence: str
    period_start: date
    period_end: date
    expected: str
    observed: str
    limits_text: str
    rule_id: uuid.UUID | None
    created_at: datetime
    # Заголовок строки, машина отклонения и возможная причина (отстающий этап)
    title: str | None = None
    equipment_type_id: uuid.UUID | None = None
    cause_stage_id: uuid.UUID | None = None


class DeviationDetailRead(DeviationRead):
    """Отклонение с доказательствами для чтения."""

    evidence: list[DeviationEvidenceRead]


class SiteSummaryRead(BaseModel):
    """Сводка статуса всей стройки.

    Эта схема не имеет соответствующей ORM-модели и всегда собирается вручную.
    """

    verdict: str  # "behind" | "no_deviations" | "insufficient_data"
    delay_days_min: int | None
    delay_days_max: int | None
    critical_count: int
    attention_count: int
    # Почему такой итог: этап с наибольшим отставанием или причина «Недостаточно данных».
    # None — объект ещё не пересчитывался
    reason: str | None = None
    stage_id: uuid.UUID | None = None
