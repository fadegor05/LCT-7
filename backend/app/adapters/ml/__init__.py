"""ML-адаптер: точка входа для работы с детектором объектов и ассистентом.

Основные экспорты:
- DetectorClient: Protocol для клиента детектора
- RawDetection: Одна детекция
- DetectionResult: Результат обработки кадра
- DetectorError: Исключение при ошибке детектора
- DetectorInfo: Информация о детекторе
- NullDetector: Детектор-заглушка
- HttpDetectorClient: HTTP-клиент к ML-сервису
- create_detector: Factory для создания подходящего детектора
- AssistantClient: Protocol для клиента ассистента
- AssistantAnswer: Ответ ассистента
- AssistantError: Исключение при ошибке ассистента
- AssistantUnavailable: Ассистент недоступен (503)
- AssistantTimeout: Таймаут ассистента (504)
- AssistantBadRequest: Некорректный запрос (400/422)
- NullAssistantClient: Ассистент-заглушка
- HttpAssistantClient: HTTP-клиент к ассистенту
- create_assistant: Factory для создания подходящего ассистента
"""

from app.adapters.ml.assistant import (
    AssistantAnswer,
    AssistantBadRequest,
    AssistantClient,
    AssistantError,
    AssistantTimeout,
    AssistantUnavailable,
    HttpAssistantClient,
    NullAssistantClient,
)
from app.adapters.ml.base import (
    DetectionResult,
    DetectorClient,
    DetectorError,
    DetectorInfo,
    RawDetection,
)
from app.adapters.ml.factory import create_assistant, create_detector
from app.adapters.ml.http import HttpDetectorClient
from app.adapters.ml.null import NullDetector

__all__ = [
    "DetectorClient",
    "RawDetection",
    "DetectionResult",
    "DetectorError",
    "DetectorInfo",
    "NullDetector",
    "HttpDetectorClient",
    "create_detector",
    "AssistantClient",
    "AssistantAnswer",
    "AssistantError",
    "AssistantUnavailable",
    "AssistantTimeout",
    "AssistantBadRequest",
    "NullAssistantClient",
    "HttpAssistantClient",
    "create_assistant",
]
