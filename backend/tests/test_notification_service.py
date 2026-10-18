"""Лента уведомлений: порядок, счётчик непрочитанных, пометка прочитанным."""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from dishka import AsyncContainer
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notification.dispatcher import NotificationDispatcher
from app.domains.notification.models import NotificationType
from app.domains.notification.repository import NotificationRepository
from app.domains.notification.service import NotificationService
from app.domains.user.models import User
from app.domains.user.service import STAND_USER_ID, UserService


class RecordingDispatcher:
    """Запоминает, что отправку попросили, но ничего не шлёт."""

    def __init__(self) -> None:
        self.scheduled: list[uuid.UUID] = []

    def schedule(self, notification_id: uuid.UUID) -> None:
        self.scheduled.append(notification_id)


@asynccontextmanager
async def make_service(
    container: AsyncContainer, dispatcher: NotificationDispatcher
) -> AsyncIterator[NotificationService]:
    """Сервис поверх сессии живого request-контейнера."""
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        yield NotificationService(
            repository=NotificationRepository(session),
            session=session,
            dispatcher=dispatcher,
        )


async def seed_user(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


async def test_notify_stores_and_schedules_delivery(container: AsyncContainer) -> None:
    await seed_user(container)
    dispatcher = RecordingDispatcher()

    async with make_service(container, dispatcher) as service:
        created = await service.notify(
            user_id=STAND_USER_ID,
            type=NotificationType.SYSTEM,
            title="Заголовок",
            body="Текст",
            link="/sites",
        )

        assert created.read_at is None
        assert dispatcher.scheduled == [created.id]


async def test_list_returns_newest_first_with_unread_count(container: AsyncContainer) -> None:
    await seed_user(container)

    async with make_service(container, RecordingDispatcher()) as service:
        await service.notify(STAND_USER_ID, NotificationType.SYSTEM, "Первое", "a", None)
        await service.notify(STAND_USER_ID, NotificationType.SYSTEM, "Второе", "b", None)

        items, unread = await service.list_for(STAND_USER_ID, limit=50, offset=0)

        assert [item.title for item in items] == ["Второе", "Первое"]
        assert unread == 2


async def test_mark_all_read_zeroes_the_counter(container: AsyncContainer) -> None:
    await seed_user(container)

    async with make_service(container, RecordingDispatcher()) as service:
        await service.notify(STAND_USER_ID, NotificationType.SYSTEM, "Первое", "a", None)

        marked = await service.mark_all_read(STAND_USER_ID)
        items, unread = await service.list_for(STAND_USER_ID, limit=50, offset=0)

        assert marked == 1
        assert unread == 0
        assert items[0].read_at is not None


async def test_mark_all_read_is_idempotent(container: AsyncContainer) -> None:
    """Открыли шторку дважды — второй раз помечать нечего."""
    await seed_user(container)

    async with make_service(container, RecordingDispatcher()) as service:
        await service.notify(STAND_USER_ID, NotificationType.SYSTEM, "Первое", "a", None)

        first = await service.mark_all_read(STAND_USER_ID)
        second = await service.mark_all_read(STAND_USER_ID)

        assert (first, second) == (1, 0)


async def test_mark_all_read_does_not_touch_other_users(container: AsyncContainer) -> None:
    """Review Focus 1: пометка прочитанным изолирована по пользователю."""
    await seed_user(container)
    other_id = uuid.uuid4()
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(User(id=other_id, full_name="Другой инженер"))
        await session.commit()

    async with make_service(container, RecordingDispatcher()) as service:
        await service.notify(STAND_USER_ID, NotificationType.SYSTEM, "Моё", "a", None)
        await service.notify(other_id, NotificationType.SYSTEM, "Чужое", "b", None)

        await service.mark_all_read(STAND_USER_ID)
        _, mine_unread = await service.list_for(STAND_USER_ID, limit=50, offset=0)
        _, theirs_unread = await service.list_for(other_id, limit=50, offset=0)

        assert mine_unread == 0
        assert theirs_unread == 1


async def test_list_paginates(container: AsyncContainer) -> None:
    await seed_user(container)

    async with make_service(container, RecordingDispatcher()) as service:
        for index in range(3):
            await service.notify(STAND_USER_ID, NotificationType.SYSTEM, f"№{index}", "x", None)

        page, page_unread = await service.list_for(STAND_USER_ID, limit=2, offset=0)
        tail, _ = await service.list_for(STAND_USER_ID, limit=2, offset=2)

        assert len(page) == 2
        assert len(tail) == 1
        # Счётчик непрочитанных считает всё, а не страницу
        assert page_unread == 3
