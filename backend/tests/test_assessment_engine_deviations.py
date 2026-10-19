"""Тесты двигателя расчёта отклонений от плана."""

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
        """Последнее наблюдение старше stale_data_days -> только stale_data, «Внимание».

        Как в clean-mvp: выводы по старым снимкам о сегодняшнем дне ничего не говорят,
        поэтому других отклонений рядом нет.
        """
        required = uuid.uuid4()
        stage, rule = _stage_and_rule(date(2024, 1, 10), date(2024, 1, 25), required)

        result = _engine().compute_site(
            [stage],
            {stage.stage_id: rule},
            [_obs(date(2024, 1, 15), uuid.uuid4())],
            date(2024, 2, 20),
        )

        assert [d.type for d in result.deviations] == [DeviationType.STALE_DATA]
        assert result.deviations[0].severity == Severity.ATTENTION


class TestDeviationMissingEquipment:
    """«Нет маркерной техники» — по окну последних дат, а не по одному дню."""

    def test_missing_equipment_three_high_days_no_marker(self):
        """Три рабочих дня с высокой наблюдаемостью без маркера -> критично."""
        required = uuid.uuid4()
        stage, rule = _stage_and_rule(date(2024, 1, 10), date(2024, 1, 31), required)
        observations = [_obs(day, uuid.uuid4()) for day in _days(16, 17, 18)]

        result = _engine().compute_site(
            [stage], {stage.stage_id: rule}, observations, date(2024, 1, 19)
        )

        missing = [d for d in result.deviations if d.type == DeviationType.MISSING_EQUIPMENT]
        assert len(missing) == 1
        deviation = missing[0]
        assert deviation.stage_id == stage.stage_id
        assert deviation.severity == Severity.CRITICAL
        assert deviation.is_hypothesis is False
        assert deviation.confidence == Confidence.HIGH
        assert deviation.period_start == date(2024, 1, 16)
        assert deviation.evidence_dates == tuple(_days(16, 17, 18))
        assert "16.01, 17.01, 18.01" in deviation.observed
        assert len(deviation.limits_text) > 0

    def test_one_day_without_marker_is_not_missing(self):
        """Один день без маркера ничего не доказывает (Березники на стенде)."""
        required = uuid.uuid4()
        stage, rule = _stage_and_rule(date(2024, 1, 10), date(2024, 1, 31), required)

        result = _engine().compute_site(
            [stage],
            {stage.stage_id: rule},
            [_obs(date(2024, 1, 18), uuid.uuid4())],
            date(2024, 1, 19),
        )

        assert not [d for d in result.deviations if d.type == DeviationType.MISSING_EQUIPMENT]

    def test_low_observability_day_in_window_is_not_missing(self):
        required = uuid.uuid4()
        stage, rule = _stage_and_rule(date(2024, 1, 10), date(2024, 1, 31), required)
        observations = [_obs(day, uuid.uuid4()) for day in _days(16, 17)] + [
            _obs(date(2024, 1, 18), uuid.uuid4(), observability="low")
        ]

        result = _engine().compute_site(
            [stage], {stage.stage_id: rule}, observations, date(2024, 1, 19)
        )

        assert not [d for d in result.deviations if d.type == DeviationType.MISSING_EQUIPMENT]


