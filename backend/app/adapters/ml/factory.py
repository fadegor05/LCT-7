"""Factory для создания подходящего детектора по конфигу."""

from app.adapters.ml.base import DetectorClient
from app.adapters.ml.http import HttpDetectorClient
from app.adapters.ml.null import NullDetector
from app.core.settings import Settings


def create_detector(settings: Settings) -> DetectorClient:
    """Создать детектор на основе конфига.

    Если settings.detector.url заполнен и не пустой после strip —
    создать HttpDetectorClient. Иначе — NullDetector (отключен).

    Args:
        settings: Settings, содержащий detector.url и detector.timeout_s

    Returns:
        Экземпляр HttpDetectorClient или NullDetector
    """
    if settings.detector.url and settings.detector.url.strip():
        return HttpDetectorClient(
            url=settings.detector.url,
            timeout_s=settings.detector.timeout_s,
        )
    return NullDetector()
