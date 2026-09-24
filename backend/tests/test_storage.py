"""Тесты для адаптера файлового хранилища."""

from pathlib import Path

import pytest
from moto import mock_aws

from app.adapters.storage import (
    LocalFileStorage,
    S3FileStorage,
    StorageError,
    create_storage,
)
from app.core.settings import Settings, StorageSettings


@pytest.fixture
def local_storage(tmp_path: Path) -> LocalFileStorage:
    """Создать экземпляр локального хранилища с временной директорией."""
    return LocalFileStorage(root=tmp_path)


@pytest.fixture
def s3_storage() -> S3FileStorage:
    """Создать экземпляр S3-хранилища с moto-моком."""
    with mock_aws():
        import boto3

        # Создать бакет перед возвращением хранилища
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket="test-bucket")

        storage = S3FileStorage(
            bucket="test-bucket",
            endpoint_url=None,  # moto перехватит вызовы к AWS SDK
            access_key="testing",
            secret_key="testing",
            region="us-east-1",
        )
        yield storage


class TestStorageContract:
    """Параметризованный контрактный тест для всех реализаций FileStorage."""

    @pytest.mark.parametrize(
        "storage_fixture",
        ["local_storage", "s3_storage"],
    )
    async def test_put_and_get_roundtrip(self, storage_fixture, request, monkeypatch):
        """Тест put/get: сохранить и прочитать файл."""
        if storage_fixture == "s3_storage":
            # Для S3 нужно оборачивать в moto
            with mock_aws():
                import boto3

                client = boto3.client("s3", region_name="us-east-1")
                client.create_bucket(Bucket="test-bucket")

                storage = S3FileStorage(
                    bucket="test-bucket",
                    endpoint_url=None,
                    access_key="testing",
                    secret_key="testing",
                    region="us-east-1",
                )
                data = b"test content"
                await storage.put("test.txt", data)
                result = await storage.get("test.txt")
                assert result == data
        else:
            storage = request.getfixturevalue("local_storage")
            data = b"test content"
            await storage.put("test.txt", data)
            result = await storage.get("test.txt")
            assert result == data

    @pytest.mark.parametrize(
        "storage_fixture",
        ["local_storage", "s3_storage"],
    )
    async def test_overwrite_file(self, storage_fixture, request):
        """Тест перезаписи файла."""
        if storage_fixture == "s3_storage":
            with mock_aws():
                import boto3

                client = boto3.client("s3", region_name="us-east-1")
                client.create_bucket(Bucket="test-bucket")

                storage = S3FileStorage(
                    bucket="test-bucket",
                    endpoint_url=None,
                    access_key="testing",
                    secret_key="testing",
                    region="us-east-1",
                )
                await storage.put("file.txt", b"old")
                await storage.put("file.txt", b"new")
                result = await storage.get("file.txt")
                assert result == b"new"
        else:
            storage = request.getfixturevalue("local_storage")
            await storage.put("file.txt", b"old")
            await storage.put("file.txt", b"new")
            result = await storage.get("file.txt")
            assert result == b"new"

    @pytest.mark.parametrize(
        "storage_fixture",
        ["local_storage", "s3_storage"],
    )
    async def test_get_missing_file_raises_error(self, storage_fixture, request):
        """Тест get несуществующего файла выбрасывает StorageError."""
        if storage_fixture == "s3_storage":
            with mock_aws():
                import boto3

                client = boto3.client("s3", region_name="us-east-1")
                client.create_bucket(Bucket="test-bucket")

                storage = S3FileStorage(
                    bucket="test-bucket",
                    endpoint_url=None,
                    access_key="testing",
                    secret_key="testing",
                    region="us-east-1",
                )
                with pytest.raises(StorageError, match="file not found"):
                    await storage.get("nonexistent.txt")
        else:
            storage = request.getfixturevalue("local_storage")
            with pytest.raises(StorageError, match="file not found"):
                await storage.get("nonexistent.txt")

    @pytest.mark.parametrize(
        "storage_fixture",
        ["local_storage", "s3_storage"],
    )
    async def test_exists_true_false(self, storage_fixture, request):
        """Тест exists: возвращает True/False корректно."""
        if storage_fixture == "s3_storage":
            with mock_aws():
                import boto3

                client = boto3.client("s3", region_name="us-east-1")
                client.create_bucket(Bucket="test-bucket")

                storage = S3FileStorage(
                    bucket="test-bucket",
                    endpoint_url=None,
                    access_key="testing",
                    secret_key="testing",
                    region="us-east-1",
                )
                assert not await storage.exists("file.txt")
                await storage.put("file.txt", b"data")
                assert await storage.exists("file.txt")
        else:
            storage = request.getfixturevalue("local_storage")
            assert not await storage.exists("file.txt")
            await storage.put("file.txt", b"data")
            assert await storage.exists("file.txt")

    @pytest.mark.parametrize(
        "storage_fixture",
        ["local_storage", "s3_storage"],
    )
    async def test_delete_idempotent(self, storage_fixture, request):
        """Тест delete: идемпотентна, не выбрасывает при отсутствии файла."""
        if storage_fixture == "s3_storage":
            with mock_aws():
                import boto3

                client = boto3.client("s3", region_name="us-east-1")
                client.create_bucket(Bucket="test-bucket")

                storage = S3FileStorage(
                    bucket="test-bucket",
                    endpoint_url=None,
                    access_key="testing",
                    secret_key="testing",
                    region="us-east-1",
                )
                # Удалить несуществующий файл (не выбросить)
                await storage.delete("nonexistent.txt")

                # Создать и удалить
                await storage.put("file.txt", b"data")
                await storage.delete("file.txt")
                assert not await storage.exists("file.txt")

                # Удалить снова (не выбросить)
                await storage.delete("file.txt")
        else:
            storage = request.getfixturevalue("local_storage")
            # Удалить несуществующий файл (не выбросить)
            await storage.delete("nonexistent.txt")

            # Создать и удалить
            await storage.put("file.txt", b"data")
            await storage.delete("file.txt")
            assert not await storage.exists("file.txt")

            # Удалить снова (не выбросить)
            await storage.delete("file.txt")

    @pytest.mark.parametrize(
        "storage_fixture",
        ["local_storage", "s3_storage"],
    )
    async def test_nested_keys(self, storage_fixture, request):
        """Тест вложенных ключей типа sites/x/photos/y.jpg."""
        if storage_fixture == "s3_storage":
            with mock_aws():
                import boto3

                client = boto3.client("s3", region_name="us-east-1")
                client.create_bucket(Bucket="test-bucket")

                storage = S3FileStorage(
                    bucket="test-bucket",
                    endpoint_url=None,
                    access_key="testing",
                    secret_key="testing",
                    region="us-east-1",
                )
                key = "sites/x/photos/y.jpg"
                data = b"image data"
                await storage.put(key, data)
                result = await storage.get(key)
                assert result == data
                assert await storage.exists(key)
                await storage.delete(key)
                assert not await storage.exists(key)
        else:
            storage = request.getfixturevalue("local_storage")
            key = "sites/x/photos/y.jpg"
            data = b"image data"
            await storage.put(key, data)
            result = await storage.get(key)
            assert result == data
            assert await storage.exists(key)
            await storage.delete(key)
            assert not await storage.exists(key)

    async def test_local_path_traversal_double_dot(self, local_storage: LocalFileStorage):
        """Тест: LocalFileStorage отклоняет ключи с ../."""
        with pytest.raises(StorageError, match="escape root"):
            await local_storage.put("../outside.txt", b"data")

    async def test_local_path_traversal_absolute(self, local_storage: LocalFileStorage):
        """Тест: LocalFileStorage отклоняет абсолютные пути."""
        with pytest.raises(StorageError, match="cannot be absolute"):
            await local_storage.put("/etc/passwd", b"data")

    async def test_local_path_traversal_complex(self, local_storage: LocalFileStorage):
        """Тест: LocalFileStorage отклоняет сложные traversal a/../../b."""
        with pytest.raises(StorageError, match="escape root"):
            await local_storage.put("a/../../outside.txt", b"data")


