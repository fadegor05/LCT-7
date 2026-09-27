"""Адаптер для работы с файловым хранилищем."""

from .base import FileStorage, StorageError
from .factory import create_storage
from .local import LocalFileStorage
from .s3 import S3FileStorage

__all__ = [
    "FileStorage",
    "StorageError",
    "LocalFileStorage",
    "S3FileStorage",
    "create_storage",
]
