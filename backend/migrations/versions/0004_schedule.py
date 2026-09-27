"""schedule: таблицы графика выполнения работ

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-24

Таблицы schedules, schedule_stages, schedule_import_issues содержат графики выполнения
работ и связанную информацию об импорте из файлов XLSX.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("rows_total", sa.Integer(), nullable=True),
        sa.Column("rows_parsed", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id"),
    )
    op.create_index(op.f("ix_schedules_site_id"), "schedules", ["site_id"], unique=False)

    op.create_table(
        "schedule_stages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_end", sa.Date(), nullable=True),
        sa.Column("dates_source", sa.String(length=16), server_default="file", nullable=False),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_schedule_stages_schedule_id"), "schedule_stages", ["schedule_id"], unique=False
    )

    op.create_table(
        "schedule_import_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("schedule_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("raw_row", sa.Text(), nullable=False),
        sa.Column("reason", sa.String(length=500), nullable=False),
        sa.ForeignKeyConstraint(["schedule_id"], ["schedules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_schedule_import_issues_schedule_id"),
        "schedule_import_issues",
        ["schedule_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_schedule_import_issues_schedule_id"), table_name="schedule_import_issues"
    )
    op.drop_table("schedule_import_issues")
    op.drop_index(op.f("ix_schedule_stages_schedule_id"), table_name="schedule_stages")
    op.drop_table("schedule_stages")
    op.drop_index(op.f("ix_schedules_site_id"), table_name="schedules")
    op.drop_table("schedules")
