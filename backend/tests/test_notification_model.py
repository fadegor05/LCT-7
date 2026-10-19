"""Схема уведомлений: типы — строки, а не постгресовый ENUM."""

from datetime import UTC, datetime, timedelta

import pytest
from dishka import AsyncContainer
from sqlalchemy import String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notification.models import (
    ChannelKind,
    ChannelLinkToken,
    Notification,
    NotificationType,
    UserChannel,
)
from app.domains.user.service import STAND_USER_ID, UserService


async def seed_user(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


def test_type_column_is_a_string_not_a_db_enum() -> None:
    """Расширение списка типов не должно требовать миграции."""
    assert isinstance(Notification.__table__.c.type.type, String)
    assert isinstance(UserChannel.__table__.c.channel.type, String)


def test_enums_are_str_enums() -> None:
    assert NotificationType.SYSTEM == "system"
    assert ChannelKind.TELEGRAM == "telegram"


async def test_notification_round_trip(container: AsyncContainer) -> None:
    await seed_user(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(
            Notification(
                user_id=STAND_USER_ID,
                type=NotificationType.SYSTEM,
                title="Проверка",
                body="Тело уведомления",
                link="/sites",
            )
        )
        await session.commit()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        stored = (await session.execute(select(Notification))).scalar_one()

        assert stored.title == "Проверка"
        assert stored.read_at is None
        assert stored.created_at is not None


async def test_one_channel_binding_per_user(container: AsyncContainer) -> None:
    """Второй телеграм у того же пользователя — нарушение уникальности."""
    await seed_user(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add_all(
            [
                UserChannel(user_id=STAND_USER_ID, channel=ChannelKind.TELEGRAM, address="111"),
                UserChannel(user_id=STAND_USER_ID, channel=ChannelKind.TELEGRAM, address="222"),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_link_token_round_trip(container: AsyncContainer) -> None:
    await seed_user(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(
            ChannelLinkToken(
                token="a" * 32,
                user_id=STAND_USER_ID,
                channel=ChannelKind.TELEGRAM,
                expires_at=datetime.now(UTC) + timedelta(minutes=15),
            )
        )
        await session.commit()

        stored = (await session.execute(select(ChannelLinkToken))).scalar_one()
        assert stored.used_at is None
        assert len(stored.token) == 32
        assert stored.user_id == STAND_USER_ID
