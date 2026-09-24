"""Тесты двигателя расчёта статусов этапов."""

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
from app.domains.assessment.models import StageStatusValue
from app.domains.observation.models import Confidence


class TestStageStatusAhead:
    """Тесты статуса AHEAD (маркер раньше планового начала с допуском)."""

    def test_ahead_marker_before_planned_start(self):
        """Маркер раньше planned_start - tolerance -> AHEAD."""
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
                planned_start=date(2024, 1, 15),
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

        # Маркер раньше planned_start
        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 8),  # До 1/15 - 5 дней = 1/10
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

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.stage_id == stage_id
        assert status.status == StageStatusValue.AHEAD
        assert status.delay_days == (date(2024, 1, 15) - date(2024, 1, 8)).days
        # Только 1 маркер-дата, но min_confirming_observations=2, поэтому MEDIUM
        assert status.confidence == Confidence.MEDIUM


class TestStageStatusOnTrack:
    """Тесты статуса ON_TRACK (маркер в плановом окне)."""

    def test_on_track_marker_in_window(self):
        """Маркер в плановом окне с допуском -> ON_TRACK."""
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
                planned_start=date(2024, 1, 15),
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

        # Маркер в окне
        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 16),  # В окне [1/10, 1/30]
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

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.status == StageStatusValue.ON_TRACK
        assert status.delay_days is None


class TestStageStatusBehindStartShift:
    """Тесты статуса BEHIND (маркер после planned_start + tolerance)."""

    def test_behind_start_shift(self):
        """Маркер после planned_start + tolerance -> BEHIND."""
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
                planned_start=date(2024, 1, 15),
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

        # Маркер после 1/15 + 5 дней = 1/20
        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 22),
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

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.status == StageStatusValue.BEHIND
        assert status.delay_days == (date(2024, 1, 22) - date(2024, 1, 15)).days


class TestStageStatusBehindEndPassed:
    """Тесты статуса BEHIND (конец прошёл + tolerance, маркер ещё активен)."""

    def test_behind_end_passed_markers_active(self):
        """Плановый конец прошёл + tolerance, маркер в latest obs -> BEHIND."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 31)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 15),
                planned_end=date(2024, 1, 20),
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
                observed_on=date(2024, 1, 30),  # Latest, маркер актуален
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

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.status == StageStatusValue.BEHIND
        assert status.delay_days == (today - date(2024, 1, 20)).days


class TestStageStatusNotStarted:
    """Тесты статуса NOT_STARTED (маркеры не видны, высокая наблюдаемость)."""

    def test_not_started_high_observability(self):
        """Маркеры не видны, высокая наблюдаемость всего окна -> NOT_STARTED."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 25)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 15),
                planned_end=date(2024, 1, 30),
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

        # Наблюдения с высокой observability, но без маркера
        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 16),
                photo_count=10,  # Высокая наблюдаемость
                observability="high",
                equipment=[],  # Нет маркера
            ),
            ObservationInput(
                observed_on=date(2024, 1, 20),
                photo_count=10,
                observability="high",
                equipment=[],
            ),
        ]

        result = engine.compute_site(stages, rules, observations, today)

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.status == StageStatusValue.NOT_STARTED
        assert status.confidence == Confidence.HIGH


class TestStageStatusNotObserved:
    """Тесты статуса NOT_OBSERVED (низкая наблюдаемость или нет наблюдений)."""

    def test_not_observed_low_observability(self):
        """Маркеры не видны, низкая наблюдаемость -> NOT_OBSERVED."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 25)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 15),
                planned_end=date(2024, 1, 30),
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
                observed_on=date(2024, 1, 16),
                photo_count=1,  # Низкая наблюдаемость
                observability="low",
                equipment=[],
            ),
        ]

        result = engine.compute_site(stages, rules, observations, today)

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.status == StageStatusValue.NOT_OBSERVED
        # Есть наблюдение в окне, но низкая наблюдаемость -> MEDIUM
        assert status.confidence == Confidence.MEDIUM

    def test_not_observed_no_observations(self):
        """Наблюдений нет -> NOT_OBSERVED."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 25)
        stage_id = uuid.uuid4()
        rule_id = uuid.uuid4()
        equipment_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 15),
                planned_end=date(2024, 1, 30),
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

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.status == StageStatusValue.NOT_OBSERVED
        assert status.confidence == Confidence.LOW


class TestStageStatusNotChecked:
    """Тесты статуса NOT_CHECKED (правило отсутствует, не проверяемо или нет маркеров)."""

    def test_not_checked_no_rule(self):
        """Нет правила для этапа -> NOT_CHECKED."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
        engine = RuleEngine(config)

        today = date(2024, 1, 20)
        stage_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 15),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {}  # Нет правила

        observations = []

        result = engine.compute_site(stages, rules, observations, today)

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.status == StageStatusValue.NOT_CHECKED
        assert status.delay_days is None
        assert status.confidence == Confidence.LOW
        assert (
            "не сопоставлен" in status.confidence_reason or "методикой" in status.confidence_reason
        )

    def test_not_checked_not_verifiable(self):
        """Правило с is_verifiable=False -> NOT_CHECKED."""
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

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Foundation",
                position=1,
                planned_start=date(2024, 1, 15),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=False,
                unverifiable_reason="Нет методики",
                requirements=[],
            )
        }

        observations = []

        result = engine.compute_site(stages, rules, observations, today)

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.status == StageStatusValue.NOT_CHECKED
        assert status.confidence_reason == "Нет методики"

    def test_not_checked_no_normative_requirements(self):
        """Правило без нормативных требований (маркеров) -> NOT_CHECKED."""
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
                planned_start=date(2024, 1, 15),
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
                        obligation="auxiliary",  # Не маркер
                        min_count=1,
                    )
                ],
            )
        }

        observations = []

        result = engine.compute_site(stages, rules, observations, today)

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.status == StageStatusValue.NOT_CHECKED


class TestStageNotInWindow:
    """Тесты: этап, чьё плановое окно ещё не начато, не выдаёт статус."""

    def test_stage_not_in_window_produces_no_status(self):
        """Плановое начало далеко в будущем -> нет StageStatusResult для этапа."""
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
                planned_start=date(2024, 2, 1),  # Далеко в будущем
                planned_end=date(2024, 2, 10),
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

        # Этап не в окне, статуса не должно быть
        assert len(result.statuses) == 0


class TestConfidenceComputation:
    """Тесты: confidence ограничена количеством подтверждающих дат."""

    def test_confidence_capped_by_min_confirming_observations(self):
        """Меньше min_confirming_observations дат -> confidence не выше MEDIUM."""
        config = EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=3,  # Требуем 3 даты
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
                planned_start=date(2024, 1, 15),
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

        # Только 2 даты с маркером, а требуется 3
        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 16),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=equipment_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                ],
            ),
            ObservationInput(
                observed_on=date(2024, 1, 17),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=equipment_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                ],
            ),
        ]

        result = engine.compute_site(stages, rules, observations, today)

        assert len(result.statuses) == 1
        status = result.statuses[0]
        # Confidence должна быть MEDIUM из-за недостаточного числа дат
        assert status.confidence == Confidence.MEDIUM

    def test_confidence_high_with_sufficient_observations(self):
        """Достаточно дат -> confidence может быть HIGH."""
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
                planned_start=date(2024, 1, 15),
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
                observed_on=date(2024, 1, 16),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=equipment_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                ],
            ),
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
                    )
                ],
            ),
        ]

        result = engine.compute_site(stages, rules, observations, today)

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.confidence == Confidence.HIGH
