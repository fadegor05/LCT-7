"""HTTP-клиент для чтения даты со штампа через ML-сервис (LCT-13).

Контракт: POST {base}/stamp, multipart/form-data, поле `file`.
Ответ: {"date": "2024-04-24" | null, "text": "...", "roi": "right"|"left"|null}.
Ошибки как у /detect: 400/413/422 не повторяются, 503 — retry с backoff.
"""

import asyncio
import logging
from datetime import date

import httpx
from pydantic import BaseModel

from app.adapters.ml.http import normalize_base_url
from app.core.settings import DetectorSettings

logger = logging.getLogger(__name__)


class _StampSchema(BaseModel):
    date: str | None = None
    text: str | None = None
    roi: str | None = None

    model_config = {"extra": "ignore"}


class HttpStampReader:
    """StampOcr через HTTP ML-сервис. Тот же base_url, что у детектора."""

    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient,
        settings: DetectorSettings,
        sleep=asyncio.sleep,
    ) -> None:
        self.base_url = normalize_base_url(base_url)
        self.client = client
        self.settings = settings
        self._sleep = sleep
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)

    async def _wait_before_retry(self, attempt: int, spent: float) -> float | None:
        backoff_index = min(attempt - 1, len(self.settings.retry_backoff_s) - 1)
        sleep_time = self.settings.retry_backoff_s[backoff_index]
        if spent + sleep_time <= self.settings.retry_budget_s:
            await self._sleep(sleep_time)
            return spent + sleep_time
        return None

    async def read_date(self, content: bytes) -> date | None:
        url = f"{self.base_url}/stamp"
        timeout = httpx.Timeout(self.settings.timeout_s, connect=self.settings.connect_timeout_s)

        retry_503_count = 0
        retry_other_count = 0
        total_sleep = 0.0

        while True:
            try:
                async with self._semaphore:
                    response = await self.client.post(
                        url,
                        files={"file": ("upload", content, None)},
                        timeout=timeout,
                    )

                if response.status_code == 503:
                    if retry_503_count < self.settings.retry_503:
                        retry_503_count += 1
                        new_spent = await self._wait_before_retry(retry_503_count, total_sleep)
                        if new_spent is not None:
                            total_sleep = new_spent
                            continue
                    logger.warning("Stamp service 503, retries exhausted")
                    return None

                if 400 <= response.status_code < 500:
                    logger.warning("Stamp service HTTP %d, no retry", response.status_code)
                    return None

                if response.status_code >= 500:
                    if retry_other_count < self.settings.retry_other:
                        retry_other_count += 1
                        new_spent = await self._wait_before_retry(retry_other_count, total_sleep)
                        if new_spent is not None:
                            total_sleep = new_spent
                            continue
                    logger.warning("Stamp service HTTP %d, retries exhausted", response.status_code)
                    return None

                if response.status_code == 200:
                    try:
                        data = response.json()
                        parsed = _StampSchema(**data)
                    except Exception:
                        logger.warning("Stamp service: invalid response body")
                        return None
                    if not parsed.date:
                        return None
                    try:
                        return date.fromisoformat(parsed.date)
                    except ValueError:
                        logger.warning("Stamp service returned unparseable date: %r", parsed.date)
                        return None

                logger.warning("Stamp service unexpected HTTP %d", response.status_code)
                return None

            except httpx.TimeoutException:
                if retry_other_count < self.settings.retry_other:
                    retry_other_count += 1
                    new_spent = await self._wait_before_retry(retry_other_count, total_sleep)
                    if new_spent is not None:
                        total_sleep = new_spent
                        continue
                logger.warning("Stamp service timeout, retries exhausted")
                return None
            except httpx.TransportError:
                if retry_other_count < self.settings.retry_other:
                    retry_other_count += 1
                    new_spent = await self._wait_before_retry(retry_other_count, total_sleep)
                    if new_spent is not None:
                        total_sleep = new_spent
                        continue
                logger.warning("Stamp service connection error, retries exhausted")
                return None
