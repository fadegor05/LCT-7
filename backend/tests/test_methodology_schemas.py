"""Тесты для schemas.py: Pydantic v2 модели с валидаторами."""

import uuid
from datetime import datetime

import pytest
from pydantic import ValidationError

from app.domains.methodology.models import Obligation
from app.domains.methodology.schemas import (
    EquipmentTypeRead,
    RequirementIn,
    RequirementRead,
    RuleRead,
    RuleUpdate,
    SetRead,
    SetWrite,
)


class TestEquipmentTypeRead:
    """Тесты для EquipmentTypeRead."""

    def test_equipment_type_read_basic(self):
        """EquipmentTypeRead содержит id, code, title, synonyms."""
        eq = EquipmentTypeRead(
            id=uuid.uuid4(),
            code="excavator_crawler",
            title="Гусеничный экскаватор",
            synonyms=["экскаватор", "гусеница"],
        )
        assert eq.code == "excavator_crawler"
        assert eq.title == "Гусеничный экскаватор"
        assert eq.synonyms == ["экскаватор", "гусеница"]


class TestRequirementIn:
    """Тесты для RequirementIn."""

    def test_requirement_in_min_count_required_positive(self):
        """min_count должен быть >= 1."""
        with pytest.raises(ValidationError) as exc_info:
            RequirementIn(
                equipment_type_id=uuid.uuid4(),
                min_count=0,
                obligation=Obligation.NORMATIVE,
                gesn_code="GESN001",
            )
        errors = exc_info.value.errors()
        assert any("greater than or equal to 1" in str(e) for e in errors)

    def test_requirement_in_requires_source(self):
        """RequirementIn требует gesn_code ИЛИ source_note (не оба пусты)."""
        with pytest.raises(ValidationError) as exc_info:
            RequirementIn(
                equipment_type_id=uuid.uuid4(),
                min_count=1,
                obligation=Obligation.NORMATIVE,
                gesn_code=None,
                source_note=None,
            )
        errors = exc_info.value.errors()
        assert any("Either gesn_code or source_note" in str(e.get("msg", "")) for e in errors)

    def test_requirement_in_blank_source_treated_as_none(self):
        """Пустые/только пробелы строки в gesn_code и source_note нормализуются в None."""
        req = RequirementIn(
            equipment_type_id=uuid.uuid4(),
            min_count=1,
            obligation=Obligation.NORMATIVE,
            gesn_code="  ",
            source_note="VALID_NOTE",
        )
        assert req.gesn_code is None
        assert req.source_note == "VALID_NOTE"

    def test_requirement_in_gesn_code_only(self):
        """RequirementIn с только gesn_code валиден."""
        req = RequirementIn(
            equipment_type_id=uuid.uuid4(),
            min_count=1,
            obligation=Obligation.NORMATIVE,
            gesn_code="GESN001",
        )
        assert req.gesn_code == "GESN001"
        assert req.source_note is None

    def test_requirement_in_source_note_only(self):
        """RequirementIn с только source_note валиден."""
        req = RequirementIn(
            equipment_type_id=uuid.uuid4(),
            min_count=2,
            obligation=Obligation.LOGICAL,
            source_note="по смыслу работы",
        )
        assert req.source_note == "по смыслу работы"
        assert req.gesn_code is None

    def test_requirement_in_obligation_values(self):
        """RequirementIn принимает все значения Obligation."""
        for obligation in [Obligation.NORMATIVE, Obligation.LOGICAL, Obligation.AUXILIARY]:
            req = RequirementIn(
                equipment_type_id=uuid.uuid4(),
                min_count=1,
                obligation=obligation,
                gesn_code="GESN001",
            )
            assert req.obligation == obligation


class TestSetWrite:
    """Тесты для SetWrite."""

    def test_set_write_requires_min_one_requirement(self):
        """SetWrite требует min_length=1."""
        with pytest.raises(ValidationError) as exc_info:
            SetWrite(requirements=[])
        errors = exc_info.value.errors()
        assert any("at least 1" in str(e) for e in errors)

    def test_set_write_with_one_requirement(self):
        """SetWrite с одним требованием валиден."""
        set_write = SetWrite(
            requirements=[
                RequirementIn(
                    equipment_type_id=uuid.uuid4(),
                    min_count=1,
                    obligation=Obligation.NORMATIVE,
                    gesn_code="GESN001",
                )
            ]
        )
        assert len(set_write.requirements) == 1

    def test_set_write_with_multiple_requirements(self):
        """SetWrite может содержать несколько требований."""
        set_write = SetWrite(
            requirements=[
                RequirementIn(
                    equipment_type_id=uuid.uuid4(),
                    min_count=1,
                    obligation=Obligation.NORMATIVE,
                    gesn_code="GESN001",
                ),
                RequirementIn(
                    equipment_type_id=uuid.uuid4(),
                    min_count=2,
                    obligation=Obligation.LOGICAL,
                    source_note="по смыслу",
                ),
            ]
        )
        assert len(set_write.requirements) == 2


