"""schedules: добавить parse_method (чем разобран файл графика)

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-28

Импорт графика поддерживает три режима: встроенный парсер, LLM и авто. Что из этого
сработало на самом деле, сохраняем в schedules.parse_method ('builtin' | 'llm'),
чтобы интерфейс мог показать, что график разобран моделью и даты стоит проверить.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "schedules",
        sa.Column("parse_method", sa.String(length=16), nullable=False, server_default="builtin"),
    )


def downgrade() -> None:
    op.drop_column("schedules", "parse_method")
