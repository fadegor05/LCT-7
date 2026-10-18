"""Привязка каналов: выдача токена, погашение, тумблер, отвязка."""

from datetime import UTC, datetime, timedelta

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import Settings
from app.domains.notification.channels import ChannelLinkService, mask_address
from app.domains.notification.models import (
    ChannelKind,
    ChannelLinkToken,
    Notification,
    NotificationType,
)
from app.domains.notification.repository import (
    ChannelLinkTokenRepository,
    UserChannelRepository,
)
from app.domains.user.service import STAND_USER_ID, UserService
from app.plugins.exceptions import AppError


async def seed(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


def make_service(session: AsyncSession) -> ChannelLinkService:
    settings = Settings()
    settings.notify.telegram.token = "123:abc"
    settings.notify.telegram.bot_username = "lct7_bot"
    return ChannelLinkService(
        channels=UserChannelRepository(session),
        tokens=ChannelLinkTokenRepository(session),
        session=session,
        settings=settings,
    )


def test_mask_shows_only_the_tail() -> None:
    assert mask_address("123456789") == "…6789"
    assert mask_address("42") == "…42"


async def test_issue_returns_a_live_token(container: AsyncContainer) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        issued = await make_service(session).issue(STAND_USER_ID, ChannelKind.TELEGRAM)

    assert len(issued.token) <= 32
    assert issued.used_at is None
    assert issued.expires_at > datetime.now(UTC)


async def test_redeem_creates_binding(container: AsyncContainer) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        service = make_service(session)
        issued = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)

        binding = await service.redeem(issued.token, address="777")

        assert binding.address == "777"
        assert binding.enabled is True


async def test_second_redeem_of_the_same_token_fails(container: AsyncContainer) -> None:
    """Review Focus 2: повторный /start не создаёт вторую привязку."""
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        service = make_service(session)
        issued = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        await service.redeem(issued.token, address="777")

        with pytest.raises(AppError):
            await service.redeem(issued.token, address="888")

        bindings = await UserChannelRepository(session).list_for_user(STAND_USER_ID)
        assert len(bindings) == 1
        assert bindings[0].address == "777"


async def test_expired_token_is_rejected(container: AsyncContainer) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(
            ChannelLinkToken(
                token="e" * 32,
                user_id=STAND_USER_ID,
                channel=ChannelKind.TELEGRAM,
                expires_at=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        await session.commit()

        with pytest.raises(AppError):
            await make_service(session).redeem("e" * 32, address="777")


async def test_unknown_token_is_rejected(container: AsyncContainer) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        with pytest.raises(AppError):
            await make_service(session).redeem("z" * 32, address="777")


async def test_relink_replaces_the_address(container: AsyncContainer) -> None:
    """Перепривязка с другого аккаунта телеграма меняет адрес, а не плодит строки."""
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        service = make_service(session)
        first = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        await service.redeem(first.token, address="111")
        second = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        await service.redeem(second.token, address="222")

        bindings = await UserChannelRepository(session).list_for_user(STAND_USER_ID)
        assert len(bindings) == 1
        assert bindings[0].address == "222"


# ---------- HTTP ----------


async def test_channels_endpoint_is_empty_at_first(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed(container)

    response = await client.get("/users/me/channels")

    assert response.status_code == 200
    assert response.json() == []


async def test_link_without_bot_configured_returns_409(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """В тестовом окружении токена бота нет — нерабочую ссылку выдавать нельзя."""
    await seed(container)

    response = await client.post("/users/me/channels/telegram/link")

    assert response.status_code == 409
    assert "не настроен" in response.json()["detail"]


async def test_toggle_and_unlink(client: AsyncClient, container: AsyncContainer) -> None:
    await seed(container)
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        service = make_service(session)
        issued = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        await service.redeem(issued.token, address="123456789")

    listed = await client.get("/users/me/channels")
    toggled = await client.patch("/users/me/channels/telegram", json={"enabled": False})
    unlinked = await client.delete("/users/me/channels/telegram")
    after = await client.get("/users/me/channels")

    assert listed.json()[0]["address_masked"] == "…6789"
    assert "123456789" not in listed.text
    assert toggled.json()["enabled"] is False
    assert unlinked.status_code == 204
    assert after.json() == []


async def test_unlink_keeps_notification_history(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Отвязка канала — не удаление ленты."""
    await seed(container)
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(
            Notification(
                user_id=STAND_USER_ID,
                type=NotificationType.SYSTEM,
                title="Было",
                body="Текст",
            )
        )
        await session.commit()
        service = make_service(session)
        issued = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)
        await service.redeem(issued.token, address="123456789")

    await client.delete("/users/me/channels/telegram")
    feed = await client.get("/notifications")

    assert len(feed.json()["items"]) == 1


async def test_toggle_missing_channel_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    await seed(container)

    response = await client.patch("/users/me/channels/telegram", json={"enabled": True})

    assert response.status_code == 404
