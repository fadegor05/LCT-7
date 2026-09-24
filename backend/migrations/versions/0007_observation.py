"""observation: таблицы наблюдений по стройке

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-24

Таблицы observations, observed_equipment содержат сведённые по дате
наблюдения за стройкой и зафиксированную в них технику.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("observed_on", sa.Date(), nullable=False),
        sa.Column("photo_count", sa.Integer(), nullable=False),
        sa.Column("observability", sa.String(length=16), nullable=False),
        sa.Column("observability_notes", sa.Text(), nullable=True),
        sa.Column(
            "recomputed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "observed_on", name="uq_observations_site_date"),
    )
    op.create_index(op.f("ix_observations_site_id"), "observations", ["site_id"], unique=False)

    op.create_table(
        "observed_equipment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_type_id", sa.Uuid(), nullable=False),
        sa.Column("count_min", sa.Integer(), nullable=False),
        sa.Column("activity", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(["observation_id"], ["observations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["equipment_type_id"], ["equipment_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "observation_id", "equipment_type_id", name="uq_observed_equipment_obs_type"
        ),
        sa.CheckConstraint("count_min >= 1", name="ck_observed_equipment_count_min"),
    )
    op.create_index(
        op.f("ix_observed_equipment_observation_id"),
        "observed_equipment",
        ["observation_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_observed_equipment_observation_id"), table_name="observed_equipment")
    op.drop_table("observed_equipment")
    op.drop_index(op.f("ix_observations_site_id"), table_name="observations")
    op.drop_table("observations")
