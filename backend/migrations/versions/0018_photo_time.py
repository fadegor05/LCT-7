"""photos: время съёмки, подсказка даты, проверка серии штампов

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-19

Как в clean-mvp: у снимка — местное время съёмки (captured_at), а не только дата;
неуверенный штамп даёт подсказку для ручного ввода (date_hint) и время, которое может
подтвердить серия кадров камеры (uncertain_at); выбросы серии помечаются (time_check).
У снимков, загруженных раньше, поля пустые.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("photos", sa.Column("captured_at", sa.DateTime(), nullable=True))
    op.add_column("photos", sa.Column("date_hint", sa.Date(), nullable=True))
    op.add_column("photos", sa.Column("uncertain_at", sa.DateTime(), nullable=True))
    op.add_column("photos", sa.Column("time_check", sa.String(length=16), nullable=True))


def downgrade() -> None:
    for column in ("time_check", "uncertain_at", "date_hint", "captured_at"):
        op.drop_column("photos", column)
