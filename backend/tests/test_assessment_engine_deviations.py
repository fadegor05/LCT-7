"""Тесты двигателя расчёта отклонений от плана."""

import uuid
from datetime import date

from app.domains.assessment.engine import (
    EngineConfig,
    EquipmentRequirementInput,
    ObservationInput,
    ObservedEquipmentInput,
    RuleEngine,
    RuleInput,
    StageInput,
)
from app.domains.assessment.models import DeviationType, Severity
from app.domains.observation.models import Confidence


class TestDeviationStaleData:
    """Тесты отклонения stale_data."""

    def test_stale_data_no_observations(self):
        """Нет наблюдений вообще -> отклонения stale_data нет (данных нет, а не устарели)."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = []

        result = engine.compute_site(stages, rules, observations, today)

        # Пустая стройка: данных нет, а не устарели — отклонения нет
        stale = [d for d in result.deviations if d.type == DeviationType.STALE_DATA]
        assert stale == []

    def test_stale_data_observations_too_old(self):
        """Последнее наблюдение старше stale_data_days -> stale_data."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 2, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        # Последнее наблюдение больше 30 дней назад
        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 20),  # > 30 дней назад (31 день)
                photo_count=5,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=equipment_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                ],
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        stale = [d for d in result.deviations if d.type == DeviationType.STALE_DATA]
        assert len(stale) == 1
        assert stale[0].severity == Severity.CRITICAL


class TestDeviationMissingEquipment:
    """Тесты отклонения missing_equipment."""

    def test_missing_equipment_high_observability_no_marker(self):
        """Высокая наблюдаемость, маркер отсутствует -> missing_equipment."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[],  # Нет маркера при высокой наблюдаемости
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        missing = [d for d in result.deviations if d.type == DeviationType.MISSING_EQUIPMENT]
        assert len(missing) == 1
        deviation = missing[0]
        assert deviation.stage_id == stage_id
        assert deviation.severity == Severity.CRITICAL
        assert deviation.is_hypothesis is False
        assert deviation.confidence == Confidence.HIGH
        assert len(deviation.limits_text) > 0


class TestDeviationStageMismatch:
    """Тесты отклонения stage_mismatch."""

    def test_stage_mismatch_wrong_equipment_type(self):
        """Наблюдаемая техника не совпадает с требуемой -> stage_mismatch."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        expected_equipment_id = uuid.uuid4()
        observed_equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=expected_equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=observed_equipment_id,  # Другой тип
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                ],
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        mismatch = [d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH]
        assert len(mismatch) == 1
        deviation = mismatch[0]
        assert deviation.severity == Severity.CRITICAL
        assert deviation.is_hypothesis is False
        assert len(deviation.limits_text) > 0

    def test_stage_mismatch_uses_equipment_names_when_provided(self):
        """observed содержит переданное имя техники, а не UUID."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        expected_equipment_id = uuid.uuid4()
        observed_equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=expected_equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=observed_equipment_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                ],
            )
        ]

        equipment_names = {observed_equipment_id: "Самосвал"}

        result = engine.compute_site(stages, rules, observations, today, equipment_names)

        mismatch = [d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH]
        assert len(mismatch) == 1
        assert "Самосвал" in mismatch[0].observed
        assert str(observed_equipment_id) not in mismatch[0].observed

    def test_stage_mismatch_falls_back_to_uuid_without_names(self):
        """Без equipment_names (дефолт None) — поведение как раньше, UUID в тексте."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        expected_equipment_id = uuid.uuid4()
        observed_equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=expected_equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=observed_equipment_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                ],
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        mismatch = [d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH]
        assert len(mismatch) == 1
        assert str(observed_equipment_id) in mismatch[0].observed


