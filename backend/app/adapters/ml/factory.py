"""Factory для создания подходящего детектора и ассистента по конфигу."""

import httpx

from app.adapters.ml.assistant import (
    AssistantClient,
    HttpAssistantClient,
    NullAssistantClient,
)
from app.adapters.ml.base import DetectorClient
from app.adapters.ml.http import HttpDetectorClient, normalize_base_url
from app.adapters.ml.null import NullDetector
from app.adapters.ml.stamp import HttpStampReader
from app.core.settings import Settings
from app.domains.photo.date_resolver import NullStampOcr, StampOcr


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


def create_stamp_reader(
    settings: Settings,
    client: httpx.AsyncClient | None,
) -> StampOcr:
    """NullStampOcr если STAMP_ENABLED=false, URL пустой, или клиент недоступен."""
    if (
        settings.detector.stamp_enabled
        and settings.detector.url
        and settings.detector.url.strip()
        and client is not None
    ):
        return HttpStampReader(
            base_url=normalize_base_url(settings.detector.url),
            client=client,
            settings=settings.detector,
        )
    return NullStampOcr()


def create_assistant(
    settings: Settings,
    client: httpx.AsyncClient | None,
) -> AssistantClient:
    """Создать ассистента на основе конфига.

    Если settings.detector.url заполнен и не пустой после strip,
    и client не None — создать HttpAssistantClient. Иначе — NullAssistantClient.

    Args:
        settings: Settings, содержащий detector.url
        client: httpx.AsyncClient для отправки запросов (или None)

    Returns:
        Экземпляр HttpAssistantClient или NullAssistantClient
    """
    if settings.detector.url and settings.detector.url.strip() and client is not None:
        return HttpAssistantClient(
            base_url=settings.detector.url,
            client=client,
            settings=settings.assistant,
        )
    return NullAssistantClient()
