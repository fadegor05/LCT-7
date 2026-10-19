"""site_summaries: итог по объекту из пересчёта; stage_statuses.delay_open

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-19

Итог по объекту считается вместе со статусами этапов и хранится в site_summaries.
stage_statuses.delay_open — отставание задано нижней границей («от N дней»).
Существующие объекты получат итог при ближайшем пересчёте.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "stage_statuses",
        sa.Column("delay_open", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_table(
        "site_summaries",
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("verdict", sa.String(length=24), nullable=False),
        sa.Column("delay_days_min", sa.Integer(), nullable=True),
        sa.Column("delay_days_max", sa.Integer(), nullable=True),
        sa.Column("stage_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_id"], ["schedule_stages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("site_id"),
    )


def downgrade() -> None:
    op.drop_table("site_summaries")
    op.drop_column("stage_statuses", "delay_open")