class TestDeviationIdle:
    """Тесты отклонения idle."""

    def test_idle_equipment_hypothesis(self):
        """Техника присутствует с activity=idle -> idle, гипотеза, severity=ATTENTION."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=equipment_id,
                        count_min=1,
                        activity="idle",  # Простой
                        confidence="high",
                    )
                ],
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        idle = [d for d in result.deviations if d.type == DeviationType.IDLE]
        assert len(idle) == 1
        deviation = idle[0]
        assert deviation.severity == Severity.ATTENTION
        assert deviation.is_hypothesis is True
        assert deviation.confidence != Confidence.HIGH  # Гипотезы не могут быть HIGH
        assert len(deviation.limits_text) > 0


class TestDeviationExtraEquipment:
    """Тесты отклонения extra_equipment."""

    def test_extra_equipment_not_in_requirements(self):
        """Техника присутствует, но не в требованиях, маркер есть -> extra_equipment."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        marker_equipment_id = uuid.uuid4()
        extra_equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=marker_equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=marker_equipment_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    ),
                    ObservedEquipmentInput(
                        equipment_type_id=extra_equipment_id,  # Не в требованиях
                        count_min=1,
                        activity="works",
                        confidence="high",
                    ),
                ],
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        extra = [d for d in result.deviations if d.type == DeviationType.EXTRA_EQUIPMENT]
        assert len(extra) == 1
        deviation = extra[0]
        assert deviation.severity == Severity.ATTENTION
        assert deviation.is_hypothesis is True
        assert len(deviation.limits_text) > 0


class TestDeviationOutOfZone:
    """Тесты отклонения out_of_zone."""

    def test_out_of_zone_equipment(self):
        """Техника с in_zone=False -> out_of_zone."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=equipment_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                        in_zone=False,  # Вне зоны
                    )
                ],
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        out_zone = [d for d in result.deviations if d.type == DeviationType.OUT_OF_ZONE]
        assert len(out_zone) == 1
        deviation = out_zone[0]
        assert deviation.severity == Severity.ATTENTION
        assert deviation.is_hypothesis is True
        assert len(deviation.limits_text) > 0


class TestDeviationNoProgress:
    """Тесты отклонения no_progress."""

    def test_no_progress_identical_equipment_no_works(self):
        """Две последние наблюдения идентичны, нет activity=works -> no_progress."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 13),
                photo_count=5,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=equipment_id,
                        count_min=1,
                        activity="idle",
                        confidence="high",
                    )
                ],
            ),
            ObservationInput(
                observed_on=date(2024, 1, 18),  # 5 дней спустя (в окне no_progress_window_days=7)
                photo_count=5,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=equipment_id,
                        count_min=1,
                        activity="idle",  # То же состояние
                        confidence="high",
                    )
                ],
            ),
        ]

        result = engine.compute_site(stages, rules, observations, today)

        no_prog = [d for d in result.deviations if d.type == DeviationType.NO_PROGRESS]
        assert len(no_prog) == 1
        deviation = no_prog[0]
        assert deviation.severity == Severity.ATTENTION
        assert deviation.is_hypothesis is False
        assert deviation.confidence == Confidence.MEDIUM
        assert len(deviation.limits_text) > 0


class TestHypothesesNeverCritical:
    """Тесты: гипотезы никогда не имеют severity=CRITICAL."""

    def test_hypothesis_never_critical_idle(self):
        """Гипотеза (idle) не может быть CRITICAL."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=equipment_id,
                        count_min=1,
                        activity="idle",
                        confidence="high",
                    )
                ],
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        idle_devs = [d for d in result.deviations if d.type == DeviationType.IDLE]
        assert len(idle_devs) == 1
        assert idle_devs[0].is_hypothesis is True
        assert idle_devs[0].severity != Severity.CRITICAL


class TestLimitsTextNeverEmpty:
    """Тесты: limits_text всегда заполнен для всех типов отклонений."""

    def test_limits_text_present_for_all_deviations(self):
        """Все отклонения имеют непустой limits_text."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()
        extra_equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=equipment_id,
                        count_min=1,
                        activity="idle",
                        confidence="high",
                    ),
                    ObservedEquipmentInput(
                        equipment_type_id=extra_equipment_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    ),
                ],
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        for deviation in result.deviations:
            assert len(deviation.limits_text) > 0, (
                f"Отклонение {deviation.type} не имеет limits_text"
            )


