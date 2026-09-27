"""Фабрика для создания экземпляра хранилища."""

from app.core.settings import Settings

from .base import FileStorage
from .local import LocalFileStorage
from .s3 import S3FileStorage


def create_storage(settings: Settings) -> FileStorage:
    """Создать хранилище на основе настроек.

    Args:
        settings: Объект конфигурации.

    Returns:
        Реализация FileStorage (S3 или локальное).
    """
    if settings.s3:
        return S3FileStorage(
            bucket=settings.storage.bucket,
            endpoint_url=settings.storage.endpoint_url,
            access_key=settings.storage.access_key,
            secret_key=settings.storage.secret_key,
            region=settings.storage.region,
        )
    else:
        return LocalFileStorage(root=settings.storage.local_root)
