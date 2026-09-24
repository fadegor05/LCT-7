"""Конфигурация приложения (аналог core/Settings.kt).

Переменные читаются из окружения / .env. Вложенные секции задаются через
двойное подчёркивание, как в Kotlin-бэкенде: POSTGRES__HOST, POSTGRES__PORT и т.д.
"""

from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseModel):
    host: str = "postgres"
    port: int = 5432
    user: str = "app_user"
    password: str = "supersecretpassword"
    db: str = "postgres"

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class StorageSettings(BaseModel):
    """Параметры файлового хранилища (локального или S3)."""

    endpoint_url: str | None = None
    bucket: str = "photos"
    access_key: str = "minioadmin"
    secret_key: str = "minioadmin"
    region: str = "us-east-1"
    local_root: str = "/data/storage"
    max_upload_mb: float = 20
    max_batch_files: int = 50

    @property
    def max_upload_bytes(self) -> int:
        """Максимальный размер одного загружаемого файла в байтах."""
        return int(self.max_upload_mb * 1024 * 1024)


class DetectorSettings(BaseModel):
    """Параметры ML-детектора."""

    url: str | None = None
    timeout_s: float = 30.0


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    domain: str = "localhost"
    secure: bool = False
    # Префикс, под которым Traefik отдаёт бэкенд (PathPrefix(`/api`)). Traefik
    # префикс не срезает, поэтому роуты монтируются именно под ним.
    api_prefix: str = "/api"
    backend_tag: str = "dev"

    postgres: PostgresSettings = PostgresSettings()
    s3: bool = False
    storage: StorageSettings = StorageSettings()
    detector: DetectorSettings = DetectorSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
