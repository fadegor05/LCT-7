"""Factory для создания подходящего детектора по конфигу."""

import httpx

from app.adapters.ml.base import DetectorClient
from app.adapters.ml.http import HttpDetectorClient
from app.adapters.ml.null import NullDetector
from app.core.settings import Settings


def create_detector(
    settings: Settings,
    client: httpx.AsyncClient | None,
) -> DetectorClient:
    """Создать детектор на основе конфига.

    Если settings.detector.url заполнен и не пустой после strip,
    и client не None — создать HttpDetectorClient. Иначе — NullDetector.

    Args:
        settings: Settings, содержащий detector.url и другие параметры
        client: httpx.AsyncClient для отправки запросов (или None для NullDetector)

    Returns:
        Экземпляр HttpDetectorClient или NullDetector
    """
    if settings.detector.url and settings.detector.url.strip() and client is not None:
        return HttpDetectorClient(
            base_url=settings.detector.url,
            client=client,
            settings=settings.detector,
        )
    return NullDetector()
