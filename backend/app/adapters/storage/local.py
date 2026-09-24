"""Локальное файловое хранилище."""

import asyncio
from pathlib import Path

from .base import StorageError


class LocalFileStorage:
    """Хранилище файлов на локальной файловой системе."""

    def __init__(self, root: Path | str):
        """Инициализировать хранилище (ленивая инициализация).

        Конструктор не создаёт директории и не проверяет их доступность.
        Директории создаются по первому обращению к put().

        Args:
            root: Корневая директория для файлов.
        """
        self.root = Path(root)

    def _validate_key(self, key: str) -> Path:
        """Валидировать и разрешить ключ к абсолютному пути.

        Args:
            key: Ключ файла.

        Returns:
            Абсолютный Path внутри root.

        Raises:
            StorageError: Если ключ пытается выйти за пределы root
                или является абсолютным путём.
        """
        if key.startswith("/"):
            raise StorageError(f"key cannot be absolute: {key}")

        # Разрешить ключ относительно root
        path = (self.root / key).resolve()

        # Проверить, что разрешённый путь остаётся внутри root
        try:
            path.relative_to(self.root)
        except ValueError as e:
            raise StorageError(f"key tries to escape root: {key}") from e

        return path

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        """Сохранить данные в локальный файл.

        Args:
            key: Ключ (путь) файла.
            data: Содержимое файла.
            content_type: Игнорируется для локального хранилища.

        Raises:
            StorageError: При ошибке записи.
        """
        try:
            path = self._validate_key(key)
            # Создать родительские директории
            path.parent.mkdir(parents=True, exist_ok=True)
            # Писать в отдельном потоке, чтобы не блокировать event loop
            await asyncio.to_thread(path.write_bytes, data)
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"failed to write {key}: {e}") from e

    async def get(self, key: str) -> bytes:
        """Прочитать данные из локального файла.

        Args:
            key: Ключ (путь) файла.

        Returns:
            Содержимое файла.

        Raises:
            StorageError: При ошибке чтения или если файл не найден.
        """
        try:
            path = self._validate_key(key)
            if not path.exists():
                raise StorageError(f"file not found: {key}")
            return await asyncio.to_thread(path.read_bytes)
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"failed to read {key}: {e}") from e

    async def delete(self, key: str) -> None:
        """Удалить локальный файл.

        Args:
            key: Ключ (путь) файла.

        Raises:
            StorageError: При ошибке удаления (игнорирует FileNotFoundError).
        """
        try:
            path = self._validate_key(key)
            if path.exists():
                await asyncio.to_thread(path.unlink)
        except StorageError:
            raise
        except FileNotFoundError:
            # Идемпотентна: файл уже удалён или не существовал
            pass
        except Exception as e:
            raise StorageError(f"failed to delete {key}: {e}") from e

    async def exists(self, key: str) -> bool:
        """Проверить наличие локального файла.

        Args:
            key: Ключ (путь) файла.

        Returns:
            True если файл существует, False иначе.
        """
        try:
            path = self._validate_key(key)
            return await asyncio.to_thread(path.exists)
        except StorageError:
            return False
