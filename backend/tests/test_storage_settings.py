"""StorageSettings: параметры файлового хранилища из конфигурации."""

from app.core.settings import Settings, StorageSettings


def test_storage_settings_default_values() -> None:
    """Значения по умолчанию для StorageSettings."""
    settings = StorageSettings()

    assert settings.max_upload_mb == 20
    assert settings.max_batch_files == 50
    assert settings.max_batch_mb == 200


def test_storage_settings_max_batch_bytes_property() -> None:
    """Свойство max_batch_bytes вычисляется из max_batch_mb."""
    settings = StorageSettings()

    assert settings.max_batch_bytes == 200 * 1024 * 1024
    assert settings.max_batch_bytes == 209715200


def test_storage_settings_max_upload_bytes_property() -> None:
    """Свойство max_upload_bytes вычисляется из max_upload_mb."""
    settings = StorageSettings()

    assert settings.max_upload_bytes == 20 * 1024 * 1024
    assert settings.max_upload_bytes == 20971520


def test_settings_contains_storage_settings() -> None:
    """Settings включает вложенную StorageSettings."""
    settings = Settings()

    assert isinstance(settings.storage, StorageSettings)
    assert settings.storage.max_batch_mb == 200
    assert settings.storage.max_batch_bytes == 200 * 1024 * 1024
