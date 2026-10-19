"""schedule_stages.work_names: названия работ этапа из графика

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-19

Этап графика собирается из работ одного пункта («4.1», «4.2»). Их названия нужны базовой
методике: комплект общего этапа («Работы по устройству котельной») подбирается по работам.
У этапов, импортированных раньше, колонка пустая — подбор по названию этапа, как раньше.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("schedule_stages", sa.Column("work_names", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("schedule_stages", "work_names")
