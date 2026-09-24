"""methodology: таблицы методологии проверки оборудования

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-24

Таблицы equipment_types, methodology_rules, equipment_sets, equipment_requirements содержат
информацию о типах оборудования, правилах проверки и требованиях к оборудованию для этапов работ.
"""

import json
import uuid
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "equipment_types",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("synonyms", sa.JSON(), nullable=False, server_default="[]"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_equipment_types_code"), "equipment_types", ["code"], unique=False)

    op.create_table(
        "methodology_rules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("site_id", sa.Uuid(), nullable=True),
        sa.Column("stage_id", sa.Uuid(), nullable=True),
        sa.Column("stage_key", sa.String(length=64), nullable=True),
        sa.Column("is_verifiable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("unverifiable_reason", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "is_verifiable OR unverifiable_reason IS NOT NULL",
            name="ck_methodology_rules_reason",
        ),
        sa.CheckConstraint(
            "(site_id IS NULL AND stage_key IS NOT NULL) "
            "OR (site_id IS NOT NULL AND stage_id IS NOT NULL)",
            name="ck_methodology_rules_scope",
        ),
        sa.ForeignKeyConstraint(["site_id"], ["sites.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["stage_id"], ["schedule_stages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("site_id", "stage_id", name="uq_methodology_rules_site_stage"),
    )
    op.create_index(
        op.f("ix_methodology_rules_site_id"), "methodology_rules", ["site_id"], unique=False
    )
    op.create_index(
        op.f("ix_methodology_rules_stage_id"), "methodology_rules", ["stage_id"], unique=False
    )

    op.create_table(
        "equipment_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["methodology_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_equipment_sets_rule_id"), "equipment_sets", ["rule_id"], unique=False)

    op.create_table(
        "equipment_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("set_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_type_id", sa.Uuid(), nullable=False),
        sa.Column("min_count", sa.Integer(), nullable=False, server_default=sa.literal(1)),
        sa.Column("obligation", sa.String(length=16), nullable=False),
        sa.Column("gesn_code", sa.String(length=64), nullable=True),
        sa.Column("source_note", sa.String(length=500), nullable=True),
        sa.CheckConstraint("min_count >= 1", name="ck_equipment_requirements_min_count"),
        sa.CheckConstraint(
            "gesn_code IS NOT NULL OR source_note IS NOT NULL",
            name="ck_equipment_requirements_source",
        ),
        sa.ForeignKeyConstraint(["equipment_type_id"], ["equipment_types.id"]),
        sa.ForeignKeyConstraint(["set_id"], ["equipment_sets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_equipment_requirements_set_id"),
        "equipment_requirements",
        ["set_id"],
        unique=False,
    )

    # Bulk insert seed data into equipment_types
    seed_data = [
        (
            "excavator_crawler",
            "Гусеничный экскаватор",
            ["экскаватор-гусеница", "гусеничный экскаватор"],
        ),
        (
            "excavator_wheeled",
            "Колёсный экскаватор",
            ["экскаватор на колёсах", "колёсный экскаватор"],
        ),
        ("backhoe_loader", "Экскаватор-погрузчик", ["экскаватор-погрузчик", "backhoe"]),
        ("tower_crane", "Башенный кран", ["кран башенный", "tower crane"]),
        ("truck_crane", "Автокран", ["кран на автомобиле", "кран грузовой", "truck crane"]),
        (
            "crawler_crane",
            "Гусеничный кран",
            ["кран гусеничный", "гусеничный кран", "crawler crane"],
        ),
        ("loader_crane", "Кран-манипулятор", ["манипулятор", "кран-манипулятор", "loader crane"]),
        (
            "drilling_rig",
            "Буровая установка",
            ["буровая машина", "буровая установка", "drilling rig"],
        ),
        ("pile_driver", "Копёр / вибропогружатель", ["копёр", "вибропогружатель", "pile driver"]),
        (
            "dwall_rig",
            "Грейфер / гидрофреза СВГ",
            ["грейфер", "гидрофреза", "гидрофреза СВГ", "dwall rig"],
        ),
        ("dump_truck", "Самосвал", ["самосвал", "dump truck", "грузовик"]),
        (
            "concrete_mixer",
            "Автобетоносмеситель",
            ["бетоносмеситель", "автобетоносмеситель", "concrete mixer"],
        ),
        ("concrete_pump", "Автобетононасос", ["бетононасос", "автобетононасос", "concrete pump"]),
        (
            "flatbed_truck",
            "Бортовой грузовик / трал",
            ["бортовик", "трал", "бортовой грузовик", "flatbed truck"],
        ),
        ("bulldozer", "Бульдозер", ["бульдозер", "bulldozer"]),
        ("roller", "Каток", ["каток", "каток уплотняющий", "roller"]),
        ("grader", "Автогрейдер", ["грейдер", "автогрейдер", "grader"]),
        ("paver", "Асфальтоукладчик", ["асфальтоукладчик", "асфальтник", "paver"]),
        (
            "wheel_loader",
            "Фронтальный погрузчик",
            ["погрузчик колёсный", "фронтальный погрузчик", "wheel loader"],
        ),
        (
            "telehandler",
            "Телескопический погрузчик",
            ["телескопический погрузчик", "телеман", "telehandler"],
        ),
    ]

    for code, title, synonyms in seed_data:
        eq_id = str(uuid.uuid4())
        synonyms_json = json.dumps(synonyms, ensure_ascii=False)
        op.execute(
            f"INSERT INTO equipment_types (id, code, title, synonyms) "
            f"VALUES ('{eq_id}', '{code}', \"{title.replace('"', '"')}\", '{synonyms_json}')"
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_equipment_requirements_set_id"), table_name="equipment_requirements")
    op.drop_table("equipment_requirements")
    op.drop_index(op.f("ix_equipment_sets_rule_id"), table_name="equipment_sets")
    op.drop_table("equipment_sets")
    op.drop_index(op.f("ix_methodology_rules_stage_id"), table_name="methodology_rules")
    op.drop_index(op.f("ix_methodology_rules_site_id"), table_name="methodology_rules")
    op.drop_table("methodology_rules")
    op.drop_index(op.f("ix_equipment_types_code"), table_name="equipment_types")
    op.drop_table("equipment_types")
