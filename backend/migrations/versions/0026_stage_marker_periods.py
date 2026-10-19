"""stage_statuses.marker_periods

Revision ID: 0026
Revises: 0025
Create Date: 2026-10-19

Периоды маркеров этапа для методики (clean-mvp): когда машина отличает этап от идущих
одновременно — «маркер 07.04–11.05». Существующие статусы получат поле при пересчёте.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stage_statuses", sa.Column("marker_periods", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("stage_statuses", "marker_periods")
