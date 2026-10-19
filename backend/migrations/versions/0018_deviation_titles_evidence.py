"""deviations.title, equipment_type_id, cause_stage_id; deviation_evidence.caption

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-19

Как в clean-mvp: у отклонения — короткий заголовок по машине, сама машина (доказательства
— кадры с её рамкой) и возможная причина (отстающий этап); у снимка-доказательства —
подпись. Существующие отклонения получат поля при ближайшем пересчёте.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("deviations", sa.Column("title", sa.String(length=300), nullable=True))
    op.add_column("deviations", sa.Column("equipment_type_id", sa.Uuid(), nullable=True))
    op.add_column("deviations", sa.Column("cause_stage_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_deviations_cause_stage",
        "deviations",
        "schedule_stages",
        ["cause_stage_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("deviation_evidence", sa.Column("caption", sa.String(length=300), nullable=True))


def downgrade() -> None:
    op.drop_column("deviation_evidence", "caption")
    op.drop_constraint("fk_deviations_cause_stage", "deviations", type_="foreignkey")
    for column in ("cause_stage_id", "equipment_type_id", "title"):
        op.drop_column("deviations", column)
