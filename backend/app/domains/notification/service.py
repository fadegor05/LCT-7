"""Лента уведомлений: создание, чтение, пометка прочитанным."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notification.dispatcher import NotificationDispatcher
from app.domains.notification.models import Notification, NotificationType
from app.domains.notification.repository import NotificationRepository


class NotificationService:
    def __init__(
        self,
        repository: NotificationRepository,
        session: AsyncSession,
        dispatcher: NotificationDispatcher,
    ) -> None:
        self._repository = repository
        self._session = session
        self._dispatcher = dispatcher

    async def notify(
        self,
        user_id: uuid.UUID,
        type: NotificationType,
        title: str,
        body: str,
        link: str | None = None,
    ) -> Notification:
        """Создать уведомление и запланировать доставку по каналам.

        Единственная точка входа для доменов-источников: они не знают ни про
        каналы, ни про телеграм.
        """
        notification = Notification(
            user_id=user_id,
            type=type.value,
            title=title,
            body=body,
            link=link,
        )
        await self._repository.add(notification)
        await self._session.commit()
        # Доставка идёт только после коммита: до него уведомления ещё нет
        self._dispatcher.schedule(notification.id)
        return notification

    async def list_for(
        self, user_id: uuid.UUID, limit: int, offset: int
    ) -> tuple[Sequence[Notification], int]:
        """Страница ленты и число непрочитанных во всей ленте."""
        items = await self._repository.list_for_user(user_id, limit=limit, offset=offset)
        unread = await self._repository.count_unread(user_id)
        return items, unread

    async def mark_all_read(self, user_id: uuid.UUID) -> int:
        """Пометить прочитанным всё непрочитанное; сколько записей тронули."""
        marked = await self._repository.mark_all_read(user_id, datetime.now(UTC))
        await self._session.commit()
        return marked