class TestNotCheckedStageProducesNoDeviations:
    """Тесты: NOT_CHECKED этап не выдаёт отклонений."""

    def test_not_checked_stage_no_deviations(self):
        """Этап NOT_CHECKED не выдаёт missing_equipment и другие деления."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=False,  # NOT_CHECKED
                unverifiable_reason="Нет методики",
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=equipment_id,
                        obligation="normative",
                        min_count=1,
                    )
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[],  # Без маркера
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        # Не должно быть отклонений для этого этапа (кроме возможного stale_data)
        stage_deviations = [d for d in result.deviations if d.stage_id == stage_id]
        assert len(stage_deviations) == 0


class TestDeviationMissingLogicalEquipment:
    """Тесты отклонения missing_logical_equipment (LCT-15)."""

    def test_missing_logical_equipment_high_observability_absent(self):
        """Высокая наблюдаемость, logical-техника отсутствует -> предупреждение."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        marker_id = uuid.uuid4()
        logical_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=marker_id,
                        obligation="normative",
                        min_count=1,
                    ),
                    EquipmentRequirementInput(
                        equipment_type_id=logical_id,
                        obligation="logical",
                        min_count=1,
                    ),
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=marker_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                    # logical_id отсутствует
                ],
            )
        ]

        equipment_names = {marker_id: "Экскаватор", logical_id: "Самосвал"}

        result = engine.compute_site(stages, rules, observations, today, equipment_names)

        warnings = [
            d for d in result.deviations if d.type == DeviationType.MISSING_LOGICAL_EQUIPMENT
        ]
        assert len(warnings) == 1
        warning = warnings[0]
        assert warning.severity == Severity.ATTENTION
        assert warning.is_hypothesis is True
        assert "Самосвал" in warning.observed
        assert len(warning.limits_text) > 0

    def test_no_warning_when_logical_equipment_present(self):
        """Logical-техника присутствует -> предупреждения нет."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        marker_id = uuid.uuid4()
        logical_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=marker_id,
                        obligation="normative",
                        min_count=1,
                    ),
                    EquipmentRequirementInput(
                        equipment_type_id=logical_id,
                        obligation="logical",
                        min_count=1,
                    ),
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=marker_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    ),
                    ObservedEquipmentInput(
                        equipment_type_id=logical_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    ),
                ],
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        warnings = [
            d for d in result.deviations if d.type == DeviationType.MISSING_LOGICAL_EQUIPMENT
        ]
        assert len(warnings) == 0

    def test_no_warning_without_logical_requirements(self):
        """У правила нет logical-требований -> предупреждения не бывает."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        marker_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=marker_id,
                        obligation="normative",
                        min_count=1,
                    ),
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=marker_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    ),
                ],
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        warnings = [
            d for d in result.deviations if d.type == DeviationType.MISSING_LOGICAL_EQUIPMENT
        ]
        assert len(warnings) == 0

    def test_no_warning_low_observability(self):
        """Низкая наблюдаемость -> предупреждения по отсутствию не бывает
        (как и у missing_equipment — нельзя быть уверенным в отсутствии)."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        marker_id = uuid.uuid4()
        logical_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 10),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[
                    EquipmentRequirementInput(
                        equipment_type_id=marker_id,
                        obligation="normative",
                        min_count=1,
                    ),
                    EquipmentRequirementInput(
                        equipment_type_id=logical_id,
                        obligation="logical",
                        min_count=1,
                    ),
                ],
            )
        }

        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=10,
                observability="low",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=marker_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    ),
                ],
            )
        ]

        result = engine.compute_site(stages, rules, observations, today)

        warnings = [
            d for d in result.deviations if d.type == DeviationType.MISSING_LOGICAL_EQUIPMENT
        ]
        assert len(warnings) == 0


def _engine() -> RuleEngine:
    return RuleEngine(
        EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
    )


def _stage_and_rule(start: date, end: date, required_id: uuid.UUID):
    stage_id = uuid.uuid4()
    stage = StageInput(
        stage_id=stage_id, name="Этап", position=1, planned_start=start, planned_end=end
    )
    rule = RuleInput(
        stage_id=stage_id,
        rule_id=uuid.uuid4(),
        is_verifiable=True,
        unverifiable_reason=None,
        requirements=[
            EquipmentRequirementInput(
                equipment_type_id=required_id, obligation="normative", min_count=1
            )
        ],
    )
    return stage, rule


def _obs(on: date, equipment_id: uuid.UUID) -> ObservationInput:
    return ObservationInput(
        observed_on=on,
        photo_count=5,
        observability="high",
        equipment=[
            ObservedEquipmentInput(
                equipment_type_id=equipment_id, count_min=1, activity="works", confidence="high"
            )
        ],
    )


class TestBehindSchedule:
    """Отставание от графика попадает в список отклонений."""

    def test_behind_stage_produces_deviation_with_delay(self):
        required = uuid.uuid4()
        stage, rule = _stage_and_rule(date(2024, 1, 1), date(2024, 1, 10), required)
        result = _engine().compute_site(
            [stage],
            {stage.stage_id: rule},
            [_obs(date(2024, 1, 18), required)],
            date(2024, 1, 20),
        )
        behind = [d for d in result.deviations if d.type == DeviationType.BEHIND_SCHEDULE]
        assert len(behind) == 1
        assert behind[0].stage_id == stage.stage_id
        assert behind[0].severity == Severity.ATTENTION
        assert "10.01.2024" in behind[0].expected
        assert "10 дн." in behind[0].observed

    def test_on_track_stage_has_no_delay_deviation(self):
        required = uuid.uuid4()
        stage, rule = _stage_and_rule(date(2024, 1, 10), date(2024, 1, 25), required)
        result = _engine().compute_site(
            [stage],
            {stage.stage_id: rule},
            [_obs(date(2024, 1, 12), required)],
            date(2024, 1, 14),
        )
        assert not [d for d in result.deviations if d.type == DeviationType.BEHIND_SCHEDULE]


class TestStageMismatchScope:
    """Несоответствие этапу — только для этапа, который идёт в день снимка."""

    def test_finished_stage_gets_no_mismatch_from_later_photo(self):
        required, other = uuid.uuid4(), uuid.uuid4()
        past, past_rule = _stage_and_rule(date(2024, 1, 1), date(2024, 1, 5), required)
        current, current_rule = _stage_and_rule(date(2024, 1, 15), date(2024, 1, 25), required)
        result = _engine().compute_site(
            [past, current],
            {past.stage_id: past_rule, current.stage_id: current_rule},
            [_obs(date(2024, 1, 3), required), _obs(date(2024, 1, 18), other)],
            date(2024, 1, 20),
        )
        mismatch = [d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH]
        assert [d.stage_id for d in mismatch] == [current.stage_id]

    def test_expected_names_required_equipment(self):
        required, other = uuid.uuid4(), uuid.uuid4()
        stage, rule = _stage_and_rule(date(2024, 1, 10), date(2024, 1, 25), required)
        result = _engine().compute_site(
            [stage],
            {stage.stage_id: rule},
            [_obs(date(2024, 1, 18), other)],
            date(2024, 1, 20),
            {required: "Экскаватор", other: "Самосвал"},
        )
        mismatch = next(d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH)
        assert "Экскаватор" in mismatch.expected
        assert "Самосвал" in mismatch.observed
