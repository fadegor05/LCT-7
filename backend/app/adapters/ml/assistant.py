"""HTTP-клиент для ML-ассистента.

Модуль определяет HttpAssistantClient — адаптер к ML HTTP-сервису для обработки
вопросов по отчётам. Без ретраев: каждый вызов — платный LLM call.
"""

import logging
import time
from dataclasses import dataclass
from typing import Protocol

import httpx
from pydantic import BaseModel

from app.adapters.ml.http import normalize_base_url
from app.core.settings import AssistantSettings

logger = logging.getLogger(__name__)

# Таймаут для GET /meta — проверка доступности не должна зависать на 130s
META_TIMEOUT_S: float = 5.0


@dataclass(frozen=True)
class AssistantAnswer:
    """Ответ ассистента на вопрос по отчёту.

    Attributes:
        answer: Текст ответа
        verified: Был ли ответ верифицирован
        numbers_not_in_report: Номера, упомянутые но не в отчёте
        numbers_of_other_site: Номера из других площадок
        limits: Ограничения на ответ (например, ограничение на токены)
    """

    answer: str
    verified: bool
    numbers_not_in_report: list[str]
    numbers_of_other_site: list[str]
    limits: str


class AssistantError(Exception):
    """Ошибка при работе с ассистентом.

    Attributes:
        message: Сообщение об ошибке (не содержит секретов)
        status_code: HTTP статус код для ответа
        code: Код ошибки для фронтенда (опционально)
    """

    def __init__(
        self, message: str, status_code: int = 400, code: str = "assistant_bad_request"
    ) -> None:
        """Инициализировать ошибку ассистента.

        Args:
            message: Сообщение об ошибке
            status_code: HTTP статус код
            code: Код ошибки
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code


class AssistantUnavailable(AssistantError):
    """Ассистент недоступен (503)."""

    def __init__(self, message: str = "Ассистент временно недоступен") -> None:
        super().__init__(message, status_code=503, code="assistant_unavailable")


class AssistantTimeout(AssistantError):
    """Таймаут ответа от ассистента (504)."""

    def __init__(self, message: str = "Модель не ответила. Повторите вопрос позже.") -> None:
        super().__init__(message, status_code=504, code="assistant_timeout")


class AssistantBadRequest(AssistantError):
    """Некорректный запрос (400 или 422 с out_of_scope)."""

    def __init__(
        self,
        message: str = "Ассистент не принял запрос",
        status_code: int = 400,
        code: str = "assistant_bad_request",
    ) -> None:
        super().__init__(message, status_code=status_code, code=code)


class _AssistantAnswerSchema(BaseModel):
    """Pydantic-схема ответа ML-сервиса."""

    answer: str
    verified: bool
    numbers_not_in_report: list[str]
    numbers_of_other_site: list[str]
    limits: str

    model_config = {"extra": "ignore"}


class AssistantClient(Protocol):
    """Протокол клиента ассистента.

    Ассистент может быть отключен (Null) либо работать через HTTP.
    """

    async def ask(self, question: str, report: dict, site_id: str | None = None) -> AssistantAnswer:
        """Задать вопрос по отчёту.

        Args:
            question: Вопрос пользователя
            report: Отчёт (dict, будет сериализован в JSON)
            site_id: ID площадки (опционально, обычно site_label)

        Returns:
            AssistantAnswer с ответом

        Raises:
            AssistantError: При ошибке сервиса
        """
        ...

    async def available(self) -> bool:
        """Проверить, доступен ли ассистент.

        Вызывает GET /meta. Кэшируется.

        Returns:
            True если ассистент доступен, False иначе
        """
        ...


class HttpAssistantClient:
    """Клиент для HTTP ML-ассистента.

    Отправляет JSON запрос с вопросом и отчётом и парсит ответ.
    БЕЗ ретраев: каждый вызов — платный LLM call.

    Args:
        base_url: Базовый URL ML-сервиса (напр. http://ml:8000)
        client: httpx.AsyncClient для отправки запросов
        settings: AssistantSettings с параметрами timeout
        clock: Функция получения текущего времени (для тестов)
    """

    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient,
        settings: AssistantSettings,
        clock=None,
    ):
        """Инициализировать HttpAssistantClient.

        Args:
            base_url: Базовый URL
            client: httpx.AsyncClient
            settings: AssistantSettings
            clock: Функция времени (по умолчанию time.monotonic)
        """
        self.base_url = normalize_base_url(base_url)
        self.client = client
        self.settings = settings
        self._clock = clock or time.monotonic
        self._available_cache: bool | None = None
        self._available_cache_time: float | None = None
        self._available_cache_is_success: bool = False

    async def ask(self, question: str, report: dict, site_id: str | None = None) -> AssistantAnswer:
        """Задать вопрос ассистенту без ретраев.

        Args:
            question: Вопрос
            report: Отчёт (dict)
            site_id: ID площадки (обычно site_label)

        Returns:
            AssistantAnswer с ответом

        Raises:
            AssistantError: При ошибке
        """
        url = f"{self.base_url}/ask"
        timeout = httpx.Timeout(self.settings.timeout_s, connect=self.settings.connect_timeout_s)

        try:
            response = await self.client.post(
                url,
                json={"question": question, "report": report, "site_id": site_id},
                timeout=timeout,
            )

            # Успешный ответ
            if response.status_code == 200:
                try:
                    data = response.json()
                except Exception as e:
                    raise AssistantUnavailable("Ассистент вернул неожиданный ответ") from e

                try:
                    parsed = _AssistantAnswerSchema(**data)
                except Exception as e:
                    raise AssistantUnavailable("Ассистент вернул неожиданный ответ") from e

                return AssistantAnswer(
                    answer=parsed.answer,
                    verified=parsed.verified,
                    numbers_not_in_report=parsed.numbers_not_in_report,
                    numbers_of_other_site=parsed.numbers_of_other_site,
                    limits=parsed.limits,
                )

            # 422 out_of_scope - специальный случай
            if response.status_code == 422:
                try:
                    data = response.json()
                    if isinstance(data.get("detail"), dict):
                        detail = data["detail"]
                        if detail.get("code") == "out_of_scope":
                            message = str(detail.get("message", ""))[:300]
                            raise AssistantBadRequest(
                                message=message, status_code=422, code="out_of_scope"
                            )
                except AssistantBadRequest:
                    raise
                except Exception:
                    pass

                # Не out_of_scope - validation error
                raise AssistantBadRequest("Ассистент не принял запрос")

            # 504 - таймаут
            if response.status_code == 504:
                raise AssistantTimeout()

            # 5xx - недоступен (кроме 504)
            if response.status_code >= 500:
                logger.warning(
                    "assistant: status=%d detail=%s",
                    response.status_code,
                    str(response.text)[:200],
                )
                raise AssistantUnavailable()

            # 4xx (кроме 422) - bad request
            if 400 <= response.status_code < 500:
                logger.warning(
                    "assistant: status=%d detail=%s",
                    response.status_code,
                    str(response.text)[:200],
                )
                raise AssistantBadRequest("Ассистент не принял запрос")

            # Неожиданный статус
            raise AssistantUnavailable()

        except AssistantError:
            raise
        except httpx.ReadTimeout as e:
            raise AssistantTimeout() from e
        except httpx.ConnectTimeout as e:
            raise AssistantUnavailable() from e
        except httpx.PoolTimeout as e:
            raise AssistantUnavailable() from e
        except httpx.TimeoutException as e:
            # Это не ConnectTimeout и не ReadTimeout
            raise AssistantTimeout() from e
        except httpx.ConnectError as e:
            raise AssistantUnavailable() from e
        except httpx.TransportError as e:
            raise AssistantUnavailable() from e

    def _remember(self, now: float, result: bool) -> bool:
        """Запомнить результат доступности в кэш и вернуть его.

        Args:
            now: Текущее время
            result: Результат проверки доступности

        Returns:
            Переданный результат
        """
        self._available_cache = result
        self._available_cache_time = now
        self._available_cache_is_success = result
        return result

    async def available(self) -> bool:
        """Проверить доступность ассистента.

        Вызывает GET /meta, кэширует результат.
        True кэшируется на status_cache_s, False на status_retry_s.

        Returns:
            True если доступен, False иначе
        """
        now = self._clock()

        # Проверяем кэш
        if self._available_cache is not None and self._available_cache_time is not None:
            if self._available_cache_is_success:
                # Success cache
                ttl = self.settings.status_cache_s
            else:
                # Failure cache
                ttl = self.settings.status_retry_s

            if now - self._available_cache_time < ttl:
                return self._available_cache

        # Кэш устарел или пуст, делаем запрос
        try:
            url = f"{self.base_url}/meta"
            timeout = httpx.Timeout(META_TIMEOUT_S, connect=self.settings.connect_timeout_s)
            response = await self.client.get(url, timeout=timeout)

            if response.status_code != 200:
                return self._remember(now, False)

            try:
                data = response.json()
                result = data.get("assistant") is True
                return self._remember(now, result)
            except Exception:
                return self._remember(now, False)

        except Exception:
            return self._remember(now, False)


class NullAssistantClient:
    """Ассистент-заглушка: всегда отключен.

    Используется когда ML-ассистент не настроен.
    """

    async def ask(self, question: str, report: dict, site_id: str | None = None) -> AssistantAnswer:
        """Всегда выбрасывает ошибку."""
        raise AssistantUnavailable("Ассистент не настроен")

    async def available(self) -> bool:
        """Всегда возвращает False (не настроен)."""
        return False
