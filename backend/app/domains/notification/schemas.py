"""Pydantic-схемы уведомлений и каналов доставки.

Схемы собираются в роутерах из моделей, которые возвращают сервисы
(.claude/rules/backend/architecture.md).
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domains.notification.models import ChannelKind, NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    title: str
    body: str
    link: str | None
    read_at: datetime | None
    created_at: datetime


class NotificationList(BaseModel):
    """Страница ленты. unread_count считает всю ленту, а не выданную страницу."""

    items: list[NotificationRead]
    unread_count: int


class MarkReadResponse(BaseModel):
    marked: int


class UserChannelRead(BaseModel):
    """Привязка канала. Полный адрес наружу не отдаётся."""

    channel: ChannelKind
    address_masked: str
    enabled: bool
    linked_at: datetime


class ChannelToggle(BaseModel):
    enabled: bool


class ChannelLinkResponse(BaseModel):
    """Ссылка привязки и срок её жизни."""

    url: str
    expires_at: datetime


class TestNotificationRequest(BaseModel):
    """Служебное создание уведомления себе — для демо и ручной проверки."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(default="Тестовое уведомление", min_length=1, max_length=255)
    body: str = Field(default="Проверка системы уведомлений", min_length=1, max_length=4000)
    type: NotificationType = NotificationType.SYSTEM
    link: str | None = Field(default=None, max_length=500)
