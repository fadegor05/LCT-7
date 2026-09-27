"""sites: объекты строительства с владельцем

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-24

Таблица sites содержит объекты строительства, принадлежащие пользователям.
Каждый сайт имеет owner_id как FK на app_user.id.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sites",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["app_user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sites_owner_id"), "sites", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_sites_owner_id"), table_name="sites")
    op.drop_table("sites")
