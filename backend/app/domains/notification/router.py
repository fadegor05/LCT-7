"""HTTP-роуты ленты уведомлений текущего пользователя.

Схемы собираются здесь: сервисы возвращают модели
(.claude/rules/backend/architecture.md).
"""

from dishka.integrations.fastapi import FromDishka, inject
from fastapi import APIRouter, Query

from app.domains.notification.schemas import (
    MarkReadResponse,
    NotificationList,
    NotificationRead,
    TestNotificationRequest,
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
