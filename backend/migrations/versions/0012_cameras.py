"""cameras: камеры стройки и привязка фотографий к камере

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-18

Таблица cameras (камера объекта, рабочая зона-полигон, поля захвата кадров)
и необязательная колонка photos.camera_id. При удалении камеры фотографии остаются,
их camera_id обнуляется.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "cameras",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("stream_url", sa.String(length=500), nullable=True),
        sa.Column("capture_every_s", sa.Integer(), nullable=True),
        sa.Column("last_capture_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_capture_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_capture_error", sa.Text(), nullable=True),
        sa.Column("capture_failures", sa.Integer(), server_default="0", nullable=False),
        sa.Column("zone", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cameras_site_id"), "cameras", ["site_id"], unique=False)

    op.add_column("photos", sa.Column("camera_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_photos_camera_id"), "photos", ["camera_id"], unique=False)
    op.create_foreign_key(
        "fk_photos_camera_id_cameras",
        "photos",
        "cameras",
        ["camera_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_photos_camera_id_cameras", "photos", type_="foreignkey")
    op.drop_index(op.f("ix_photos_camera_id"), table_name="photos")
    op.drop_column("photos", "camera_id")

    op.drop_index(op.f("ix_cameras_site_id"), table_name="cameras")
    op.drop_table("cameras")
