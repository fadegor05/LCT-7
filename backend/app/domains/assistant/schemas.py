"""Схемы для API ассистента."""

import uuid
from typing import Annotated

from pydantic import BaseModel, StringConstraints


class AskRequest(BaseModel):
    """Запрос к ассистенту."""

    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]


class StageRefRead(BaseModel):
    """Ссылка на этап."""

    ref: str
    stage_id: uuid.UUID


class AssistantAnswerRead(BaseModel):
    """Ответ ассистента с метаинформацией."""

    answer: str
    verified: bool
    numbers_not_in_report: list[str]
    numbers_of_other_site: list[str]
    limits: str
    site_label: str
    stages: list[StageRefRead]


class AssistantStatusRead(BaseModel):
    """Статус доступности ассистента."""

    enabled: bool
