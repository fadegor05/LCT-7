"""Тесты двигателя расчёта статусов этапов с поддержкой наборов оборудования (kits)."""

import uuid
from datetime import date

from app.domains.assessment.engine import (
    EngineConfig,
    EquipmentRequirementInput,
    KitInput,
    ObservationInput,
    ObservedEquipmentInput,
    RuleEngine,
    RuleInput,
    StageInput,
)
from app.domains.assessment.models import DeviationType, StageStatusValue
from app.domains.observation.models import Confidence


class TestKitBackwardCompatibility:
    """Тесты: RuleInput без kits работает как раньше (flat requirements)."""

    def test_flat_requirements_without_kits_field(self):
        """RuleInput с flat requirements и без kits остаётся работоспособным."""
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

        # RuleInput БЕЗ поля kits — используется flat requirements
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
        assert status.confidence == Confidence.MEDIUM  # Одна дата, min_confirming_observations=2


class TestKitConfirmation1:
    """Тест 1: Набор из двух нормативных машин, только одна наблюдается -> НЕ подтверждено."""

    def test_kit_two_normative_only_one_observed(self):
        """Набор требует две нормативные машины, видна только одна -> NOT_STARTED."""
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
        excavator_id = uuid.uuid4()
        dump_truck_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Excavation",
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
                requirements=[],  # flat requirements empty
                kits=[
                    KitInput(
                        position=0,
                        requirements=[
                            EquipmentRequirementInput(
                                equipment_type_id=excavator_id,
                                obligation="normative",
                                min_count=1,
                            ),
                            EquipmentRequirementInput(
                                equipment_type_id=dump_truck_id,
                                obligation="normative",
                                min_count=1,
                            ),
                        ],
                    )
                ],
            )
        }

        # Видна только экскаватор, dump truck отсутствует
        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 16),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=excavator_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                ],
            ),
            ObservationInput(
                observed_on=date(2024, 1, 20),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=excavator_id,
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
        # Набор не может быть подтверждён без обеих машин
        assert status.status in (StageStatusValue.NOT_STARTED, StageStatusValue.NOT_OBSERVED)


class TestKitConfirmation2:
    """Тест 2: Нормативная машина требует count_min=2, видна count_min=1 -> НЕ подтверждено."""

    def test_kit_normative_min_count_not_met(self):
        """Требуется count_min=2, но наблюдается count_min=1 -> NOT_STARTED."""
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
        dump_truck_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Hauling",
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
                requirements=[],
                kits=[
                    KitInput(
                        position=0,
                        requirements=[
                            EquipmentRequirementInput(
                                equipment_type_id=dump_truck_id,
                                obligation="normative",
                                min_count=2,  # Требуем 2
                            )
                        ],
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
                        equipment_type_id=dump_truck_id,
                        count_min=1,  # Видим только 1
                        activity="works",
                        confidence="high",
                    )
                ],
            ),
        ]

        result = engine.compute_site(stages, rules, observations, today)

        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.status in (StageStatusValue.NOT_STARTED, StageStatusValue.NOT_OBSERVED)


class TestKitConfirmation3:
    """Тест 3: Экскаватор (норм, генерик) + самосвал (логич, генерик), только экскаватор."""

    def test_kit_with_logical_equipment_missing(self):
        """Нормативный экскаватор видна, логический самосвал отсутствует, высокая observability."""
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
        excavator_id = uuid.uuid4()
        dump_truck_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Excavation",
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
                        equipment_type_id=dump_truck_id,
                        obligation="logical",
                        min_count=1,
                    ),
                ],
                kits=[
                    KitInput(
                        position=0,
                        requirements=[
                            EquipmentRequirementInput(
                                equipment_type_id=excavator_id,
                                obligation="normative",
                                min_count=1,
                                is_specific=False,  # generic
                            ),
                            EquipmentRequirementInput(
                                equipment_type_id=dump_truck_id,
                                obligation="logical",
                                min_count=1,
                                is_specific=False,  # generic
                            ),
                        ],
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
                        equipment_type_id=excavator_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                ],
            ),
        ]

        equipment_names = {
            excavator_id: "Экскаватор",
            dump_truck_id: "Самосвал",
        }

        result = engine.compute_site(stages, rules, observations, today, equipment_names)

        # Статус ON_TRACK (нормативное оборудование подтверждено)
        assert len(result.statuses) == 1
        status = result.statuses[0]
        assert status.status == StageStatusValue.ON_TRACK
        # Confidence LOW так как подтверждено только универсальной техникой (missing logical)
        assert status.confidence == Confidence.LOW
        assert status.confidence_reason == "подтверждено только универсальной техникой"

        # Должно быть отклонение missing_logical_equipment
        missing_logical = [
            d for d in result.deviations if d.type == DeviationType.MISSING_LOGICAL_EQUIPMENT
        ]
        assert len(missing_logical) == 1
        deviation = missing_logical[0]
        # В observed должно быть имя самосвала
        assert "Самосвал" in deviation.observed
        # evidence_dates должны содержать дату наблюдения
        assert date(2024, 1, 16) in deviation.evidence_dates


