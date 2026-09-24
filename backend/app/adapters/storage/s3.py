"""S3-совместимое хранилище (AWS S3, MinIO и т.д.)."""

import asyncio

import boto3
from botocore.exceptions import ClientError

from .base import StorageError


class S3FileStorage:
    """Хранилище файлов в S3-совместимом сервисе."""

    def __init__(
        self,
        bucket: str,
        endpoint_url: str | None = None,
        access_key: str = "minioadmin",
        secret_key: str = "minioadmin",
        region: str = "us-east-1",
    ):
        """Инициализировать S3-хранилище.

        Args:
            bucket: Имя бакета.
            endpoint_url: URL эндпоинта (None для AWS S3, иначе например
                http://minio:9000 для MinIO).
            access_key: Access Key ID.
            secret_key: Secret Access Key.
            region: AWS регион.
        """
        self.bucket = bucket
        self.endpoint_url = endpoint_url
        self.access_key = access_key
        self.secret_key = secret_key
        self.region = region

        # Создать boto3 клиента (он создаёт новый экземпляр, не синглтон)
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    async def put(self, key: str, data: bytes, content_type: str | None = None) -> None:
        """Сохранить данные в S3.

        Args:
            key: Ключ объекта в S3.
            data: Содержимое файла.
            content_type: MIME-тип файла (передаётся в Content-Type).

        Raises:
            StorageError: При ошибке записи.
        """
        try:

            def _put() -> None:
                kwargs: dict[str, str | bytes] = {
                    "Bucket": self.bucket,
                    "Key": key,
                    "Body": data,
                }
                if content_type:
                    kwargs["ContentType"] = content_type
                self._client.put_object(**kwargs)  # type: ignore[arg-type]

            await asyncio.to_thread(_put)
        except ClientError as e:
            raise StorageError(f"failed to put {key} to S3: {e}") from e
        except Exception as e:
            raise StorageError(f"failed to put {key} to S3: {e}") from e

    async def get(self, key: str) -> bytes:
        """Прочитать данные из S3.

        Args:
            key: Ключ объекта в S3.

        Returns:
            Содержимое файла.

        Raises:
            StorageError: При ошибке чтения или если объект не найден.
        """
        try:

            def _get() -> bytes:
                response = self._client.get_object(Bucket=self.bucket, Key=key)
                body = response.get("Body")
                if body is None:
                    raise StorageError(f"no body in response for {key}")
                return body.read()

            return await asyncio.to_thread(_get)

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "NoSuchKey":
                raise StorageError(f"file not found: {key}") from e
            raise StorageError(f"failed to get {key} from S3: {e}") from e
        except StorageError:
            raise
        except Exception as e:
            raise StorageError(f"failed to get {key} from S3: {e}") from e

    async def delete(self, key: str) -> None:
        """Удалить объект из S3.

        Args:
            key: Ключ объекта в S3.

        Raises:
            StorageError: При ошибке удаления (игнорирует отсутствие файла).
        """
        try:

            def _delete() -> None:
                self._client.delete_object(Bucket=self.bucket, Key=key)

            await asyncio.to_thread(_delete)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code == "NoSuchKey":
                # Идемпотентна: файл уже удалён или не существовал
                return
            raise StorageError(f"failed to delete {key} from S3: {e}") from e
        except Exception as e:
            raise StorageError(f"failed to delete {key} from S3: {e}") from e

    async def exists(self, key: str) -> bool:
        """Проверить наличие объекта в S3.

        Args:
            key: Ключ объекта в S3.

        Returns:
            True если объект существует, False иначе.
        """
        try:

            def _exists() -> bool:
                try:
                    self._client.head_object(Bucket=self.bucket, Key=key)
                    return True
                except ClientError as e:
                    error_code = e.response.get("Error", {}).get("Code")
                    if error_code in ("NoSuchKey", "404"):
                        return False
                    # Другие ошибки (например, permission denied) — рассмотрим как
                    # что файл не найден для консервативности
                    return False

            return await asyncio.to_thread(_exists)
        except Exception:
            return False
