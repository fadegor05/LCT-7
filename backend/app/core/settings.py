"""Конфигурация приложения (аналог core/Settings.kt).

Переменные читаются из окружения / .env. Вложенные секции задаются через
двойное подчёркивание, как в Kotlin-бэкенде: POSTGRES__HOST, POSTGRES__PORT и т.д.
"""

from datetime import date
from enum import StrEnum
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
    max_batch_mb: float = 200

    @property
    def max_upload_bytes(self) -> int:
        """Максимальный размер одного загружаемого файла в байтах."""
        return int(self.max_upload_mb * 1024 * 1024)

    @property
    def max_batch_bytes(self) -> int:
        """Максимальный общий размер пачки файлов в байтах."""
        return int(self.max_batch_mb * 1024 * 1024)


class DetectorSettings(BaseModel):
    """Параметры ML-детектора."""

    url: str | None = None
    timeout_s: float = 30.0
    connect_timeout_s: float = 2.0
    max_concurrency: int = 2
    retry_503: int = 3
    retry_other: int = 1
    retry_backoff_s: tuple[float, ...] = (2.0, 5.0, 10.0)
    retry_budget_s: float = 20.0
    stamp_enabled: bool = False  # LCT-13


class ObservationSettings(BaseModel):
    """Пороги для расчёта наблюдаемости, уверенности и активности."""

    min_photos_medium: int = 2
    min_photos_high: int = 3
    min_score_high: float = 0.7
    min_score_medium: float = 0.4
    movement_threshold: float = 0.05


class AsOfMode(StrEnum):
    """Режим определения опорной даты расчёта отклонений (LCT-14).

    today — обычное поведение, date.today(). last_observation — дата
    последнего наблюдения НА КОНКРЕТНОЙ площадке (как в ML-отчёте:
    as_of = states[-1]["date"], ml/tools/match_schedule.py) — нужно для
    демо на площадках из разных лет, где одна общая дата не годится.
    fixed — одна дата на всё окружение (as_of_override).
    """

    TODAY = "today"
    LAST_OBSERVATION = "last_observation"
    FIXED = "fixed"


class AssessmentSettings(BaseModel):
    """Пороги для расчёта статусов этапов и отклонений."""

    tolerance_days: int = 3
    stale_data_days: int = 7
    no_progress_window_days: int = 5
    min_confirming_observations: int = 2
    # Режим опорной даты расчёта (LCT-14) — см. AsOfMode.
    as_of_mode: AsOfMode = AsOfMode.TODAY
    # Используется только при as_of_mode == "fixed".
    as_of_override: date | None = None


class AssistantSettings(BaseModel):
    """Параметры ассистента (ML-адаптер и API)."""

    timeout_s: float = 130.0
    connect_timeout_s: float = 2.0
    rate_limit_per_min: int = 10
    max_report_kb: int = 512
    status_cache_s: float = 30.0
    status_retry_s: float = 5.0
    # Разбор плана моделью идёт кусками по ~40 строк, каждый — отдельный вызов LLM
    parse_timeout_s: float = 600.0


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
    observation: ObservationSettings = ObservationSettings()
    assessment: AssessmentSettings = AssessmentSettings()
    assistant: AssistantSettings = AssistantSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()