class TestKitConfirmation4:
    """Тест 4: Башенный кран (норм, генерик) + бетономешалка (логич, отсутствует)."""

    def test_kit_normative_only_with_missing_logical(self):
        """Только нормативное общее оборудование, логическое отсутствует."""
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
        tower_crane_id = uuid.uuid4()
        concrete_pump_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Monolith",
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
                requirements=[],
                kits=[
                    KitInput(
                        position=0,
                        requirements=[
                            EquipmentRequirementInput(
                                equipment_type_id=tower_crane_id,
                                obligation="normative",
                                min_count=1,
                                is_specific=False,  # generic
                            ),
                            EquipmentRequirementInput(
                                equipment_type_id=concrete_pump_id,
                                obligation="logical",
                                min_count=1,
                                is_specific=False,  # generic
                            ),
                        ],
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
                        equipment_type_id=tower_crane_id,
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
        assert status.status == StageStatusValue.ON_TRACK
        # Confidence LOW так как есть missing логическое оборудование
        assert status.confidence == Confidence.LOW
        assert status.confidence_reason == "подтверждено только универсальной техникой"


class TestKitConfirmation5:
    """Тест 5: Буровая установка (норм, специальная) -> подтверждено с HIGH confidence."""

    def test_kit_specific_normative_equipment(self):
        """Специальное оборудование -> подтверждено с HIGH confidence."""
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
        piling_rig_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Piling",
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
                requirements=[],
                kits=[
                    KitInput(
                        position=0,
                        requirements=[
                            EquipmentRequirementInput(
                                equipment_type_id=piling_rig_id,
                                obligation="normative",
                                min_count=1,
                                is_specific=True,  # SPECIFIC
                            ),
                        ],
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
                        equipment_type_id=piling_rig_id,
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
                        equipment_type_id=piling_rig_id,
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
        assert status.status == StageStatusValue.ON_TRACK
        # Confidence HIGH: 2 даты достаточно, и is_specific=True
        assert status.confidence == Confidence.HIGH


class TestKitConfirmation6:
    """Тест 6: Два набора, второй выполнен -> подтверждено."""

    def test_kit_second_kit_fulfilled(self):
        """Первый набор не выполнен, второй выполнен -> статус как будто набор выполнен."""
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
        excavator_id = uuid.uuid4()
        tower_crane_id = uuid.uuid4()

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
                requirements=[],
                kits=[
                    KitInput(
                        position=0,
                        requirements=[
                            EquipmentRequirementInput(
                                equipment_type_id=excavator_id,
                                obligation="normative",
                                min_count=1,
                            ),
                        ],
                    ),
                    KitInput(
                        position=1,
                        requirements=[
                            EquipmentRequirementInput(
                                equipment_type_id=tower_crane_id,
                                obligation="normative",
                                min_count=1,
                            ),
                        ],
                    ),
                ],
            )
        }

        # Видна только башенный кран (second kit)
        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 16),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=tower_crane_id,
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
        # Второй набор выполнен -> ON_TRACK
        assert status.status == StageStatusValue.ON_TRACK


class TestMissingEquipmentDeviation:
    """Тест: MISSING_EQUIPMENT для двухмашинного набора с только одной машиной."""

    def test_missing_equipment_when_kit_not_fulfilled(self):
        """Три дня с высокой observability, ни один набор не выполнен -> MISSING_EQUIPMENT.

        «Нет маркерной техники» — по окну из window_dates дат после допуска от начала,
        а не по одному дню.
        """
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
        excavator_id = uuid.uuid4()
        dump_truck_id = uuid.uuid4()

        stages = [
            StageInput(
                stage_id=stage_id,
                name="Excavation",
                position=1,
                planned_start=date(2024, 1, 8),
                planned_end=date(2024, 1, 25),
            )
        ]

        rules = {
            stage_id: RuleInput(
                stage_id=stage_id,
                rule_id=rule_id,
                is_verifiable=True,
                unverifiable_reason=None,
                requirements=[],
                kits=[
                    KitInput(
                        position=0,
                        requirements=[
                            EquipmentRequirementInput(
                                equipment_type_id=excavator_id,
                                obligation="normative",
                                min_count=1,
                            ),
                            EquipmentRequirementInput(
                                equipment_type_id=dump_truck_id,
                                obligation="normative",
                                min_count=1,
                            ),
                        ],
                    )
                ],
            )
        }

        # Последнее наблюдение с высокой observability, только экскаватор видна
        observations = [
            ObservationInput(
                observed_on=date(2024, 1, 16),
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=excavator_id,
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
                        equipment_type_id=excavator_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                ],
            ),
            ObservationInput(
                observed_on=date(2024, 1, 18),  # Latest
                photo_count=10,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(
                        equipment_type_id=excavator_id,
                        count_min=1,
                        activity="works",
                        confidence="high",
                    )
                ],
            ),
        ]

        result = engine.compute_site(stages, rules, observations, today)

        # Должно быть отклонение missing_equipment
        missing = [d for d in result.deviations if d.type == DeviationType.MISSING_EQUIPMENT]
        assert len(missing) == 1
        deviation = missing[0]
        assert deviation.stage_id == stage_id