class TestDeviationStageMismatch:
    """«Несоответствие этапу»: машина этапа, который по плану сейчас не идёт."""

    @staticmethod
    def _site():
        """Идут «Котлован» (экскаватор); «Сваи» (буровая) по плану закончились."""
        excavator, drill = uuid.uuid4(), uuid.uuid4()
        piles, piles_rule = _stage_and_rule(date(2024, 1, 1), date(2024, 1, 5), drill, name="Сваи")
        pit, pit_rule = _stage_and_rule(
            date(2024, 1, 10), date(2024, 1, 31), excavator, name="Котлован", position=2
        )
        rules = {piles.stage_id: piles_rule, pit.stage_id: pit_rule}
        return [piles, pit], rules, pit, excavator, drill

    def test_one_photo_is_attention_not_critical(self):
        """Машина замечена на одном снимке -> «Внимание»: так было в Москве на стенде."""
        stages, rules, pit, _, drill = self._site()

        result = _engine().compute_site(
            stages,
            rules,
            [_obs(date(2024, 1, 18), drill)],
            date(2024, 1, 19),
            {drill: "Буровая установка"},
        )

        mismatch = [d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH]
        assert len(mismatch) == 1
        deviation = mismatch[0]
        assert deviation.stage_id == pit.stage_id
        assert deviation.severity == Severity.ATTENTION
        assert deviation.is_hypothesis is False
        assert deviation.observed == (
            "Буровая установка (не менее 1) — техника этапа «Сваи», "
            "который по плану сейчас не идёт."
        )
        assert "«Котлован»" in deviation.expected
        assert len(deviation.limits_text) > 0

    def test_three_dates_in_a_row_are_critical(self):
        stages, rules, _, _, drill = self._site()
        observations = [_obs(day, drill) for day in _days(16, 17, 18)]

        result = _engine().compute_site(stages, rules, observations, date(2024, 1, 19))

        mismatch = [d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH]
        assert [d.severity for d in mismatch] == [Severity.CRITICAL]
        assert mismatch[0].period_start == date(2024, 1, 16)
        assert mismatch[0].evidence_dates == tuple(_days(16, 17, 18))

    def test_coarse_class_fits_running_stage(self):
        """«Экскаватор (тип не определён)» подходит котловану с гусеничным экскаватором."""
        stages, rules, _, excavator, _ = self._site()
        unknown = uuid.uuid4()

        result = _engine().compute_site(
            stages,
            rules,
            [_obs(date(2024, 1, 18), unknown)],
            date(2024, 1, 19),
            coarse={unknown: frozenset({excavator})},
        )

        assert not [
            d
            for d in result.deviations
            if d.type in (DeviationType.STAGE_MISMATCH, DeviationType.EXTRA_EQUIPMENT)
        ]

    def test_machine_outside_zone_is_ignored(self):
        stages, rules, _, _, drill = self._site()
        outside = ObservationInput(
            observed_on=date(2024, 1, 18),
            photo_count=5,
            observability="high",
            equipment=[
                ObservedEquipmentInput(
                    equipment_type_id=drill,
                    count_min=1,
                    activity="works",
                    confidence="high",
                    in_zone=False,
                )
            ],
        )

        result = _engine().compute_site(stages, rules, [outside], date(2024, 1, 19))

        assert not [d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH]

    def test_machine_of_no_stage_is_extra_hypothesis(self):
        """Машины нет ни в одном этапе — гипотеза «Лишняя техника», одна на объект."""
        stages, rules, _, _, _ = self._site()
        stranger = uuid.uuid4()

        result = _engine().compute_site(
            stages, rules, [_obs(date(2024, 1, 18), stranger)], date(2024, 1, 19)
        )

        extra = [d for d in result.deviations if d.type == DeviationType.EXTRA_EQUIPMENT]
        assert len(extra) == 1
        assert extra[0].stage_id is None
        assert extra[0].is_hypothesis is True
        assert extra[0].severity == Severity.ATTENTION
        assert str(stranger) in extra[0].observed  # без названий — UUID
        assert not [d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH]


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


