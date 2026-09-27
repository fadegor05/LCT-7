"""Базовые интерфейсы и исключения для работы с файловым хранилищем."""

from typing import Protocol


class StorageError(Exception):
    """Исключение при работе с хранилищем (общее для локального и S3)."""

    pass


class FileStorage(Protocol):
    """Протокол асинхронного файлового хранилища."""

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        """Сохранить данные в хранилище.

        Args:
            key: Ключ (путь) файла.
            data: Содержимое файла.
            content_type: MIME-тип файла (опционально).

        Raises:
            StorageError: При ошибке записи.
        """
        ...

    async def get(self, key: str) -> bytes:
        """Прочитать данные из хранилища.

        Args:
            key: Ключ (путь) файла.

        Returns:
            Содержимое файла.

        Raises:
            StorageError: При ошибке чтения или если файл не найден.
        """
        ...

    async def delete(self, key: str) -> None:
        """Удалить файл из хранилища.

        Args:
            key: Ключ (путь) файла.

        Raises:
            StorageError: При ошибке удаления. Идемпотентна — если файл
                не существует, не выбрасывает исключение.
        """
        ...

    async def exists(self, key: str) -> bool:
        """Проверить наличие файла.

        Args:
            key: Ключ (путь) файла.

        Returns:
            True если файл существует, False иначе.
        """
        ...
