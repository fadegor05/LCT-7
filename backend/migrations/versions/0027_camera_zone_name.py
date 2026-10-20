"""cameras.zone_name

Revision ID: 0027
Revises: 0026
Create Date: 2026-10-20

Необязательное название рабочей зоны камеры для текстов отклонений. Существующие камеры
получат null: названия нет, тексты останутся прежними.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: str | None = "0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("cameras", sa.Column("zone_name", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("cameras", "zone_name")