class TestRuleUpdate:
    """Тесты для RuleUpdate."""

    def test_rule_update_is_verifiable_true_clears_reason(self):
        """Если is_verifiable=True, reason обнуляется."""
        rule = RuleUpdate(is_verifiable=True, unverifiable_reason="не нужно")
        assert rule.is_verifiable is True
        assert rule.unverifiable_reason is None

    def test_rule_update_is_verifiable_false_requires_reason(self):
        """Если is_verifiable=False, reason должна быть непуста."""
        with pytest.raises(ValidationError) as exc_info:
            RuleUpdate(is_verifiable=False, unverifiable_reason=None)
        errors = exc_info.value.errors()
        assert any("reason must be non-empty" in str(e) for e in errors)

    def test_rule_update_is_verifiable_false_blank_reason_fails(self):
        """Если is_verifiable=False и reason только пробелы, валидация падает."""
        with pytest.raises(ValidationError) as exc_info:
            RuleUpdate(is_verifiable=False, unverifiable_reason="   ")
        errors = exc_info.value.errors()
        assert any("reason must be non-empty" in str(e) for e in errors)

    def test_rule_update_is_verifiable_false_with_reason(self):
        """Если is_verifiable=False с валидной reason, модель валидна."""
        rule = RuleUpdate(is_verifiable=False, unverifiable_reason="стадия отсутствует")
        assert rule.is_verifiable is False
        assert rule.unverifiable_reason == "стадия отсутствует"


class TestRequirementRead:
    """Тесты для RequirementRead."""

    def test_requirement_read_basic(self):
        """RequirementRead содержит основные поля: id, equipment_type, min_count и др."""
        eq_type = EquipmentTypeRead(
            id=uuid.uuid4(),
            code="excavator_crawler",
            title="Гусеничный экскаватор",
            synonyms=[],
        )
        req = RequirementRead(
            id=uuid.uuid4(),
            equipment_type=eq_type,
            min_count=1,
            obligation=Obligation.NORMATIVE,
            gesn_code="GESN001",
            source_note=None,
        )
        assert req.equipment_type.code == "excavator_crawler"
        assert req.min_count == 1
        assert req.obligation == Obligation.NORMATIVE


class TestSetRead:
    """Тесты для SetRead."""

    def test_set_read_basic(self):
        """SetRead содержит id, position, requirements."""
        eq_type = EquipmentTypeRead(
            id=uuid.uuid4(),
            code="excavator_crawler",
            title="Гусеничный экскаватор",
            synonyms=[],
        )
        req = RequirementRead(
            id=uuid.uuid4(),
            equipment_type=eq_type,
            min_count=1,
            obligation=Obligation.NORMATIVE,
            gesn_code="GESN001",
            source_note=None,
        )
        set_read = SetRead(id=uuid.uuid4(), position=1, requirements=[req])
        assert set_read.position == 1
        assert len(set_read.requirements) == 1


class TestRuleRead:
    """Тесты для RuleRead."""

    def test_rule_read_basic(self):
        """RuleRead содержит основные поля: id, stage_id, is_verifiable, sets и др."""
        rule = RuleRead(
            id=uuid.uuid4(),
            stage_id=uuid.uuid4(),
            stage_name="Foundation Work",
            is_verifiable=True,
            unverifiable_reason=None,
            updated_at=datetime.now(),
            sets=[],
        )
        assert rule.is_verifiable is True
        assert rule.unverifiable_reason is None
        assert rule.sets == []

    def test_rule_read_stage_id_none(self):
        """RuleRead может иметь stage_id=None (базовое правило)."""
        rule = RuleRead(
            id=uuid.uuid4(),
            stage_id=None,
            stage_name=None,
            is_verifiable=False,
            unverifiable_reason="на основе ключевого слова",
            updated_at=datetime.now(),
            sets=[],
        )
        assert rule.stage_id is None
        assert rule.stage_name is None
