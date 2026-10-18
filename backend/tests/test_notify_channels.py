"""Реестр каналов: без настроек — только запись в лог."""

import logging

import pytest

from app.adapters.notify.base import ChannelMessage, NotificationChannel
from app.adapters.notify.factory import create_channel_registry
from app.adapters.notify.log import LogChannel
from app.core.settings import Settings
from app.domains.notification.models import ChannelKind


def test_log_channel_satisfies_the_protocol() -> None:
    channel: NotificationChannel = LogChannel()

    assert channel.kind is ChannelKind.TELEGRAM


async def test_log_channel_writes_title_and_body(
    caplog: pytest.LogCaptureFixture,
) -> None:
    channel = LogChannel()

    with caplog.at_level(logging.INFO):
        await channel.send("42", ChannelMessage(title="Заголовок", body="Текст", link=None))

    assert "Заголовок" in caplog.text


async def test_registry_without_token_falls_back_to_log() -> None:
    """Без токена бота привязанный телеграм не должен ронять доставку."""
    settings = Settings()
    settings.notify.telegram.token = None

    registry = create_channel_registry(settings)

    assert isinstance(registry.get(ChannelKind.TELEGRAM), LogChannel)


def test_registry_returns_none_for_unknown_channel() -> None:
    settings = Settings()

    registry = create_channel_registry(settings)

    assert registry.get("smoke-signals") is None  # type: ignore[arg-type]
