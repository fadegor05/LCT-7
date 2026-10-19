"""Тесты для defaults.py: DEFAULT_RULES, DefaultRuleSet, match_stage."""

from app.domains.methodology.defaults import DefaultRuleSet
from app.domains.methodology.models import Obligation
from app.domains.methodology.seed import EQUIPMENT_SEED


class TestDefaultRulesStructure:
    """Проверки структуры DEFAULT_RULES."""

    def test_all_equipment_codes_exist_in_seed(self):
        """Все коды оборудования в DEFAULT_RULES существуют в EQUIPMENT_SEED."""
        rule_set = DefaultRuleSet()
        seed_codes = {item["code"] for item in EQUIPMENT_SEED}

        for rule in rule_set.rules:
            for requirement_set in rule.sets:
                for req in requirement_set:
                    assert req.equipment_code in seed_codes, (
                        f"Код {req.equipment_code} не найден в EQUIPMENT_SEED"
                    )

    def test_default_rules_never_reference_coarse_codes(self):
        """DEFAULT_RULES никогда не ссылаются на grubые коды оборудования."""
        rule_set = DefaultRuleSet()
        coarse_codes = {item["code"] for item in EQUIPMENT_SEED if item.get("is_coarse", False)}

        for rule in rule_set.rules:
            for requirement_set in rule.sets:
                for req in requirement_set:
                    assert req.equipment_code not in coarse_codes, (
                        f"Правило {rule.stage_key} ссылается на grubый код {req.equipment_code}"
                    )

    def test_every_set_has_at_least_one_normative(self):
        """Каждый набор требований содержит хотя бы одно нормативное требование."""
        rule_set = DefaultRuleSet()

        for rule in rule_set.rules:
            for idx, requirement_set in enumerate(rule.sets):
                normative_count = sum(
                    1 for req in requirement_set if req.obligation == Obligation.NORMATIVE
                )
                assert normative_count >= 1, (
                    f"Правило {rule.stage_key}, набор {idx}: нет нормативных требований"
                )

    def test_every_requirement_has_source(self):
        """Каждое требование имеет gesn_code ИЛИ source_note (оба не пусты одновременно нельзя)."""
        rule_set = DefaultRuleSet()

        for rule in rule_set.rules:
            for requirement_set in rule.sets:
                for req in requirement_set:
                    has_gesn = req.gesn_code is not None and req.gesn_code.strip()
                    has_note = req.source_note is not None and req.source_note.strip()
                    assert has_gesn or has_note, (
                        f"Требование {req.equipment_code} в правиле {rule.stage_key}: "
                        f"нет gesn_code и source_note"
                    )

    def test_stage_keys_are_unique(self):
        """Все stage_key в DEFAULT_RULES уникальны."""
        rule_set = DefaultRuleSet()
        stage_keys = [rule.stage_key for rule in rule_set.rules]
        assert len(stage_keys) == len(set(stage_keys)), "stage_key должны быть уникальны"

    def test_keywords_are_lowercase(self):
        """Все ключевые слова в нижнем регистре."""
        rule_set = DefaultRuleSet()

        for rule in rule_set.rules:
            for keyword in rule.name_keywords:
                assert keyword == keyword.lower(), (
                    f"Ключевое слово '{keyword}' в правиле {rule.stage_key} не в нижнем регистре"
                )

    def test_piles_rule_each_set_has_exactly_one_normative(self):
        """Правило 'piles': каждый набор имеет ровно одно нормативное требование.

        Нормативное требование — специфичная машина метода:
        - Набор 1 (буровая установка): drilling_rig NORMATIVE
        - Набор 2 (копёр): pile_driver NORMATIVE
        """
        rule_set = DefaultRuleSet()
        piles_rule = next((rule for rule in rule_set.rules if rule.stage_key == "piles"), None)
        assert piles_rule is not None, "Правило 'piles' не найдено"

        # Проверить, что drilling_rig и pile_driver — нормативные
        set_1_normative = [
            req.equipment_code
            for req in piles_rule.sets[0]
            if req.obligation == Obligation.NORMATIVE
        ]
        set_2_normative = [
            req.equipment_code
            for req in piles_rule.sets[1]
            if req.obligation == Obligation.NORMATIVE
        ]

        assert set_1_normative == ["drilling_rig"], (
            f"Набор 1: ожидается ['drilling_rig'], получено {set_1_normative}"
        )
        assert set_2_normative == ["pile_driver"], (
            f"Набор 2: ожидается ['pile_driver'], получено {set_2_normative}"
        )


