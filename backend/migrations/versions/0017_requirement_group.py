"""equipment_requirements.group_code: группа взаимозаменяемой техники

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-19

Сваи подтверждает любая сваебойная машина (буровая, копёр, грейфер СВГ) — в базовой
методике это три набора. Для «Неполного комплекта» они — одна группа: нехватка, только
когда нет ни одной. У требований, заведённых раньше, группы нет.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "equipment_requirements", sa.Column("group_code", sa.String(length=32), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("equipment_requirements", "group_code")
