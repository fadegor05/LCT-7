"""sites.object_type, sites.workdays

Revision ID: 0023
Revises: 0022
Create Date: 2026-10-19

Тип объекта и рабочие дни объекта (clean-mvp, мастер стройки). Рабочие дни — вход движка:
в нерабочий день отсутствие техники не отклонение. По умолчанию пн–пт, как было в движке.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sites",
        sa.Column("object_type", sa.String(16), nullable=False, server_default="other"),
    )
    op.add_column(
        "sites",
        sa.Column(
            "workdays", sa.JSON(), nullable=False, server_default=sa.text("'[0, 1, 2, 3, 4]'")
        ),
    )


def downgrade() -> None:
    op.drop_column("sites", "workdays")
    op.drop_column("sites", "object_type")
