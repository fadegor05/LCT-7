"""HTTP-роуты ленты уведомлений текущего пользователя.

Схемы собираются здесь: сервисы возвращают модели
(.claude/rules/backend/architecture.md).
"""

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from app.core.settings import Settings
from app.domains.notification.channels import ChannelLinkService, mask_address
from app.domains.notification.digest import DigestService
from app.domains.notification.models import ChannelKind, UserChannel
from app.domains.notification.schemas import (
    ChannelLinkRequest,
    ChannelLinkResponse,
    ChannelToggle,
    MarkReadResponse,
    NotificationList,
    NotificationRead,
    TestNotificationRequest,
    UserChannelRead,
)
from app.domains.notification.service import NotificationService
from app.domains.user.provider import CurrentUser
from app.plugins.exceptions import AppError

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
@inject
async def list_notifications(
    user: FromDishka[CurrentUser],
    service: FromDishka[NotificationService],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> NotificationList:
    items, unread = await service.list_for(user.id, limit=limit, offset=offset)
    return NotificationList(
        items=[NotificationRead.model_validate(item) for item in items],
        unread_count=unread,
    )


@router.post("/read")
@inject
async def mark_all_read(
    user: FromDishka[CurrentUser],
    service: FromDishka[NotificationService],
) -> MarkReadResponse:
    """Открытие шторки помечает прочитанным всё непрочитанное разом."""
    return MarkReadResponse(marked=await service.mark_all_read(user.id))


@router.post("/test", status_code=201)
@inject
async def create_test_notification(
    data: TestNotificationRequest,
    user: FromDishka[CurrentUser],
    service: FromDishka[NotificationService],
) -> NotificationRead:
    """Служебное создание произвольного уведомления себе — для демо и ручной проверки."""
    created = await service.notify(
        user_id=user.id,
        type=data.type,
        title=data.title,
        body=data.body,
        link=data.link,
    )
    return NotificationRead.model_validate(created)


@router.post("/digest", status_code=201)
@inject
async def send_digest(
    user: FromDishka[CurrentUser],
    service: FromDishka[DigestService],
) -> NotificationRead:
    """Отправить себе сводку по объектам сейчас: лента и привязанные каналы."""
    return NotificationRead.model_validate(await service.send_to_me(user.id))


channels_router = APIRouter(prefix="/users/me/channels", tags=["notifications"])


def _channel_read(binding: UserChannel) -> UserChannelRead:
    """Привязка наружу: без полного адреса."""
    return UserChannelRead(
        channel=ChannelKind(binding.channel),
        address_masked=mask_address(binding.address),
        enabled=binding.enabled,
        linked_at=binding.linked_at,
    )


@channels_router.get("")
@inject
async def list_channels(
    user: FromDishka[CurrentUser],
    service: FromDishka[ChannelLinkService],
) -> list[UserChannelRead]:
    bindings = await service.list_for(user.id)
    return [_channel_read(binding) for binding in bindings]


@channels_router.post("/{channel}/link")
@inject
async def link_channel(
    channel: ChannelKind,
    user: FromDishka[CurrentUser],
    service: FromDishka[ChannelLinkService],
    settings: FromDishka[Settings],
    data: ChannelLinkRequest | None = None,
) -> ChannelLinkResponse:
    """Выдать одноразовую ссылку привязки канала.

    Почта: в теле адрес, на него уходит письмо со ссылкой подтверждения; url в ответе пуст.
    """
    address = data.address if data else None
    token = await service.issue(user.id, channel, address=address)
    if channel is ChannelKind.EMAIL:
        return ChannelLinkResponse(url=None, expires_at=token.expires_at)
    bot = settings.notify.telegram.bot_username
    return ChannelLinkResponse(
        url=f"https://t.me/{bot}?start={token.token}", expires_at=token.expires_at
    )


@channels_router.patch("/{channel}")
@inject
async def toggle_channel(
    channel: ChannelKind,
    data: ChannelToggle,
    user: FromDishka[CurrentUser],
    service: FromDishka[ChannelLinkService],
) -> UserChannelRead:
    return _channel_read(await service.set_enabled(user.id, channel, data.enabled))


@channels_router.delete("/{channel}", status_code=204)
@inject
async def unlink_channel(
    channel: ChannelKind,
    user: FromDishka[CurrentUser],
    service: FromDishka[ChannelLinkService],
) -> None:
    await service.unlink(user.id, channel)


# Публичный роут: ссылку из письма открывают в браузере, где нет заголовка авторизации.
# Защита — одноразовый непредсказуемый токен с коротким сроком жизни.
email_confirm_router = APIRouter(prefix="/notifications/email", tags=["notifications"])


@email_confirm_router.get("/confirm")
@inject
async def confirm_email(
    token: str,
    service: FromDishka[ChannelLinkService],
    settings: FromDishka[Settings],
) -> RedirectResponse:
    """Погасить токен из письма и вернуть пользователя в профиль."""
    try:
        await service.redeem(token)
        result = "confirmed"
    except AppError:
        result = "invalid"
    return RedirectResponse(f"{settings.notify.public_url}/profile?email={result}", status_code=302)
