"""equipment_types: добавить поле is_coarse для неопределённых типов техники

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-25

Таблица equipment_types получает новое логическое поле is_coarse, которое отмечает
"грубые" классы оборудования из ML-детектора (*_unknown), которые нельзя использовать
в требованиях методологии (только для хранения результатов детекции).
"""

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Добавляем столбец is_coarse
    op.add_column(
        "equipment_types",
        sa.Column("is_coarse", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Вставляем 5 новых coarse equipment
    equipment_types_table = sa.table(
        "equipment_types",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("title", sa.String()),
        sa.column("synonyms", sa.JSON()),
        sa.column("is_coarse", sa.Boolean()),
    )

    coarse_seed_data = [
        (
            uuid.uuid4(),
            "excavator_unknown",
            "Экскаватор (тип не определён)",
            [],
            True,
        ),
        (
            uuid.uuid4(),
            "crane_unknown",
            "Кран (тип не определён)",
            [],
            True,
        ),
        (
            uuid.uuid4(),
            "drilling_unknown",
            "Буровая техника (тип не определён)",
            [],
            True,
        ),
        (
            uuid.uuid4(),
            "truck_unknown",
            "Грузовик (тип не определён)",
            [],
            True,
        ),
        (
            uuid.uuid4(),
            "loader_unknown",
            "Погрузчик (тип не определён)",
            [],
            True,
        ),
    ]

    # CAST строки в JSON: один путь и для онлайн-режима, и для `alembic --sql`
    for item_id, code, title, synonyms, is_coarse in coarse_seed_data:
        op.execute(
            equipment_types_table.insert().values(
                id=item_id,
                code=code,
                title=title,
                synonyms=sa.cast(
                    sa.literal(json.dumps(synonyms, ensure_ascii=False), sa.String()), sa.JSON()
                ),
                is_coarse=is_coarse,
            )
        )


def downgrade() -> None:
    # Удаляем coarse equipment
    op.execute(
        sa.delete(sa.table("equipment_types", sa.column("code", sa.String()))).where(
            sa.column("code").in_(
                [
                    "excavator_unknown",
                    "crane_unknown",
                    "drilling_unknown",
                    "truck_unknown",
                    "loader_unknown",
                ]
            )
        )
    )

    # Удаляем столбец is_coarse
    op.drop_column("equipment_types", "is_coarse")