class TestIncompleteKit:
    """«Неполный комплект» (clean-mvp) вместо прежней гипотезы «Нет ожидаемой техники»."""

    @staticmethod
    def _pit():
        excavator, bulldozer, truck = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        stage = StageInput(uuid.uuid4(), "Котлован", 1, date(2024, 1, 8), date(2024, 2, 28))
        rule = RuleInput(
            stage_id=stage.stage_id,
            rule_id=uuid.uuid4(),
            is_verifiable=True,
            unverifiable_reason=None,
            requirements=[],
            kits=[
                KitInput(
                    position=0,
                    requirements=[
                        EquipmentRequirementInput(excavator, "normative", 1),
                        EquipmentRequirementInput(truck, "logical", 1),
                    ],
                ),
                KitInput(
                    position=1,
                    requirements=[
                        EquipmentRequirementInput(bulldozer, "normative", 1),
                        EquipmentRequirementInput(truck, "logical", 1),
                    ],
                ),
            ],
        )
        return stage, rule, excavator, bulldozer, truck

    def test_missing_normative_and_logical_are_separate_rows(self):
        """Пример из ТЗ: экскаватор в котловане есть, бульдозера и самосвалов нет."""
        stage, rule, excavator, bulldozer, truck = self._pit()
        names = {excavator: "Экскаватор", bulldozer: "Бульдозер", truck: "Самосвал"}

        result = _engine().compute_site(
            [stage],
            {stage.stage_id: rule},
            [_obs(day, excavator) for day in _days(16, 17, 18)],
            date(2024, 1, 19),
            names,
        )

        rows = [d for d in result.deviations if d.type == DeviationType.INCOMPLETE_KIT]
        assert [d.expected for d in rows] == [
            "Бульдозер — нормативная техника этапа «Котлован».",
            "Самосвал — логическая техника этапа «Котлован».",
        ]
        assert rows[1].observed.endswith("Без этой техники возможно снижение темпа работ.")
        assert all(d.severity == Severity.ATTENTION and not d.is_hypothesis for d in rows)
        # Машина отклонения — недостающая: у двух строк этапа разные ключи (id, решение)
        assert [d.equipment_type_id for d in rows] == [bulldozer, truck]
        assert not [
            d for d in result.deviations if d.type == DeviationType.MISSING_LOGICAL_EQUIPMENT
        ]

    def test_machine_seen_on_one_of_the_dates_is_not_missing(self):
        stage, rule, excavator, bulldozer, truck = self._pit()
        observations = [_obs(day, excavator) for day in _days(16, 17)]
        observations.append(
            ObservationInput(
                observed_on=date(2024, 1, 18),
                photo_count=5,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(excavator, 1, "works", "high"),
                    ObservedEquipmentInput(truck, 1, "works", "high"),
                ],
            )
        )

        result = _engine().compute_site(
            [stage], {stage.stage_id: rule}, observations, date(2024, 1, 19)
        )

        rows = [d for d in result.deviations if d.type == DeviationType.INCOMPLETE_KIT]
        assert len(rows) == 1  # только бульдозер: самосвал был 18.01

    def test_coarse_class_closes_the_kit_gap(self):
        """«Экскаватор (тип не определён)» закрывает экскаватор комплекта (clean, covering)."""
        stage, rule, excavator, bulldozer, truck = self._pit()
        unknown = uuid.uuid4()
        observations = [
            ObservationInput(
                observed_on=day,
                photo_count=5,
                observability="high",
                equipment=[
                    ObservedEquipmentInput(bulldozer, 1, "works", "high"),
                    ObservedEquipmentInput(unknown, 1, "works", "high"),
                    ObservedEquipmentInput(truck, 1, "works", "high"),
                ],
            )
            for day in _days(16, 17, 18)
        ]

        result = _engine().compute_site(
            [stage],
            {stage.stage_id: rule},
            observations,
            date(2024, 1, 19),
            coarse={unknown: frozenset({excavator})},
        )

        assert not [d for d in result.deviations if d.type == DeviationType.INCOMPLETE_KIT]

    def test_any_machine_of_a_group_closes_the_gap(self):
        """Сваи: буровая, копёр или грейфер — одна группа, нехватки нет при любой из них."""
        drill, driver = uuid.uuid4(), uuid.uuid4()
        stage = StageInput(uuid.uuid4(), "Сваи", 1, date(2024, 1, 8), date(2024, 2, 28))
        rule = RuleInput(
            stage_id=stage.stage_id,
            rule_id=uuid.uuid4(),
            is_verifiable=True,
            unverifiable_reason=None,
            requirements=[],
            kits=[
                KitInput(0, [EquipmentRequirementInput(drill, "normative", 1, group="piling")]),
                KitInput(1, [EquipmentRequirementInput(driver, "normative", 1, group="piling")]),
            ],
        )

        result = _engine().compute_site(
            [stage],
            {stage.stage_id: rule},
            [_obs(day, drill) for day in _days(16, 17, 18)],
            date(2024, 1, 19),
        )

        assert not [d for d in result.deviations if d.type == DeviationType.INCOMPLETE_KIT]

    def test_finished_stage_gets_no_row(self):
        stage, rule, excavator, _, _ = self._pit()
        finished = StageInput(stage.stage_id, stage.name, 1, date(2023, 12, 1), date(2024, 1, 10))

        result = _engine().compute_site(
            [finished],
            {stage.stage_id: rule},
            [_obs(day, excavator) for day in _days(16, 17, 18)],
            date(2024, 1, 19),
        )

        assert not [d for d in result.deviations if d.type == DeviationType.INCOMPLETE_KIT]

    def test_low_observability_day_gives_no_row(self):
        stage, rule, excavator, _, _ = self._pit()
        observations = [_obs(day, excavator) for day in _days(16, 17)] + [
            _obs(date(2024, 1, 18), excavator, observability="medium")
        ]

        result = _engine().compute_site(
            [stage], {stage.stage_id: rule}, observations, date(2024, 1, 19)
        )

        assert not [d for d in result.deviations if d.type == DeviationType.INCOMPLETE_KIT]


def _engine() -> RuleEngine:
    return RuleEngine(
        EngineConfig(
            tolerance_days=5,
            stale_data_days=30,
            no_progress_window_days=7,
            min_confirming_observations=2,
        )
    )


