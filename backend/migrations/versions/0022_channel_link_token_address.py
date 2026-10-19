"""channel_link_tokens.address

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-19

Адрес, который подтверждает токен привязки. Нужен почтовому каналу: пользователь вводит
e-mail до подтверждения, а у телеграма адрес приходит от бота при погашении токена.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("channel_link_tokens", sa.Column("address", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("channel_link_tokens", "address")
