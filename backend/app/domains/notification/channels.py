"""Привязка каналов доставки: одноразовые токены, тумблер, отвязка.

Сервис возвращает модели, схемы собирает роутер
(.claude/rules/backend/architecture.md).
"""

import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.domains.notification.models import ChannelKind, ChannelLinkToken, UserChannel
from app.domains.notification.repository import (
    ChannelLinkTokenRepository,
    UserChannelRepository,
)
from app.plugins.exceptions import AppError

# Столько живёт ссылка привязки: хватает дойти до телеграма и нажать «Запустить»
LINK_TOKEN_TTL_MINUTES = 15
# Длина колонки token в channel_link_tokens
TOKEN_LENGTH = 32


def mask_address(address: str) -> str:
    """Показать только хвост адреса: chat_id наружу не отдаём."""
    return f"…{address[-4:]}"


class ChannelLinkService:
    def __init__(
        self,
        channels: UserChannelRepository,
        tokens: ChannelLinkTokenRepository,
        session: AsyncSession,
        settings: Settings,
    ) -> None:
        self._channels = channels
        self._tokens = tokens
        self._session = session
        self._settings = settings

    async def list_for(self, user_id: uuid.UUID) -> Sequence[UserChannel]:
        return await self._channels.list_for_user(user_id)

    async def issue(self, user_id: uuid.UUID, channel: ChannelKind) -> ChannelLinkToken:
        """Выдать одноразовый токен привязки."""
        if channel is ChannelKind.TELEGRAM and not self._settings.notify.telegram_configured:
            raise AppError("Канал «телеграм» не настроен на сервере", status_code=409)

        token = ChannelLinkToken(
            token=secrets.token_urlsafe(24)[:TOKEN_LENGTH],
            user_id=user_id,
            channel=channel.value,
            expires_at=datetime.now(UTC) + timedelta(minutes=LINK_TOKEN_TTL_MINUTES),
        )
        await self._tokens.add(token)
        await self._session.commit()
        return token

    async def redeem(self, token: str, address: str) -> UserChannel:
        """Погасить токен и привязать адрес. Зовётся поллером бота."""
        stored = await self._tokens.get(token)
        if stored is None or stored.used_at is not None:
            raise AppError("Ссылка привязки недействительна", status_code=404)
        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            # SQLite возвращает naive datetime; в Postgres колонка timezone-aware
            expires_at = expires_at.replace(tzinfo=UTC)
        if expires_at < datetime.now(UTC):
            raise AppError("Ссылка привязки устарела", status_code=410)

        kind = ChannelKind(stored.channel)
        existing = await self._channels.get_for(stored.user_id, kind)
        if existing is None:
            existing = UserChannel(
                user_id=stored.user_id, channel=kind.value, address=address, enabled=True
            )
            await self._channels.add(existing)
        else:
            # Перепривязка с другого аккаунта меняет адрес, а не плодит строки
            existing.address = address
            existing.enabled = True

        stored.used_at = datetime.now(UTC)
        await self._session.commit()
        return existing

    async def set_enabled(
        self, user_id: uuid.UUID, channel: ChannelKind, enabled: bool
    ) -> UserChannel:
        binding = await self._require(user_id, channel)
        binding.enabled = enabled
        await self._session.commit()
        return binding

    async def unlink(self, user_id: uuid.UUID, channel: ChannelKind) -> None:
        """Отвязать канал. Историю уведомлений не трогаем."""
        binding = await self._require(user_id, channel)
        await self._channels.delete(binding)
        await self._session.commit()

    async def _require(self, user_id: uuid.UUID, channel: ChannelKind) -> UserChannel:
        binding = await self._channels.get_for(user_id, channel)
        if binding is None:
            raise AppError("Канал не привязан", status_code=404)
        return binding