class TestStorageFactory:
    """Тесты фабрики create_storage."""

    def test_factory_creates_local_storage_when_s3_false(self, tmp_path: Path, monkeypatch):
        """Тест: create_storage возвращает LocalFileStorage при s3=False."""
        settings = Settings(s3=False, storage=StorageSettings(local_root=str(tmp_path)))
        storage = create_storage(settings)
        assert isinstance(storage, LocalFileStorage)

    def test_factory_creates_s3_storage_when_s3_true(self, monkeypatch):
        """Тест: create_storage возвращает S3FileStorage при s3=True."""
        settings = Settings(
            s3=True,
            storage=StorageSettings(
                endpoint_url="http://minio:9000",
                bucket="test-bucket",
                access_key="key",
                secret_key="secret",
            ),
        )
        storage = create_storage(settings)
        assert isinstance(storage, S3FileStorage)


class TestSettingsParsingEnv:
    """Тесты парсинга settings из окружения."""

    def test_storage_settings_from_env(self, monkeypatch, tmp_path: Path):
        """Тест: StorageSettings парсится из STORAGE__* переменных."""
        monkeypatch.setenv("S3", "false")
        monkeypatch.setenv("STORAGE__BUCKET", "custom-bucket")
        monkeypatch.setenv("STORAGE__LOCAL_ROOT", str(tmp_path))
        monkeypatch.setenv("STORAGE__MAX_UPLOAD_MB", "50")

        settings = Settings()
        assert settings.s3 is False
        assert settings.storage.bucket == "custom-bucket"
        assert settings.storage.local_root == str(tmp_path)
        assert settings.storage.max_upload_mb == 50

    def test_detector_settings_from_env(self, monkeypatch):
        """Тест: DetectorSettings парсится из DETECTOR__* переменных."""
        monkeypatch.setenv("DETECTOR__URL", "http://detector:5000")
        monkeypatch.setenv("DETECTOR__TIMEOUT_S", "60.0")

        settings = Settings()
        assert settings.detector.url == "http://detector:5000"
        assert settings.detector.timeout_s == 60.0

    def test_s3_true_with_s3_settings(self, monkeypatch):
        """Тест: S3 включается и параметры парсятся."""
        monkeypatch.setenv("S3", "true")
        monkeypatch.setenv("STORAGE__ENDPOINT_URL", "http://minio:9000")
        monkeypatch.setenv("STORAGE__BUCKET", "photos")
        monkeypatch.setenv("STORAGE__ACCESS_KEY", "minio")
        monkeypatch.setenv("STORAGE__SECRET_KEY", "miniopass")
        monkeypatch.setenv("STORAGE__REGION", "us-west-2")

        settings = Settings()
        assert settings.s3 is True
        assert settings.storage.endpoint_url == "http://minio:9000"
        assert settings.storage.bucket == "photos"
        assert settings.storage.access_key == "minio"
        assert settings.storage.secret_key == "miniopass"
        assert settings.storage.region == "us-west-2"


