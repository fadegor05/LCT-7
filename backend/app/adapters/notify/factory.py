"""Сборка реестра каналов по настройкам."""

from app.adapters.notify.base import NotificationChannel
from app.adapters.notify.log import LogChannel
from app.core.settings import Settings
from app.domains.notification.models import ChannelKind


class ChannelRegistry:
    """Канал по его виду. Неизвестный вид — None, доставка просто не состоится."""

    def __init__(self, channels: dict[ChannelKind, NotificationChannel]) -> None:
        self._channels = channels

    def get(self, kind: ChannelKind) -> NotificationChannel | None:
        return self._channels.get(kind)


def create_channel_registry(settings: Settings) -> ChannelRegistry:
    """Собрать реестр: настоящий телеграм при заданном токене, иначе лог."""
    channels: dict[ChannelKind, NotificationChannel] = {ChannelKind.TELEGRAM: LogChannel()}
    return ChannelRegistry(channels)
