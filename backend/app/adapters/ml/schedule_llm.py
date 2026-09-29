"""HTTP-клиент LLM-разбора плана стройки.

Адаптер к ML-сервису (`POST /parse-schedule`): ему отдают «сырую» таблицу файла
(номер строки + ячейки как текст), он возвращает строки графика. Промпт и
проверка ответа модели живут на стороне ML (`ml/tools/schedule_llm.py`).

Без ретраев: каждый вызов — платный LLM call. Ошибки — те же, что у ассистента
(`AssistantError` и потомки): у них тот же ML-сервис, тот же провайдер модели.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol

import httpx
from pydantic import BaseModel

from app.adapters.ml.assistant import (
    AssistantBadRequest,
    AssistantTimeout,
    AssistantUnavailable,
)
from app.adapters.ml.http import normalize_base_url
from app.core.settings import AssistantSettings

logger = logging.getLogger(__name__)

# Строка таблицы для LLM: (номер строки в файле, ячейки как текст)
GridRow = tuple[int, Sequence[str]]


@dataclass(frozen=True)
class LlmScheduleRow:
    """Работа, которую модель нашла в таблице (и проверка подтвердила)."""

    row: int
    name: str
    start: date | None
    end: date | None


@dataclass(frozen=True)
class LlmScheduleIssue:
    """Строка, которую модель выдала, но проверка не пропустила."""

    row: int
    raw: str
    reason: str


@dataclass(frozen=True)
class LlmScheduleResult:
    rows: list[LlmScheduleRow]
    issues: list[LlmScheduleIssue]


class _RowSchema(BaseModel):
    row: int
    name: str
    start: date | None = None
    end: date | None = None

    model_config = {"extra": "ignore"}


class _IssueSchema(BaseModel):
    row: int
    raw: str = ""
    reason: str

    model_config = {"extra": "ignore"}


class _ResultSchema(BaseModel):
    rows: list[_RowSchema]
    issues: list[_IssueSchema] = []

    model_config = {"extra": "ignore"}


class ScheduleLlmClient(Protocol):
    """Клиент LLM-разбора плана: HTTP либо заглушка."""

    async def parse(self, rows: Sequence[GridRow]) -> LlmScheduleResult:
        """Разобрать таблицу моделью.

        Raises:
            AssistantError: при ошибке сервиса или если LLM не настроена
        """
        ...


class HttpScheduleLlmClient:
    """Клиент ML `POST /parse-schedule`."""

    def __init__(
        self, base_url: str, client: httpx.AsyncClient, settings: AssistantSettings
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.client = client
        self.settings = settings

    async def parse(self, rows: Sequence[GridRow]) -> LlmScheduleResult:
        url = f"{self.base_url}/parse-schedule"
        timeout = httpx.Timeout(
            self.settings.parse_timeout_s, connect=self.settings.connect_timeout_s
        )
        payload = {"rows": [{"row": number, "cells": list(cells)} for number, cells in rows]}

        try:
            response = await self.client.post(url, json=payload, timeout=timeout)
        except httpx.ReadTimeout as e:
            raise AssistantTimeout("Модель не успела разобрать файл. Повторите позже.") from e
        except httpx.TimeoutException as e:
            raise AssistantUnavailable(_UNAVAILABLE) from e
        except httpx.TransportError as e:
            raise AssistantUnavailable(_UNAVAILABLE) from e

        if response.status_code == 200:
            try:
                parsed = _ResultSchema(**response.json())
            except Exception as e:
                raise AssistantUnavailable("LLM-разбор вернул неожиданный ответ") from e
            return LlmScheduleResult(
                rows=[LlmScheduleRow(r.row, r.name, r.start, r.end) for r in parsed.rows],
                issues=[LlmScheduleIssue(i.row, i.raw, i.reason) for i in parsed.issues],
            )

        logger.warning(
            "schedule-llm: status=%d detail=%s", response.status_code, str(response.text)[:200]
        )
        if response.status_code == 413:
            raise AssistantBadRequest(
                "Таблица слишком большая для LLM-разбора",
                status_code=413,
                code="schedule_llm_too_large",
            )
        if response.status_code == 504:
            raise AssistantTimeout("Модель не ответила. Повторите позже.")
        raise AssistantUnavailable(_UNAVAILABLE)


_UNAVAILABLE = "LLM-разбор временно недоступен"


class NullScheduleLlmClient:
    """Заглушка: ML-сервис не настроен."""

    async def parse(self, rows: Sequence[GridRow]) -> LlmScheduleResult:
        raise AssistantUnavailable("LLM-разбор не настроен")
