"""notifications: уведомления, каналы доставки и токены привязки

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-18

Таблица notifications (лента пользователя), user_channels (привязка канала доставки)
и channel_link_tokens (одноразовые токены привязки). Тип уведомления и вид канала —
обычные строки, а не постгресовый ENUM: список типов пополняется доменами-источниками,
и новый тип не должен требовать миграции.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("type", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.String(length=500), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notifications_user_id"), "notifications", ["user_id"], unique=False)
    # Шторка читает ленту одного пользователя в обратном хронологическом порядке
    op.create_index(
        "ix_notifications_user_created",
        "notifications",
        ["user_id", sa.text("created_at DESC")],
        unique=False,
    )

    op.create_table(
        "user_channels",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "channel", name="uq_user_channels_user_channel"),
    )
    op.create_index(op.f("ix_user_channels_user_id"), "user_channels", ["user_id"], unique=False)

    op.create_table(
        "channel_link_tokens",
        sa.Column("token", sa.String(length=32), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_index(
        op.f("ix_channel_link_tokens_user_id"), "channel_link_tokens", ["user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_channel_link_tokens_user_id"), table_name="channel_link_tokens")
    op.drop_table("channel_link_tokens")

    op.drop_index(op.f("ix_user_channels_user_id"), table_name="user_channels")
    op.drop_table("user_channels")

    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_index(op.f("ix_notifications_user_id"), table_name="notifications")
    op.drop_table("notifications")
