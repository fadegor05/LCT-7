"""ORM-модели уведомлений, привязок каналов и токенов привязки.

Тип уведомления и вид канала — питоновские StrEnum поверх колонки String, а не
постгресовый ENUM: список типов пополняется доменами-источниками, и новый тип не
должен требовать миграции.
"""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class NotificationType(StrEnum):
    """Тип уведомления. Домены-источники добавляют свои значения сюда."""

    SYSTEM = "system"


class ChannelKind(StrEnum):
    """Канал доставки. СМС появится отдельным адаптером."""

    TELEGRAM = "telegram"
    EMAIL = "email"


class Notification(Base):
    """Уведомление для одного пользователя; рассылок на группу нет."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Относительный путь фронта, куда ведёт клик; абсолютный URL для внешних
    # каналов собирается из NOTIFY__PUBLIC_URL
    link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # NULL — непрочитанное; шторка проставляет время при открытии
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Время ставит приложение, а не БД: server_default=func.now() в Postgres возвращает
    # время начала транзакции, а в SQLite округляет до секунды, и два уведомления подряд
    # получают одинаковый штамп. Тогда порядок ленты решает тай-брейкер по случайному
    # UUID — то есть он произволен. Микросекунды из datetime.now() это чинят.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # Шторка читает ленту одного пользователя в обратном хронологическом порядке
        Index("ix_notifications_user_created", "user_id", created_at.desc()),
    )


class UserChannel(Base):
    """Привязка канала доставки к пользователю."""

    __tablename__ = "user_channels"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    # Для телеграма — chat_id строкой; в ответах API маскируется
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    # Тумблер «слать сюда», отдельно от факта привязки
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    linked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (UniqueConstraint("user_id", "channel", name="uq_user_channels_user_channel"),)


class ChannelLinkToken(Base):
    """Одноразовый токен привязки канала.

    Лежит в БД, а не в памяти процесса: в деве бэкенд поднят с --reload, и правка
    любого файла убила бы токен посреди привязки.
    """

    __tablename__ = "channel_link_tokens"

    token: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("app_user.id", ondelete="CASCADE"), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    # Адрес, который подтверждается токеном. Для почты его вводит пользователь до
    # подтверждения; у телеграма адрес приходит от бота при погашении, тут NULL
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
