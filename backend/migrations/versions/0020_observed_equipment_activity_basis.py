"""observed_equipment.activity_basis

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-19

Основание активности, как в clean-mvp: «Движение: машина сместилась между 10:05 и 10:15»,
«Зона: вне зоны». Активность теперь считается по серии кадров одной камеры за день, а не
по сдвигу между датами; существующие наблюдения получат основание при пересчёте.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("observed_equipment", sa.Column("activity_basis", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("observed_equipment", "activity_basis")
