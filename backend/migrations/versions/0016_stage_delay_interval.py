"""stage_statuses.delay_min, delay_max: сдвиг этапа интервалом

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-19

Сдвиг этапа — интервал, как в clean-mvp: затянувшийся конец «14–74 дня» (от последнего дня
с маркером до опорной даты), позднее начало «до 63» (нижней границы нет). delay_days
остаётся одним числом для прежних экранов. Существующие статусы получат интервал при
ближайшем пересчёте.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stage_statuses", sa.Column("delay_min", sa.Integer(), nullable=True))
    op.add_column("stage_statuses", sa.Column("delay_max", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("stage_statuses", "delay_max")
    op.drop_column("stage_statuses", "delay_min")
