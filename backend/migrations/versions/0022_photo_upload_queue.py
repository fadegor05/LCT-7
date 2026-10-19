"""photos: фоновая обработка загрузки — пачка и место в ней, индекс по статусу

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-19

Загрузка больше не ждёт штамп и детектор: кадр принимается со статусом queued, фоновый
обработчик ставит дату и технику. upload_batch_id и upload_batch_pos держат пачку до конца
обработки — по ним ставится дата по соседям в исходном порядке.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("photos", sa.Column("upload_batch_id", sa.Uuid(), nullable=True))
    op.add_column("photos", sa.Column("upload_batch_pos", sa.Integer(), nullable=True))
    op.create_index("ix_photos_upload_batch_id", "photos", ["upload_batch_id"])
    op.create_index("ix_photos_processing_status", "photos", ["processing_status"])


def downgrade() -> None:
    op.drop_index("ix_photos_processing_status", table_name="photos")
    op.drop_index("ix_photos_upload_batch_id", table_name="photos")
    op.drop_column("photos", "upload_batch_pos")
    op.drop_column("photos", "upload_batch_id")
