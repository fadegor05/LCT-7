"""Сборка реестра каналов по настройкам."""

from app.adapters.notify.base import NotificationChannel
from app.adapters.notify.log import LogChannel
from app.adapters.notify.telegram import TelegramChannel, TelegramClient
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
    telegram: NotificationChannel = LogChannel()
    if settings.notify.telegram.token:
        telegram = TelegramChannel(
            TelegramClient(
                token=settings.notify.telegram.token,
                timeout_s=settings.notify.telegram.request_timeout_s,
                proxy_url=settings.notify.telegram.proxy_url,
            )
        )
    channels: dict[ChannelKind, NotificationChannel] = {ChannelKind.TELEGRAM: telegram}
    return ChannelRegistry(channels)
