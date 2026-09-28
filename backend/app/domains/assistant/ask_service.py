"""Оркестрация вопроса к ассистенту с проверками, лимитом и маппингом ошибок."""

from __future__ import annotations

import json
import logging
import math
import re
import time
import uuid
from typing import TYPE_CHECKING

from app.adapters.ml.assistant import AssistantClient, AssistantError
from app.core.rate_limit import SlidingWindowRateLimiter
from app.core.settings import Settings
from app.domains.assistant.report import SITE_LABEL
from app.domains.assistant.schemas import AssistantAnswerRead, AssistantStatusRead, StageRefRead
from app.domains.site.guard import SiteAccessGuard
from app.plugins.exceptions import AppError

if TYPE_CHECKING:
    from app.domains.assistant.service import AssistantReportService

logger = logging.getLogger(__name__)


def referenced_stages(answer: str, stage_ids: dict[int, uuid.UUID]) -> list[StageRefRead]:
    """Извлечь ссылки на этапы из ответа.

    Использует regex для парсинга "этап N", "этапа N", "этап №N" и т.д.
    Возвращает только этапы, присутствующие в stage_ids, в порядке первого появления,
    без дубликатов.

    Args:
        answer: Текст ответа ассистента
        stage_ids: Маппинг stage_no -> stage_id

    Returns:
        Список StageRefRead в порядке первого появления
    """
    # Regex для поиска "этап N", "этапа N", "этап №N" и т.д.
    # (?<!\w) — не предшествует буква (word boundary)
    # этап[а-яё]* — "этап", "этапа", "этапе", "этапов", "этапу" и т.д.
    # \s*№?\s* — опциональный номер с пробелами вокруг
    # (\d{1,4}) — 1-4 цифры (номер этапа)
    # (?!\d) — не следует цифра (word boundary для чисел)
    pattern = r"(?<!\w)этап[а-яё]*\s*№?\s*(\d{1,4})(?!\d)"

    matches = re.finditer(pattern, answer, re.IGNORECASE)

    seen = set()
    result = []

    for match in matches:
        stage_no = int(match.group(1))

        # Пропускаем дубликаты
        if stage_no in seen:
            continue

        # Пропускаем этапы, не присутствующие в stage_ids
        if stage_no not in stage_ids:
            continue

        seen.add(stage_no)
        result.append(StageRefRead(ref=f"этап {stage_no}", stage_id=stage_ids[stage_no]))

    return result


class AssistantService:
    """Оркестрация вопроса с проверками доступа, лимита, размера и маппингом ошибок."""

    def __init__(
        self,
        reports: AssistantReportService,
        client: AssistantClient,
        limiter: SlidingWindowRateLimiter,
        guard: SiteAccessGuard,
        settings: Settings,
    ) -> None:
        """Инициализировать сервис.

        Args:
            reports: Сервис для сборки отчёта
            client: Клиент ассистента
            limiter: Rate limiter
            guard: Гвард доступа к сайтам
            settings: Глобальные настройки
        """
        self._reports = reports
        self._client = client
        self._limiter = limiter
        self._guard = guard
        self._settings = settings

    async def status(self) -> AssistantStatusRead:
        """Получить статус доступности ассистента.

        Returns:
            AssistantStatusRead с enabled=True если ассистент доступен
        """
        enabled = await self._client.available()
        return AssistantStatusRead(enabled=enabled)

    async def ask(self, site_id: uuid.UUID, question: str) -> AssistantAnswerRead:
        """Задать вопрос по отчёту с полной оркестрацией проверок.

        Порядок проверок (дёшево и не потребляющие квоту сначала):
        1. guard.require(site_id) → 404 если чужая площадка
        2. client.available() → 503 если не доступен (НЕ потребляет квоту)
        3. limiter.hit() → 429 если превышен лимит
        4. reports.build() → пропускает AppError без изменений
        5. size check → 413 если отчёт слишком большой
        6. client.ask() → маппирует AssistantError в AppError

        Args:
            site_id: ID площадки
            question: Вопрос пользователя

        Returns:
            AssistantAnswerRead с ответом и ссылками на этапы

        Raises:
            AppError: 404 (чужая площадка/нет графика), 503 (ассистент недоступен),
                      429 (превышен лимит), 413 (отчёт слишком большой),
                      или другие ошибки от ассистента
        """
        start_time = time.monotonic()
        duration_ms = None

        try:
            # 1. Проверка доступа и получение site.owner_id
            site = await self._guard.require(site_id)

            # 2. Проверка доступности ассистента (НЕ потребляет квоту)
            if not await self._client.available():
                raise AppError(
                    "Ассистент недоступен",
                    status_code=503,
                    code="assistant_unavailable",
                )

            # 3. Проверка лимита частоты
            wait_s = self._limiter.hit(str(site.owner_id))
            if wait_s is not None:
                wait_ceil = math.ceil(wait_s)
                raise AppError(
                    f"Слишком много вопросов. Повторите через {wait_ceil} с.",
                    status_code=429,
                    code="rate_limited",
                )

            # 4. Сборка отчёта
            built_report = await self._reports.build(site_id)
            report = built_report.report
            stage_ids = built_report.stage_ids

            # 5. Проверка размера отчёта
            report_json = json.dumps(report, ensure_ascii=False)
            report_size_bytes = len(report_json.encode("utf-8"))
            max_size_bytes = self._settings.assistant.max_report_kb * 1024

            if report_size_bytes > max_size_bytes:
                raise AppError(
                    "Отчёт слишком велик для ассистента",
                    status_code=413,
                    code="report_too_large",
                )

            # 6. Вызов ассистента
            try:
                answer_data = await self._client.ask(question, report, site_id=SITE_LABEL)
            except AssistantError as e:
                raise AppError(e.message, e.status_code, code=e.code) from e

            # Парсим упомянутые этапы из ответа
            stages = referenced_stages(answer_data.answer, stage_ids)

            # Логируем успешный запрос
            duration_ms = int((time.monotonic() - start_time) * 1000)
            logger.info(
                "assistant.ask site=%s q_len=%d a_len=%d verified=%s ms=%d",
                site_id,
                len(question),
                len(answer_data.answer),
                answer_data.verified,
                duration_ms,
            )

            return AssistantAnswerRead(
                answer=answer_data.answer,
                verified=answer_data.verified,
                numbers_not_in_report=answer_data.numbers_not_in_report,
                numbers_of_other_site=answer_data.numbers_of_other_site,
                limits=answer_data.limits,
                site_label=SITE_LABEL,
                stages=stages,
            )

        except AppError as e:
            # Логируем ошибку
            logger.warning(
                "assistant.ask site=%s status_code=%d code=%s",
                site_id,
                e.status_code,
                e.code,
            )
            raise