def _stage_and_rule(
    start: date,
    end: date,
    required_id: uuid.UUID,
    *,
    name: str = "Этап",
    position: int = 1,
):
    stage_id = uuid.uuid4()
    stage = StageInput(
        stage_id=stage_id, name=name, position=position, planned_start=start, planned_end=end
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


def _days(*days: int) -> list[date]:
    """Дни января 2024: 15–19 — пн–пт."""
    return [date(2024, 1, d) for d in days]


def _obs(on: date, equipment_id: uuid.UUID, observability: str = "high") -> ObservationInput:
    return ObservationInput(
        observed_on=on,
        photo_count=5,
        observability=observability,
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
        # Как в clean-mvp: 8 доказанных дней при высокой наблюдаемости — «Критично»
        assert behind[0].severity == Severity.CRITICAL
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
    """Несоответствие этапу — только к этапам, которые идут в день снимка."""

    def test_finished_stage_gets_no_mismatch_from_later_photo(self):
        piles_id, pit_id = uuid.uuid4(), uuid.uuid4()
        past, past_rule = _stage_and_rule(date(2024, 1, 1), date(2024, 1, 5), piles_id)
        current, current_rule = _stage_and_rule(
            date(2024, 1, 15), date(2024, 1, 25), pit_id, position=2
        )
        result = _engine().compute_site(
            [past, current],
            {past.stage_id: past_rule, current.stage_id: current_rule},
            [_obs(date(2024, 1, 3), piles_id), _obs(date(2024, 1, 18), piles_id)],
            date(2024, 1, 20),
        )
        mismatch = [d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH]
        assert [d.stage_id for d in mismatch] == [current.stage_id]

    def test_expected_names_running_stages(self):
        required, other = uuid.uuid4(), uuid.uuid4()
        stage, rule = _stage_and_rule(
            date(2024, 1, 10), date(2024, 1, 25), required, name="Котлован"
        )
        owner, owner_rule = _stage_and_rule(
            date(2024, 3, 1), date(2024, 3, 31), other, name="Засыпка", position=2
        )
        result = _engine().compute_site(
            [stage, owner],
            {stage.stage_id: rule, owner.stage_id: owner_rule},
            [_obs(date(2024, 1, 18), other)],
            date(2024, 1, 20),
            {required: "Экскаватор", other: "Самосвал"},
        )
        mismatch = next(d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH)
        assert mismatch.expected == "Техника этапов, идущих по плану на 18.01: «Котлован»."
        assert "Самосвал" in mismatch.observed
        assert "«Засыпка»" in mismatch.observed


class TestStationaryMachines:
    """Башенный кран стоит весь срок: ни «несоответствия», ни «лишней техники»."""

    def test_tower_crane_never_mismatches_a_running_stage(self):
        crane, excavator = uuid.uuid4(), uuid.uuid4()
        pit, pit_rule = _stage_and_rule(date(2024, 1, 10), date(2024, 1, 31), excavator)
        frame, frame_rule = _stage_and_rule(
            date(2024, 3, 1), date(2024, 6, 1), crane, name="Каркас", position=2
        )
        observations = [_obs(day, crane) for day in _days(16, 17, 18)]

        result = _engine().compute_site(
            [pit, frame],
            {pit.stage_id: pit_rule, frame.stage_id: frame_rule},
            observations,
            date(2024, 1, 19),
            stationary=frozenset({crane}),
        )

        assert not [
            d
            for d in result.deviations
            if d.type in (DeviationType.STAGE_MISMATCH, DeviationType.EXTRA_EQUIPMENT)
        ]


class TestMismatchStreak:
    """Серия «Несоответствия» — только дни, когда машину не объясняет идущий этап."""

    def test_streak_starts_after_the_owner_stage_window(self):
        """Буровая видна с 09.01, сваи до 11.01 (+5 допуска) — серия с 17.01, а не с 09.01."""
        drill, excavator = uuid.uuid4(), uuid.uuid4()
        piles, piles_rule = _stage_and_rule(date(2024, 1, 1), date(2024, 1, 11), drill, name="Сваи")
        pit, pit_rule = _stage_and_rule(
            date(2024, 1, 7), date(2024, 1, 25), excavator, name="Котлован", position=2
        )
        observations = [_obs(day, drill) for day in [*_days(9, 10, 11, 12), *_days(15, 16, 17)]]

        result = _engine().compute_site(
            [piles, pit],
            {piles.stage_id: piles_rule, pit.stage_id: pit_rule},
            observations,
            date(2024, 1, 18),
            {drill: "Буровая установка"},
        )

        mismatch = next(d for d in result.deviations if d.type == DeviationType.STAGE_MISMATCH)
        assert mismatch.period_start == date(2024, 1, 17)
        assert mismatch.title == "Буровая установка: техника этапа «Сваи»"
        assert mismatch.equipment_type_id == drill
        assert mismatch.cause_stage_id == piles.stage_id  # сваи затянулись
