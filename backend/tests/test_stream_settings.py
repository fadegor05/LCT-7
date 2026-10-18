"""Настройки снимков со стрима: STREAM__* из окружения, проверка значений."""

import pytest
from pydantic import ValidationError

from app.core.settings import Settings, StreamSettings


def test_stream_capture_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STREAM__ENABLED", raising=False)
    settings = Settings()
    assert settings.stream.enabled is False
    assert settings.stream.window == (8, 20)
    assert settings.stream.timezone == "Europe/Moscow"
    assert settings.stream.allowed_networks == []


def test_stream_settings_come_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STREAM__ENABLED", "true")
    monkeypatch.setenv("STREAM__HOURS", "9-18")
    monkeypatch.setenv("STREAM__CONCURRENCY", "2")
    monkeypatch.setenv("STREAM__ALLOWED_NETWORKS", '["192.168.1.0/24"]')
    settings = Settings()
    assert settings.stream.enabled is True
    assert settings.stream.window == (9, 18)
    assert settings.stream.concurrency == 2
    assert settings.stream.allowed_networks == ["192.168.1.0/24"]


@pytest.mark.parametrize("hours", ["20-8", "8-25", "8", "a-b", "8-8"])
def test_window_must_be_hours_inside_one_day(hours: str) -> None:
    with pytest.raises(ValidationError):
        StreamSettings(hours=hours)


@pytest.mark.parametrize("network", ["192.168.1.0/33", "cam.lan", "10.0.0.0/8/8"])
def test_networks_must_be_cidr(network: str) -> None:
    with pytest.raises(ValidationError):
        StreamSettings(allowed_networks=[network])
    with pytest.raises(ValidationError):
        StreamSettings(blocked_networks=[network])


def test_unknown_timezone_is_rejected() -> None:
    with pytest.raises(ValidationError):
        StreamSettings(timezone="Mars/Olympus")
