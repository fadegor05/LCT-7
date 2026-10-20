"""VideoSettings: лимиты ручной загрузки видео из конфигурации (VIDEO__*)."""

import pytest
from pydantic import ValidationError

from app.core.settings import Settings, VideoSettings


def test_video_settings_default_values() -> None:
    settings = VideoSettings()

    assert settings.max_mb == 500
    assert settings.max_frames == 200
    assert settings.default_step_s == 30
    assert settings.min_step_s == 5
    assert settings.max_step_s == 3600
    assert settings.timeout_s == 300


def test_video_settings_max_bytes_property() -> None:
    assert VideoSettings().max_bytes == 500 * 1024 * 1024
    assert VideoSettings(max_mb=1.5).max_bytes == int(1.5 * 1024 * 1024)


def test_video_settings_rejects_too_few_frames() -> None:
    with pytest.raises(ValidationError):
        VideoSettings(max_frames=1)


def test_settings_contains_video_settings() -> None:
    settings = Settings()

    assert isinstance(settings.video, VideoSettings)


def test_video_max_frames_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEO__MAX_FRAMES", "10")

    assert Settings().video.max_frames == 10
