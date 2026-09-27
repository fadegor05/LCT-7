"""photo: таблицы фотографий и детекций

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-24

Таблицы photos, detections содержат фотографии с объекта строительства
и результаты детекции оборудования на них.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "photos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_name", sa.String(length=255), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("captured_on", sa.Date(), nullable=True),
        sa.Column("date_source", sa.String(length=16), nullable=True),
        sa.Column(
            "processing_status",
            sa.String(length=16),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_photos_site_id"), "photos", ["site_id"], unique=False)
    op.create_index(
        "ix_photos_site_id_captured_on", "photos", ["site_id", "captured_on"], unique=False
    )

    op.create_table(
        "detections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("photo_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_type_id", sa.Uuid(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["equipment_type_id"], ["equipment_types.id"]),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_detections_equipment_type_id"), "detections", ["equipment_type_id"], unique=False
    )
    op.create_index(op.f("ix_detections_photo_id"), "detections", ["photo_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_detections_photo_id"), table_name="detections")
    op.drop_index(op.f("ix_detections_equipment_type_id"), table_name="detections")
    op.drop_table("detections")
    op.drop_index("ix_photos_site_id_captured_on", table_name="photos")
    op.drop_index(op.f("ix_photos_site_id"), table_name="photos")
    op.drop_table("photos")
