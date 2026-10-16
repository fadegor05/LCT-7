"""Добавить в User аутентификацию (login и password_hash).

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-16

Колонки login (уникальный, чувствительный к регистру в БД, но хранится lowercase)
и password_hash (nullable) для поддержки login/password аутентификации.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("app_user", sa.Column("login", sa.String(length=64), nullable=True))
    op.add_column("app_user", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.create_unique_constraint("uq_app_user_login", "app_user", ["login"])


def downgrade() -> None:
    op.drop_constraint("uq_app_user_login", "app_user", type_="unique")
    op.drop_column("app_user", "password_hash")
    op.drop_column("app_user", "login")