class TestLocalStorageLazyInit:
    """Тесты ленивой инициализации LocalFileStorage."""

    def test_construct_with_nonexistent_root_does_not_raise(self):
        """Тест: конструктор не создаёт директорию, не выбрасывает."""
        # /nonexistent-root/x точно не существует и не доступна для записи
        nonexistent_root = "/nonexistent-root/x"
        # Конструктор не должен выбросить
        storage = LocalFileStorage(root=nonexistent_root)
        assert storage.root.as_posix() == nonexistent_root

    def test_put_creates_parent_dirs_in_tmp_path(self, tmp_path: Path):
        """Тест: put() создаёт родительские директории при необходимости."""
        storage = LocalFileStorage(root=tmp_path)
        # Положить файл с вложенными директориями, которые не существуют
        await_result = storage.put("deep/nested/file.txt", b"data")

        # Использовать asyncio для получения результата
        import asyncio

        asyncio.run(await_result)
        # Проверить, что файл создался
        assert (tmp_path / "deep" / "nested" / "file.txt").read_bytes() == b"data"

    async def test_get_on_nonexistent_root_raises_error(self, tmp_path: Path):
        """Тест: get() на не созданном root выбрасывает StorageError."""
        nonexistent_root = tmp_path / "does_not_exist"
        storage = LocalFileStorage(root=nonexistent_root)
        with pytest.raises(StorageError, match="file not found"):
            await storage.get("file.txt")

    async def test_exists_on_nonexistent_root_returns_false(self, tmp_path: Path):
        """Тест: exists() на не созданном root возвращает False."""
        nonexistent_root = tmp_path / "does_not_exist"
        storage = LocalFileStorage(root=nonexistent_root)
        assert not await storage.exists("file.txt")

    async def test_delete_on_nonexistent_root_is_idempotent(self, tmp_path: Path):
        """Тест: delete() на не созданном root идемпотентна."""
        nonexistent_root = tmp_path / "does_not_exist"
        storage = LocalFileStorage(root=nonexistent_root)
        # Не должна выбросить
        await storage.delete("file.txt")
