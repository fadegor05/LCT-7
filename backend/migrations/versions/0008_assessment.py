"""assessment: расчёт статусов этапов и отклонений от плана

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-24

Таблицы stage_statuses, deviations, deviation_evidence, status_basis содержат
рассчитанные статусы этапов работ, обнаруженные отклонения от плана/методологии/наблюдений,
доказательства отклонений и наблюдения, послужившие основанием для статусов.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stage_statuses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("delay_days", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("confidence_reason", sa.Text(), nullable=True),
        sa.Column(
            "computed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["stage_id"], ["schedule_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stage_id", name="uq_stage_statuses_stage_id"),
    )
    op.create_index(op.f("ix_stage_statuses_stage_id"), "stage_statuses", ["stage_id"], unique=True)

    op.create_table(
        "deviations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("stage_id", sa.Uuid(), nullable=True),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("is_hypothesis", sa.Boolean(), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.String(length=16), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("expected", sa.Text(), nullable=False),
        sa.Column("observed", sa.Text(), nullable=False),
        sa.Column("limits_text", sa.Text(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["rule_id"], ["methodology_rules.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_id"], ["schedule_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_deviations_site_id"), "deviations", ["site_id"], unique=False)
    op.create_index(op.f("ix_deviations_stage_id"), "deviations", ["stage_id"], unique=False)

    op.create_table(
        "deviation_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("deviation_id", sa.Uuid(), nullable=False),
        sa.Column("photo_id", sa.Uuid(), nullable=False),
        sa.Column("detection_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["detection_id"], ["detections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deviation_id"], ["deviations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deviation_id",
            "photo_id",
            "detection_id",
            name="uq_deviation_evidence_dev_photo_detection",
        ),
    )
    op.create_index(
        op.f("ix_deviation_evidence_deviation_id"),
        "deviation_evidence",
        ["deviation_id"],
        unique=False,
    )

    op.create_table(
        "status_basis",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("status_id", sa.Uuid(), nullable=False),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["observation_id"], ["observations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["status_id"], ["stage_statuses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "status_id", "observation_id", name="uq_status_basis_status_observation"
        ),
    )
    op.create_index(
        op.f("ix_status_basis_status_id"),
        "status_basis",
        ["status_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_status_basis_status_id"), table_name="status_basis")
    op.drop_table("status_basis")
    op.drop_index(op.f("ix_deviation_evidence_deviation_id"), table_name="deviation_evidence")
    op.drop_table("deviation_evidence")
    op.drop_index(op.f("ix_deviations_stage_id"), table_name="deviations")
    op.drop_index(op.f("ix_deviations_site_id"), table_name="deviations")
    op.drop_table("deviations")
    op.drop_index(op.f("ix_stage_statuses_stage_id"), table_name="stage_statuses")
    op.drop_table("stage_statuses")
