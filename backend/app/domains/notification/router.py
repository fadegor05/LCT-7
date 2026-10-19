"""HTTP-роуты ленты уведомлений текущего пользователя.

Схемы собираются здесь: сервисы возвращают модели
(.claude/rules/backend/architecture.md).
"""

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Query

from app.core.settings import Settings
from app.domains.notification.channels import ChannelLinkService, mask_address
from app.domains.notification.models import ChannelKind, UserChannel
from app.domains.notification.schemas import (
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
    """Служебное создание уведомления себе: источников событий пока нет."""
    created = await service.notify(
        user_id=user.id,
        type=data.type,
        title=data.title,
        body=data.body,
        link=data.link,
    )
    return NotificationRead.model_validate(created)


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
) -> ChannelLinkResponse:
    """Выдать одноразовую ссылку привязки канала."""
    token = await service.issue(user.id, channel)
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
