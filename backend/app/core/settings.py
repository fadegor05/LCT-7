"""Конфигурация приложения (аналог core/Settings.kt).

Переменные читаются из окружения / .env. Вложенные секции задаются через
двойное подчёркивание, как в Kotlin-бэкенде: POSTGRES__HOST, POSTGRES__PORT и т.д.
"""

import ipaddress
from datetime import date
from enum import StrEnum
from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_AUTH_SECRET_KEY = "dev-insecure-change-me"


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
    stamp_enabled: bool = True  # LCT-13; без DETECTOR__URL всё равно NullStampOcr


class StreamSettings(BaseModel):
    """Снимки со стрима камеры (STREAM__*). Выключены по умолчанию: прод не меняется."""

    # Фоновый планировщик и сам захват; «Снять кадр сейчас» работает только при включении
    enabled: bool = False
    # Часы съёмки по поясу стройки, конец не включается: «8-20» — с 8:00 до 19:59
    hours: str = "8-20"
    timezone: str = "Europe/Moscow"
    # Сколько ждать один кадр со стрима
    timeout_s: float = 15.0
    # Сколько камер снимать одновременно
    concurrency: int = Field(default=4, ge=1)
    # Как часто планировщик смотрит, кому пора снимать
    tick_s: float = 15.0
    # После сбоев интервал удваивается, но не дальше этого
    max_backoff_s: int = 3600
    # Службы compose, с которых снимать нельзя (по именам); петля и метаданные закрыты всегда
    blocked_hosts: list[str] = ["postgres", "minio", "ml", "backend", "frontend", "web"]
    # Свои закрытые сети (CIDR) сверх всего перечисленного
    blocked_networks: list[str] = []
    # Частные сети с камерами стройки (CIDR), которые разрешаем снимать; по умолчанию никакие
    allowed_networks: list[str] = []

    @field_validator("hours")
    @classmethod
    def _check_hours(cls, value: str) -> str:
        start, sep, end = value.strip().partition("-")
        if not (sep and start.isdigit() and end.isdigit() and 0 <= int(start) < int(end) <= 24):
            raise ValueError(
                f"STREAM__HOURS — часы «начало-конец» в пределах суток, а не {value!r}"
            )
        return value.strip()

    @field_validator("timezone")
    @classmethod
    def _check_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)  # неизвестный пояс падает здесь, а не в фоновой задаче
        except (ZoneInfoNotFoundError, ValueError) as e:
            raise ValueError(f"STREAM__TIMEZONE — пояс IANA, а не {value!r}") from e
        return value

    @field_validator("blocked_networks", "allowed_networks")
    @classmethod
    def _check_networks(cls, value: list[str]) -> list[str]:
        for network in value:
            ipaddress.ip_network(network, strict=False)  # ValueError — не CIDR
        return value

    @property
    def window(self) -> tuple[int, int]:
        start, end = self.hours.split("-")
        return int(start), int(end)


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


class AuthSettings(BaseModel):
    """Параметры аутентификации (JWT и rate limiting)."""

    secret_key: str = DEFAULT_AUTH_SECRET_KEY
    token_ttl_minutes: int = 720
    login_rate_limit_per_min: int = 10
    register_rate_limit_per_min: int = 5
    seed_login: str | None = None
    seed_password: str | None = None


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
    stream: StreamSettings = StreamSettings()
    observation: ObservationSettings = ObservationSettings()
    assessment: AssessmentSettings = AssessmentSettings()
    assistant: AssistantSettings = AssistantSettings()
    auth: AuthSettings = AuthSettings()


@lru_cache
def get_settings() -> Settings:
    return Settings()


def check_auth_secret(settings: Settings) -> None:
    """Проверить что secret_key не использует значение по умолчанию в secure режиме.

    Поднимает RuntimeError если secure=True и secret_key равен DEFAULT_AUTH_SECRET_KEY.
    """
    if settings.secure and settings.auth.secret_key == DEFAULT_AUTH_SECRET_KEY:
        raise RuntimeError(
            "INSECURE: secure=True but auth.secret_key is still the default. "
            "Set AUTH__SECRET_KEY in environment."
        )
