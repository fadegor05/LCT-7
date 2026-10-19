"""Почта как канал доставки и привязка по письму."""

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.notify.base import ChannelMessage, NotifyError
from app.adapters.notify.email import EmailChannel, build_message
from app.adapters.notify.factory import ChannelRegistry
from app.core.settings import Settings
from app.domains.notification.channels import ChannelLinkService, mask_address
from app.domains.notification.models import ChannelKind
from app.domains.notification.repository import ChannelLinkTokenRepository, UserChannelRepository
from app.domains.user.service import STAND_USER_ID, UserService
from app.plugins.exceptions import AppError


class FakeSmtp:
    """Вместо сети — список писем."""

    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list = []
        self.error = error

    async def send(self, mail) -> None:  # noqa: ANN001
        if self.error is not None:
            raise self.error
        self.sent.append(mail)


class RecordingChannel:
    kind = ChannelKind.EMAIL

    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[tuple[str, ChannelMessage]] = []
        self.error = error

    async def send(self, address: str, message: ChannelMessage) -> None:
        if self.error is not None:
            raise self.error
        self.sent.append((address, message))


def email_settings() -> Settings:
    settings = Settings()
    settings.notify.email.host = "smtp.test"
    settings.notify.email.from_addr = "bot@lct7.test"
    settings.notify.public_url = "https://lct7.test"
    return settings


def make_service(session: AsyncSession, channel: RecordingChannel | None) -> ChannelLinkService:
    registry = ChannelRegistry({ChannelKind.EMAIL: channel} if channel else {})
    return ChannelLinkService(
        channels=UserChannelRepository(session),
        tokens=ChannelLinkTokenRepository(session),
        session=session,
        settings=email_settings(),
        registry=registry,
    )


async def seed(container: AsyncContainer) -> None:
    async with container() as request_container:
        await (await request_container.get(UserService)).ensure_stand_user()


def test_build_message_has_subject_body_and_link() -> None:
    mail = build_message("a@x", "b@y", ChannelMessage(title="Тема", body="Текст", link="https://l"))

    assert mail["Subject"] == "Тема"
    assert mail["To"] == "b@y"
    content = mail.get_content()
    assert "Текст" in content and "https://l" in content


async def test_channel_hands_message_to_client() -> None:
    smtp = FakeSmtp()
    await EmailChannel(smtp, "bot@x").send("u@y", ChannelMessage(title="T", body="B"))  # type: ignore[arg-type]

    assert len(smtp.sent) == 1
    assert smtp.sent[0]["To"] == "u@y"


async def test_channel_propagates_notify_error() -> None:
    channel = EmailChannel(FakeSmtp(NotifyError("boom")), "bot@x")  # type: ignore[arg-type]

    with pytest.raises(NotifyError):
        await channel.send("u@y", ChannelMessage(title="T", body="B"))


def test_mask_hides_most_of_email_local_part() -> None:
    assert mask_address("ivan@example.com") == "i***@example.com"


async def test_issue_sends_confirmation_letter(container: AsyncContainer) -> None:
    await seed(container)
    channel = RecordingChannel()

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        token = await make_service(session, channel).issue(
            STAND_USER_ID, ChannelKind.EMAIL, address="u@example.com"
        )

    address, message = channel.sent[0]
    assert address == "u@example.com"
    assert message.link == f"https://lct7.test/api/notifications/email/confirm?token={token.token}"


async def test_issue_requires_address(container: AsyncContainer) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        with pytest.raises(AppError) as error:
            await make_service(session, RecordingChannel()).issue(STAND_USER_ID, ChannelKind.EMAIL)

    assert error.value.status_code == 422


async def test_issue_rejects_when_smtp_not_configured(container: AsyncContainer) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        service = make_service(session, RecordingChannel())
        service._settings = Settings()
        with pytest.raises(AppError) as error:
            await service.issue(STAND_USER_ID, ChannelKind.EMAIL, address="u@example.com")

    assert error.value.status_code == 409


async def test_send_failure_gives_502_and_no_token(container: AsyncContainer) -> None:
    await seed(container)
    channel = RecordingChannel(NotifyError("smtp down"))

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        with pytest.raises(AppError) as error:
            await make_service(session, channel).issue(
                STAND_USER_ID, ChannelKind.EMAIL, address="u@example.com"
            )

    assert error.value.status_code == 502


async def test_redeem_binds_address_from_token_once(container: AsyncContainer) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        service = make_service(session, RecordingChannel())
        token = await service.issue(STAND_USER_ID, ChannelKind.EMAIL, address="u@example.com")

        binding = await service.redeem(token.token)
        assert binding.address == "u@example.com"
        assert binding.channel == "email"

        with pytest.raises(AppError):
            await service.redeem(token.token)


async def test_telegram_token_cannot_be_redeemed_without_address(
    container: AsyncContainer,
) -> None:
    await seed(container)

    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        service = make_service(session, RecordingChannel())
        service._settings.notify.telegram.token = "1:a"
        service._settings.notify.telegram.bot_username = "bot"
        token = await service.issue(STAND_USER_ID, ChannelKind.TELEGRAM)

        with pytest.raises(AppError):
            await service.redeem(token.token)


async def test_confirm_endpoint_redirects_to_profile(client: AsyncClient) -> None:
    response = await client.get("/notifications/email/confirm?token=nope", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].endswith("/profile?email=invalid")
