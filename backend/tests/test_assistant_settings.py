"""AssistantSettings: параметры ассистента из конфигурации."""

import pytest

from app.core.settings import AssistantSettings, Settings


def test_assistant_settings_default_values() -> None:
    """Значения по умолчанию для AssistantSettings."""
    settings = AssistantSettings()

    assert settings.timeout_s == 130.0
    assert settings.connect_timeout_s == 2.0
    assert settings.rate_limit_per_min == 10
    assert settings.max_report_kb == 512
    assert settings.status_cache_s == 30.0
    assert settings.status_retry_s == 5.0


def test_settings_contains_assistant_settings() -> None:
    """Settings включает вложенную AssistantSettings."""
    settings = Settings()

    assert isinstance(settings.assistant, AssistantSettings)
    assert settings.assistant.rate_limit_per_min == 10


def test_assistant_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Переменные окружения ASSISTANT__* переопределяют значения по умолчанию."""
    monkeypatch.setenv("ASSISTANT__RATE_LIMIT_PER_MIN", "3")
    monkeypatch.setenv("ASSISTANT__TIMEOUT_S", "7")

    settings = Settings()

    assert settings.assistant.rate_limit_per_min == 3
    assert settings.assistant.timeout_s == 7.0
    assert settings.assistant.connect_timeout_s == 2.0  # остальные по умолчанию