class TestDefaultRuleSetMatchStage:
    """Тесты для метода match_stage."""

    def test_match_piles_stage(self):
        """'Устройство свай' -> 'piles'."""
        rule_set = DefaultRuleSet()
        matched = rule_set.match_stage("Устройство свай")
        assert matched is not None
        assert matched.stage_key == "piles"

    def test_match_enclosure_stage_priority(self):
        """'Шпунтовое ограждение котлована' -> 'enclosure' (не 'excavation')."""
        rule_set = DefaultRuleSet()
        matched = rule_set.match_stage("Шпунтовое ограждение котлована")
        assert matched is not None
        assert matched.stage_key == "enclosure", "Должно совпадать с 'enclosure', не 'excavation'"

    def test_match_excavation_stage(self):
        """'Разработка котлована' -> 'excavation'."""
        rule_set = DefaultRuleSet()
        matched = rule_set.match_stage("Разработка котлована")
        assert matched is not None
        assert matched.stage_key == "excavation"

    def test_no_match_returns_none(self):
        """Работ без крупной техники в семействах нет -> None."""
        rule_set = DefaultRuleSet()
        assert rule_set.match_stage("Внутренние отделочные работы") is None

    def test_facade_is_matched_as_not_checked(self):
        """Фасад узнаётся, но по технике не проверяется — с причиной (как в clean-mvp)."""
        matched = DefaultRuleSet().match_stage("Отделка фасада")
        assert matched is not None and matched.stage_key == "facade"
        assert matched.sets == ()
        assert matched.unchecked_reason

    def test_match_case_insensitive(self):
        """Совпадение работает без учёта регистра."""
        rule_set = DefaultRuleSet()
        matched = rule_set.match_stage("УСТРОЙСТВО СВАЙ")
        assert matched is not None
        assert matched.stage_key == "piles"

    def test_match_earthworks_stage(self):
        """'Обратная засыпка' -> 'earthworks'; общие «Земляные работы» — котлован, как в clean."""
        rule_set = DefaultRuleSet()
        matched = rule_set.match_stage("Обратная засыпка пазух")
        assert matched is not None
        assert matched.stage_key == "earthworks"
        assert rule_set.match_stage("Земляные работы").stage_key == "excavation"

    def test_match_monolith_stage(self):
        """'Монолитные работы ниже нуля' -> 'monolith'."""
        rule_set = DefaultRuleSet()
        matched = rule_set.match_stage("Монолитные работы ниже нуля")
        assert matched is not None
        assert matched.stage_key == "monolith"

    def test_match_frame_stage(self):
        """'Возведение каркаса' -> 'frame'."""
        rule_set = DefaultRuleSet()
        matched = rule_set.match_stage("Возведение каркаса")
        assert matched is not None
        assert matched.stage_key == "frame"


def test_general_stage_is_matched_by_its_works() -> None:
    """Общее название этапа — семейство по работам: котельная с фундаментом (clean-mvp)."""
    rules = DefaultRuleSet()
    found = rules.match_stage_or_works(
        "Работы по устройству котельной", ["Устройство фундамента", "Монтаж дымовой трубы"]
    )
    assert found is not None and found.stage_key == "monolith"
    # Название этапа важнее работ
    assert rules.match_stage_or_works("Устройство свай", ["Устройство фундамента"]).stage_key == (
        "piles"
    )
    assert rules.match_stage_or_works("Строительные работы", None) is None
