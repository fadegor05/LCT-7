"""ML-адаптер: точка входа для работы с детектором объектов.

Основные экспорты:
- DetectorClient: Protocol для клиента детектора
- RawDetection: Одна детекция
- DetectionResult: Результат обработки кадра
- DetectorError: Исключение при ошибке детектора
- DetectorInfo: Информация о детекторе
- NullDetector: Детектор-заглушка
- HttpDetectorClient: HTTP-клиент к ML-сервису
- create_detector: Factory для создания подходящего детектора
"""

from app.adapters.ml.base import (
    DetectionResult,
    DetectorClient,
    DetectorError,
    DetectorInfo,
    RawDetection,
)
from app.adapters.ml.factory import create_detector
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
]
