"""hypothesis_decisions: решение инженера по гипотезе

Revision ID: 0024
Revises: 0023
Create Date: 2026-10-19

Как в clean-mvp (§8.8): инженер подтверждает гипотезу или отклоняет её. Строки deviations
пересоздаёт каждый пересчёт, поэтому решение хранится по устойчивому ключу «тип:этап:машина».
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "hypothesis_decisions",
        sa.Column(
            "site_id", sa.Uuid(), sa.ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True
        ),
        sa.Column("deviation_key", sa.String(120), primary_key=True),
        sa.Column("decision", sa.String(16), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "decided_by",
            sa.Uuid(),
            sa.ForeignKey("app_user.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decided_by_name", sa.String(255), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("hypothesis_decisions")
