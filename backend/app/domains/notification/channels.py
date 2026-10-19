"""Привязка каналов доставки: одноразовые токены, тумблер, отвязка.

Сервис возвращает модели, схемы собирает роутер
(.claude/rules/backend/architecture.md).
"""

import secrets
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.notify.base import ChannelMessage, NotifyError
from app.adapters.notify.factory import ChannelRegistry
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
    """Показать только хвост адреса: chat_id наружу не отдаём; у почты — a***@домен."""
    if "@" in address:
        local, _, domain = address.rpartition("@")
        return f"{local[:1]}***@{domain}"
    return f"…{address[-4:]}"


class ChannelLinkService:
    def __init__(
        self,
        channels: UserChannelRepository,
        tokens: ChannelLinkTokenRepository,
        session: AsyncSession,
        settings: Settings,
        # Нужен только отправке писем; поллеру телеграма он ни к чему
        registry: ChannelRegistry | None = None,
    ) -> None:
        self._channels = channels
        self._tokens = tokens
        self._session = session
        self._settings = settings
        self._registry = registry

    async def list_for(self, user_id: uuid.UUID) -> Sequence[UserChannel]:
        return await self._channels.list_for_user(user_id)

    async def issue(
        self, user_id: uuid.UUID, channel: ChannelKind, address: str | None = None
    ) -> ChannelLinkToken:
        """Выдать одноразовый токен привязки.

        Для почты address обязателен: токен уходит письмом на этот адрес, и привязка
        состоится только после перехода по ссылке из письма.
        """
        if channel is ChannelKind.TELEGRAM and not self._settings.notify.telegram_configured:
            raise AppError("Канал «телеграм» не настроен на сервере", status_code=409)
        if channel is ChannelKind.EMAIL:
            if not self._settings.notify.email_configured:
                raise AppError("Канал «почта» не настроен на сервере", status_code=409)
            if not address:
                raise AppError("Не указан адрес почты", status_code=422)

        token = ChannelLinkToken(
            token=secrets.token_urlsafe(24)[:TOKEN_LENGTH],
            user_id=user_id,
            channel=channel.value,
            address=address if channel is ChannelKind.EMAIL else None,
            expires_at=datetime.now(UTC) + timedelta(minutes=LINK_TOKEN_TTL_MINUTES),
        )
        await self._tokens.add(token)
        if channel is ChannelKind.EMAIL and address:
            await self._send_confirmation(token, address)
        await self._session.commit()
        return token

    async def _send_confirmation(self, token: ChannelLinkToken, address: str) -> None:
        """Письмо со ссылкой подтверждения. Не ушло — токен не коммитим."""
        channel = self._registry.get(ChannelKind.EMAIL) if self._registry else None
        if channel is None:
            raise AppError("Канал «почта» не настроен на сервере", status_code=409)
        base = self._settings.notify.public_url
        url = f"{base}{self._settings.api_prefix}/notifications/email/confirm?token={token.token}"
        message = ChannelMessage(
            title="Подтверждение почты",
            body=(
                "Чтобы получать уведомления на этот адрес, подтвердите его по ссылке. "
                f"Она действует {LINK_TOKEN_TTL_MINUTES} минут. "
                "Если вы ничего не привязывали, просто проигнорируйте письмо."
            ),
            link=url,
        )
        try:
            await channel.send(address, message)
        except NotifyError as error:
            raise AppError("Не удалось отправить письмо подтверждения", status_code=502) from error

    async def redeem(self, token: str, address: str | None = None) -> UserChannel:
        """Погасить токен и привязать адрес.

        Телеграм: зовётся поллером бота и передаёт chat_id. Почта: адрес берётся из токена.
        """
        stored = await self._tokens.get(token)
        if stored is None or stored.used_at is not None:
            raise AppError("Ссылка привязки недействительна", status_code=404)
        address = address or stored.address
        if not address:
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
