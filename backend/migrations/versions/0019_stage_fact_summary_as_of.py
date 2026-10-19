"""stage_statuses.start_fact, marker_names; site_summaries.as_of

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-19

Для «Этапов» на обзоре, как в clean-mvp: факт по маркеру («с 09.09, идёт») и маркеры этапа
(техника, отличающая его от идущих одновременно); у итога — опорная дата («данные на»).
Существующие статусы получат поля при ближайшем пересчёте.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("stage_statuses", sa.Column("start_fact", sa.Date(), nullable=True))
    op.add_column("stage_statuses", sa.Column("marker_names", sa.JSON(), nullable=True))
    op.add_column("site_summaries", sa.Column("as_of", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("site_summaries", "as_of")
    op.drop_column("stage_statuses", "marker_names")
    op.drop_column("stage_statuses", "start_fact")
