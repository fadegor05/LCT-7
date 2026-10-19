"""Репозитории уведомлений и каналов. Коммит — забота сервиса."""

import uuid
from collections.abc import Sequence
from datetime import datetime
from typing import cast

from sqlalchemy import CursorResult, func, select, update

from app.core.repository import BaseRepository
from app.domains.notification.models import (
    ChannelKind,
    ChannelLinkToken,
    Notification,
    UserChannel,
)


class NotificationRepository(BaseRepository[Notification]):
    model = Notification

    async def list_for_user(
        self, user_id: uuid.UUID, limit: int, offset: int
    ) -> Sequence[Notification]:
        """Лента пользователя, новые сверху."""
        result = await self._session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc(), Notification.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def count_unread(self, user_id: uuid.UUID) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        )
        return int(result.scalar_one())

    async def mark_all_read(self, user_id: uuid.UUID, now: datetime) -> int:
        """Пометить прочитанными все непрочитанные этого пользователя; сколько тронули."""
        # UPDATE возвращает CursorResult: у него есть rowcount, у общего Result — нет
        result = cast(
            CursorResult,
            await self._session.execute(
                update(Notification)
                .where(Notification.user_id == user_id, Notification.read_at.is_(None))
                .values(read_at=now)
            ),
        )
        await self._session.flush()
        return int(result.rowcount or 0)


class UserChannelRepository(BaseRepository[UserChannel]):
    model = UserChannel

    async def list_for_user(self, user_id: uuid.UUID) -> Sequence[UserChannel]:
        result = await self._session.execute(
            select(UserChannel).where(UserChannel.user_id == user_id).order_by(UserChannel.channel)
        )
        return result.scalars().all()

    async def get_for(self, user_id: uuid.UUID, channel: ChannelKind) -> UserChannel | None:
        result = await self._session.execute(
            select(UserChannel).where(
                UserChannel.user_id == user_id, UserChannel.channel == channel.value
            )
        )
        return result.scalar_one_or_none()

    async def list_enabled(self, user_id: uuid.UUID) -> Sequence[UserChannel]:
        result = await self._session.execute(
            select(UserChannel).where(UserChannel.user_id == user_id, UserChannel.enabled.is_(True))
        )
        return result.scalars().all()


class ChannelLinkTokenRepository(BaseRepository[ChannelLinkToken]):
    model = ChannelLinkToken
