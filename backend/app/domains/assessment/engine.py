"""Двигатель расчёта статусов этапов и отклонений от плана."""

import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta

from app.domains.assessment.models import (
    DeviationType,
    Severity,
    StageStatusValue,
)
from app.domains.observation.models import Confidence, Observability


@dataclass(frozen=True)
class EquipmentRequirementInput:
    """Требование по оборудованию для входа движка."""

    equipment_type_id: uuid.UUID
    obligation: str  # "normative" | "logical" | "auxiliary"
    min_count: int


@dataclass(frozen=True)
class RuleInput:
    """Правило методологии для входа движка."""

    stage_id: uuid.UUID
    rule_id: uuid.UUID
    is_verifiable: bool
    unverifiable_reason: str | None
    requirements: Sequence[EquipmentRequirementInput]


@dataclass(frozen=True)
class StageInput:
    """Этап графика для входа движка."""

    stage_id: uuid.UUID
    name: str
    position: int
    planned_start: date | None
    planned_end: date | None


@dataclass(frozen=True)
class ObservedEquipmentInput:
    """Наблюдаемое оборудование."""

    equipment_type_id: uuid.UUID
    count_min: int
    activity: str  # "works" | "idle" | "unknown"
    confidence: str  # "high" | "medium" | "low"
    in_zone: bool | None = None


@dataclass(frozen=True)
class ObservationInput:
    """Наблюдение за дату."""

    observed_on: date
    photo_count: int
    observability: str  # "high" | "medium" | "low"
    equipment: Sequence[ObservedEquipmentInput]


@dataclass(frozen=True)
class EngineConfig:
    """Конфигурация движка."""

    tolerance_days: int
    stale_data_days: int
    no_progress_window_days: int
    min_confirming_observations: int
    workdays: tuple[int, ...] = (0, 1, 2, 3, 4)  # date.weekday(): Mon=0..Sun=6


@dataclass(frozen=True)
class StageStatusResult:
    """Результат расчёта статуса этапа."""

    stage_id: uuid.UUID
    status: StageStatusValue
    delay_days: int | None
    confidence: Confidence
    confidence_reason: str | None
    basis_dates: tuple[date, ...]


@dataclass(frozen=True)
class DeviationResult:
    """Результат выявления отклонения."""

    stage_id: uuid.UUID | None
    type: DeviationType
    is_hypothesis: bool
    severity: Severity
    confidence: Confidence
    period_start: date
    period_end: date
    expected: str
    observed: str
    limits_text: str
    rule_id: uuid.UUID | None
    evidence_dates: tuple[date, ...]


@dataclass(frozen=True)
class SiteComputation:
    """Результат расчёта для объекта."""

    statuses: list[StageStatusResult]
    deviations: list[DeviationResult]


class RuleEngine:
    """Двигатель расчёта статусов этапов и отклонений."""

    def __init__(self, config: EngineConfig) -> None:
        """Инициализировать движок с конфигурацией."""
        self.config = config

    def compute_site(
        self,
        stages: Sequence[StageInput],
        rules_by_stage: dict[uuid.UUID, RuleInput],
        observations: Sequence[ObservationInput],
        today: date,
        equipment_names: Mapping[uuid.UUID, str] | None = None,
    ) -> SiteComputation:
        """Рассчитать статусы и отклонения для объекта.

        Args:
            stages: Этапы графика.
            rules_by_stage: Правила методологии по stage_id.
            observations: Наблюдения в хронологическом порядке.
            today: Текущая дата.
            equipment_names: Названия типов техники по id (LCT-15) — для
                читаемого текста в отклонениях вместо сырых UUID. Движок не
                знает о БД/каталоге — словарь строит вызывающий код
                (RecomputeCoordinator, через EquipmentCatalog).

        Returns:
            SiteComputation с статусами и отклонениями.
        """
        names = equipment_names or {}
        statuses: list[StageStatusResult] = []
        deviations: list[DeviationResult] = []

        # Наблюдения отсортированы по дате
        sorted_observations = sorted(observations, key=lambda o: o.observed_on)

        # Расчёт статусов этапов
        for stage in stages:
            status = self._compute_stage_status(
                stage, rules_by_stage.get(stage.stage_id), sorted_observations, today
            )
            if status is not None:
                statuses.append(status)

        # Отклонение stale_data проверяется один раз для всего объекта (даже без наблюдений)
        deviations.extend(self._check_stale_data(sorted_observations, today))

        # Отклонения по этапам
        for stage in stages:
            rule = rules_by_stage.get(stage.stage_id)

            # Проверяем, что статус был выдан для этого этапа и он верифицируемый
            stage_status = next((s for s in statuses if s.stage_id == stage.stage_id), None)

            # Отклонения выдаются только для верифицируемых этапов (имеющих статус != NOT_CHECKED)
            if stage_status is not None and stage_status.status != StageStatusValue.NOT_CHECKED:
                deviations.extend(
                    self._check_stage_deviations(
                        stage, rule, sorted_observations, today, stage_status.basis_dates, names
                    )
                )

        return SiteComputation(statuses=statuses, deviations=deviations)

    def _compute_stage_status(
        self,
        stage: StageInput,
        rule: RuleInput | None,
        observations: Sequence[ObservationInput],
        today: date,
    ) -> StageStatusResult | None:
        """Рассчитать статус одного этапа.

        Возвращает None, если окно этапа ещё не начато.
        """
        # Шаг 1: Проверяем верификабельность и маркеры
        if rule is None or not rule.is_verifiable:
            reason = (
                rule.unverifiable_reason
                if rule and rule.unverifiable_reason
                else "этап не сопоставлен с методикой или у него нет маркеров"
            )
            return StageStatusResult(
                stage_id=stage.stage_id,
                status=StageStatusValue.NOT_CHECKED,
                delay_days=None,
                confidence=Confidence.LOW,
                confidence_reason=reason,
                basis_dates=(),
            )

        # Проверяем наличие нормативных требований (маркеры)
        markers = {r.equipment_type_id for r in rule.requirements if r.obligation == "normative"}
        if not markers:
            return StageStatusResult(
                stage_id=stage.stage_id,
                status=StageStatusValue.NOT_CHECKED,
                delay_days=None,
                confidence=Confidence.LOW,
                confidence_reason="этап не сопоставлен с методикой или у него нет маркеров",
                basis_dates=(),
            )

        # Шаг 2: Проверяем, начали ли окно этапа
        window_started = stage.planned_start is None or today >= stage.planned_start - timedelta(
            days=self.config.tolerance_days
        )
        if not window_started:
            # Окно ещё не началось, этап не оценивается
            return None

        # Шаг 3: Вычисляем маркерные даты
        marker_dates = self._extract_marker_dates(observations, markers)
        first_marker = marker_dates[0] if marker_dates else None
        latest_obs_on = observations[-1].observed_on if observations else None
        markers_active_now = latest_obs_on is not None and latest_obs_on in marker_dates

        # Шаг 4: Проверяем, прошёл ли плановый конец
        end_passed = stage.planned_end is not None and today > stage.planned_end + timedelta(
            days=self.config.tolerance_days
        )

        # Шаг 5: Выбираем статус по приоритету
        if end_passed and markers_active_now:
            # a. Конец прошёл, маркеры ещё видны
            status = StageStatusValue.BEHIND
            # stage.planned_end не None, так как end_passed требует это
            delay_days = (today - (stage.planned_end or today)).days
            confidence, reason = self._compute_confidence_for_status(
                marker_dates, first_marker, observations
            )
        elif (
            stage.planned_start is not None
            and first_marker is not None
            and first_marker > stage.planned_start + timedelta(days=self.config.tolerance_days)
        ):
            # b. Маркер после planned_start + tolerance
            status = StageStatusValue.BEHIND
            delay_days = (first_marker - stage.planned_start).days
            confidence, reason = self._compute_confidence_for_status(
                marker_dates, first_marker, observations
            )
        elif (
            stage.planned_start is not None
            and first_marker is not None
            and first_marker < stage.planned_start - timedelta(days=self.config.tolerance_days)
        ):
            # c. Маркер раньше planned_start - tolerance
            status = StageStatusValue.AHEAD
            delay_days = (stage.planned_start - first_marker).days
            confidence, reason = self._compute_confidence_for_status(
                marker_dates, first_marker, observations
            )
        elif first_marker is not None:
            # d. Маркер в окне
            status = StageStatusValue.ON_TRACK
            delay_days = None
            confidence, reason = self._compute_confidence_for_status(
                marker_dates, first_marker, observations
            )
        else:
            # e. Маркер никогда не видели
            status, confidence, reason, basis_dates = self._check_not_started_vs_not_observed(
                stage, observations, today
            )
            return StageStatusResult(
                stage_id=stage.stage_id,
                status=status,
                delay_days=None,
                confidence=confidence,
                confidence_reason=reason,
                basis_dates=basis_dates,
            )

        # Шаг 6-8: Возвращаем результат для a/b/c/d
        return StageStatusResult(
            stage_id=stage.stage_id,
            status=status,
            delay_days=delay_days,
            confidence=confidence,
            confidence_reason=reason,
            basis_dates=tuple(marker_dates),
        )

    def _extract_marker_dates(
        self, observations: Sequence[ObservationInput], markers: set[uuid.UUID]
    ) -> list[date]:
        """Извлечь отсортированные даты, когда видели маркер."""
        marker_dates = []
        for obs in observations:
            has_marker = any(
                eq.equipment_type_id in markers and eq.count_min >= 1 for eq in obs.equipment
            )
            if has_marker:
                marker_dates.append(obs.observed_on)
        return sorted(marker_dates)

    def _compute_confidence_for_status(
        self,
        marker_dates: list[date],
        first_marker: date | None,
        observations: Sequence[ObservationInput],
    ) -> tuple[Confidence, str]:
        """Рассчитать confidence и причину для статуса со статусом (AHEAD/ON_TRACK/BEHIND).

        Шаг 6-7 алгоритма.
        """
        if first_marker is None:
            # Не должно быть вызвано, но на всякий случай
            return Confidence.LOW, "маркер не найден"

        # Находим observation с first_marker
        first_obs = next((o for o in observations if o.observed_on == first_marker), None)
        if first_obs is None:
            return Confidence.LOW, "наблюдение с маркером не найдено"

        # (i) Худшая confidence среди оборудования в первом наблюдении маркера
        equipment_confidences = [
            self._str_to_confidence(eq.confidence) for eq in first_obs.equipment
        ]
        marker_eq_confidence = (
            min(equipment_confidences, key=lambda c: self._confidence_order(c))
            if equipment_confidences
            else Confidence.HIGH
        )

        # (ii) Confidence по количеству дат
        if len(marker_dates) >= self.config.min_confirming_observations:
            date_confidence = Confidence.HIGH
            date_reason = "количество подтверждающих дат достаточно"
        else:
            date_confidence = Confidence.MEDIUM
            date_reason = "уверенность ограничена количеством подтверждающих дат"

        # Финальная confidence — минимум из двух
        final_confidence = self._min_confidence(marker_eq_confidence, date_confidence)

        # Выбираем причину
        reason = date_reason
        if marker_eq_confidence != Confidence.HIGH:
            reason = "уверенность ограничена уверенностью детекции маркерной техники"

        return final_confidence, reason

    def _check_not_started_vs_not_observed(
        self, stage: StageInput, observations: Sequence[ObservationInput], today: date
    ) -> tuple[StageStatusValue, Confidence, str, tuple[date, ...]]:
        """Определить NOT_STARTED или NOT_OBSERVED.

        Шаг 5e алгоритма.
        """
        # Определяем окно для проверки наблюдаемости
        window_start = stage.planned_start or (
            observations[0].observed_on if observations else today
        )
        window_end = today

        # Находим наблюдения в окне на рабочие дни
        obs_in_window = [
            o
            for o in observations
            if window_start <= o.observed_on <= window_end
            and o.observed_on.weekday() in self.config.workdays
        ]

        # Вычисляем худшую наблюдаемость в окне
        worst_observability = Observability.LOW
        if obs_in_window:
            observabilities = [self._str_to_observability(o.observability) for o in obs_in_window]
            worst_observability = min(observabilities, key=lambda o: self._observability_order(o))

        basis_dates = tuple(o.observed_on for o in obs_in_window)

        if worst_observability == Observability.HIGH:
            status = StageStatusValue.NOT_STARTED
            confidence = Confidence.HIGH
            reason = "маркерная техника не наблюдается при высокой наблюдаемости всего окна"
        else:
            status = StageStatusValue.NOT_OBSERVED
            if obs_in_window:
                confidence = Confidence.MEDIUM
                reason = "низкая наблюдаемость в окне этапа"
            else:
                confidence = Confidence.LOW
                reason = "отсутствуют наблюдения в окне этапа"

        return status, confidence, reason, basis_dates

    def _check_stale_data(
        self, observations: Sequence[ObservationInput], today: date
    ) -> list[DeviationResult]:
        """Проверить отклонение stale_data (один раз для всего объекта)."""
        if not observations:
            latest_obs_on = None
        else:
            latest_obs_on = observations[-1].observed_on

        if latest_obs_on is None or (today - latest_obs_on).days > self.config.stale_data_days:
            if latest_obs_on is None:
                period_start = today
                period_end = today
            else:
                period_start = latest_obs_on
                period_end = today

            return [
                DeviationResult(
                    stage_id=None,
                    type=DeviationType.STALE_DATA,
                    is_hypothesis=False,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    period_start=period_start,
                    period_end=period_end,
                    expected="Актуальные данные съёмки",
                    observed="Последнее наблюдение из прошлого"
                    if latest_obs_on
                    else "Наблюдений нет",
                    limits_text=(
                        "Не доказывает текущее состояние объекта — "
                        "техника могла измениться после последней съёмки."
                    ),
                    rule_id=None,
                    evidence_dates=(),
                )
            ]

        return []

    def _check_stage_deviations(
        self,
        stage: StageInput,
        rule: RuleInput | None,
        observations: Sequence[ObservationInput],
        today: date,
        status_basis_dates: tuple[date, ...],
        equipment_names: Mapping[uuid.UUID, str],
    ) -> list[DeviationResult]:
        """Проверить отклонения по одному верифицируемому этапу."""
        deviations: list[DeviationResult] = []

        if not observations:
            return deviations

        latest_obs_on = observations[-1].observed_on
        latest_obs = observations[-1]

        if rule is None:
            return deviations

        # Получаем маркеры и требуемую технику
        markers = {r.equipment_type_id for r in rule.requirements if r.obligation == "normative"}
        all_required = {r.equipment_type_id for r in rule.requirements}

        # 2. missing_equipment
        deviations.extend(
            self._check_missing_equipment(stage, latest_obs, latest_obs_on, markers, rule)
        )

        # 2b. missing_logical_equipment (LCT-15) — мягкое предупреждение по
        # "логической" технике методики: ожидаемой на этапе, но не
        # обязательной для подтверждения его начала (в отличие от
        # нормативных маркеров выше).
        deviations.extend(
            self._check_missing_logical_equipment(
                stage, latest_obs, latest_obs_on, rule, equipment_names
            )
        )

        # 3. stage_mismatch
        if latest_obs.equipment and not any(
            eq.equipment_type_id in all_required for eq in latest_obs.equipment
        ):
            mismatch_names = self._format_equipment_names(
                [eq.equipment_type_id for eq in latest_obs.equipment], equipment_names
            )
            deviations.append(
                DeviationResult(
                    stage_id=stage.stage_id,
                    type=DeviationType.STAGE_MISMATCH,
                    is_hypothesis=False,
                    severity=Severity.CRITICAL,
                    confidence=self._worst_confidence(latest_obs.equipment),
                    period_start=latest_obs_on,
                    period_end=latest_obs_on,
                    expected="Техника, предусмотренная методикой этапа",
                    observed=f"Техника: {mismatch_names}",
                    limits_text=(
                        "Не доказывает завершённость этапа или смену техники — "
                        "техника могла быть вне зоны обзора камер."
                    ),
                    rule_id=rule.rule_id,
                    evidence_dates=(latest_obs_on,),
                )
            )
            # Не добавляем missing_equipment, если есть stage_mismatch
            deviations = [
                d
                for d in deviations
                if not (d.type == DeviationType.MISSING_EQUIPMENT and d.stage_id == stage.stage_id)
            ]

        # 4. idle
        idle_eq = [eq for eq in latest_obs.equipment if eq.activity == "idle"]
        if idle_eq:
            idle_names = self._format_equipment_names(
                [eq.equipment_type_id for eq in idle_eq], equipment_names
            )
            deviations.append(
                DeviationResult(
                    stage_id=stage.stage_id,
                    type=DeviationType.IDLE,
                    is_hypothesis=True,
                    severity=Severity.ATTENTION,
                    confidence=self._min_confidence(
                        self._worst_confidence(idle_eq), Confidence.MEDIUM
                    ),
                    period_start=latest_obs_on,
                    period_end=latest_obs_on,
                    expected="Активная работа техники на этапе",
                    observed=f"Техника в состоянии простоя: {idle_names}",
                    limits_text=(
                        "Гипотеза — не доказывает остановку работ, "
                        "техника могла быть в перерыве или ожидании."
                    ),
                    rule_id=rule.rule_id,
                    evidence_dates=(latest_obs_on,),
                )
            )

        # 5. extra_equipment
        extra_eq = [eq for eq in latest_obs.equipment if eq.equipment_type_id not in all_required]
        markers_active_now = latest_obs_on in status_basis_dates
        if extra_eq and markers_active_now:
            extra_names = self._format_equipment_names(
                [eq.equipment_type_id for eq in extra_eq], equipment_names
            )
            deviations.append(
                DeviationResult(
                    stage_id=stage.stage_id,
                    type=DeviationType.EXTRA_EQUIPMENT,
                    is_hypothesis=True,
                    severity=Severity.ATTENTION,
                    confidence=self._min_confidence(
                        self._worst_confidence(extra_eq), Confidence.MEDIUM
                    ),
                    period_start=latest_obs_on,
                    period_end=latest_obs_on,
                    expected="Только техника, предусмотренная методикой",
                    observed=f"Дополнительная техника: {extra_names}",
                    limits_text=(
                        "Гипотеза — не доказывает незапланированные работы, "
                        "техника могла быть на соседнем объекте или проезжать мимо."
                    ),
                    rule_id=rule.rule_id,
                    evidence_dates=(latest_obs_on,),
                )
            )

        # 6. out_of_zone
        out_zone_eq = [eq for eq in latest_obs.equipment if eq.in_zone is False]
        if out_zone_eq:
            out_zone_names = self._format_equipment_names(
                [eq.equipment_type_id for eq in out_zone_eq], equipment_names
            )
            deviations.append(
                DeviationResult(
                    stage_id=stage.stage_id,
                    type=DeviationType.OUT_OF_ZONE,
                    is_hypothesis=True,
                    severity=Severity.ATTENTION,
                    confidence=self._min_confidence(
                        self._worst_confidence(out_zone_eq), Confidence.MEDIUM
                    ),
                    period_start=latest_obs_on,
                    period_end=latest_obs_on,
                    expected="Работа техники в пределах рабочей зоны",
                    observed=f"Техника вне рабочей зоны: {out_zone_names}",
                    limits_text=(
                        "Гипотеза — не доказывает нарушение, "
                        "зона могла быть некорректно задана или техника выезжала временно."
                    ),
                    rule_id=rule.rule_id,
                    evidence_dates=(latest_obs_on,),
                )
            )

        # 7. no_progress
        if len(observations) >= 2:
            deviations.extend(self._check_no_progress(observations, stage, rule))

        return deviations

    def _check_missing_equipment(
        self,
        stage: StageInput,
        latest_obs: ObservationInput,
        latest_obs_on: date,
        markers: set[uuid.UUID],
        rule: RuleInput,
    ) -> list[DeviationResult]:
        """Проверить отклонение missing_equipment."""
        if latest_obs.observability == "high":
            has_marker = any(
                eq.equipment_type_id in markers and eq.count_min >= 1 for eq in latest_obs.equipment
            )
            if not has_marker:
                return [
                    DeviationResult(
                        stage_id=stage.stage_id,
                        type=DeviationType.MISSING_EQUIPMENT,
                        is_hypothesis=False,
                        severity=Severity.CRITICAL,
                        confidence=Confidence.HIGH,
                        period_start=latest_obs_on,
                        period_end=latest_obs_on,
                        expected="Присутствие маркерной техники этапа",
                        observed="Маркерная техника не обнаружена",
                        limits_text=(
                            "Не доказывает остановку работ вне времени и мест съёмки — "
                            "техника могла работать вне зоны обзора камер."
                        ),
                        rule_id=rule.rule_id,
                        evidence_dates=(latest_obs_on,),
                    )
                ]

        return []

    def _check_missing_logical_equipment(
        self,
        stage: StageInput,
        latest_obs: ObservationInput,
        latest_obs_on: date,
        rule: RuleInput,
        equipment_names: Mapping[uuid.UUID, str],
    ) -> list[DeviationResult]:
        """Проверить отклонение missing_logical_equipment (LCT-15).

        В отличие от missing_equipment (нормативные маркеры, CRITICAL,
        подтверждает/опровергает сам факт активности этапа) — это мягкое
        предупреждение по "логической" технике методики: ожидаемой на
        этапе, но не обязательной для подтверждения его начала.
        """
        if latest_obs.observability != "high":
            return []

        logical_ids = {r.equipment_type_id for r in rule.requirements if r.obligation == "logical"}
        if not logical_ids:
            return []

        present_ids = {eq.equipment_type_id for eq in latest_obs.equipment if eq.count_min >= 1}
        missing_ids = logical_ids - present_ids
        if not missing_ids:
            return []

        return [
            DeviationResult(
                stage_id=stage.stage_id,
                type=DeviationType.MISSING_LOGICAL_EQUIPMENT,
                is_hypothesis=True,
                severity=Severity.ATTENTION,
                confidence=Confidence.MEDIUM,
                period_start=latest_obs_on,
                period_end=latest_obs_on,
                expected=(
                    f"Техника из логического набора этапа: "
                    f"{self._format_equipment_names(logical_ids, equipment_names)}"
                ),
                observed=(
                    f"Не обнаружена: {self._format_equipment_names(missing_ids, equipment_names)}"
                ),
                limits_text=(
                    "Гипотеза — логическая техника не обязательна для подтверждения "
                    "этапа, могла быть вне зоны обзора камер или не понадобиться на "
                    "этой стадии."
                ),
                rule_id=rule.rule_id,
                evidence_dates=(latest_obs_on,),
            )
        ]

    def _format_equipment_names(
        self, equipment_type_ids: Iterable[uuid.UUID], equipment_names: Mapping[uuid.UUID, str]
    ) -> str:
        """Отобразить типы техники по именам (LCT-15), а не по UUID.

        Каталог передаётся снаружи — движок не знает о БД. Отсутствующее в
        словаре имя — fallback на сам UUID (деградация, не падение).
        """
        names = sorted(equipment_names.get(eid, str(eid)) for eid in equipment_type_ids)
        return ", ".join(names)

    def _check_no_progress(
        self,
        observations: Sequence[ObservationInput],
        stage: StageInput,
        rule: RuleInput,
    ) -> list[DeviationResult]:
        """Проверить отклонение no_progress (две последние близкие по времени наблюдения)."""
        # Берём два последних наблюдения
        if len(observations) < 2:
            return []

        # Ищем две наиболее свежие даты в окне no_progress_window_days
        recent = sorted(observations, key=lambda o: o.observed_on, reverse=True)

        # Должны быть в окне
        for i in range(len(recent) - 1):
            later_obs = recent[i]
            earlier_obs = recent[i + 1]

            days_diff = (later_obs.observed_on - earlier_obs.observed_on).days
            if days_diff > self.config.no_progress_window_days:
                break

            # Проверяем, идентична ли техника
            later_eq_set = {(eq.equipment_type_id, eq.count_min) for eq in later_obs.equipment}
            earlier_eq_set = {(eq.equipment_type_id, eq.count_min) for eq in earlier_obs.equipment}

            if later_eq_set == earlier_eq_set and later_eq_set:
                # Проверяем, нет ли activity="works"
                has_works_later = any(eq.activity == "works" for eq in later_obs.equipment)
                has_works_earlier = any(eq.activity == "works" for eq in earlier_obs.equipment)

                if not has_works_later and not has_works_earlier:
                    return [
                        DeviationResult(
                            stage_id=stage.stage_id,
                            type=DeviationType.NO_PROGRESS,
                            is_hypothesis=False,
                            severity=Severity.ATTENTION,
                            confidence=Confidence.MEDIUM,
                            period_start=earlier_obs.observed_on,
                            period_end=later_obs.observed_on,
                            expected="Изменение состояния техники или начало активных работ",
                            observed="Техника не изменилась и не работает",
                            limits_text=(
                                "Не доказывает полную остановку проекта — "
                                "возможны работы вне зоны обзора или внутренние процессы."
                            ),
                            rule_id=rule.rule_id,
                            evidence_dates=(
                                earlier_obs.observed_on,
                                later_obs.observed_on,
                            ),
                        )
                    ]

        return []

    def _str_to_confidence(self, s: str) -> Confidence:
        """Конвертировать строку в Confidence."""
        if s == "high":
            return Confidence.HIGH
        elif s == "medium":
            return Confidence.MEDIUM
        else:
            return Confidence.LOW

    def _str_to_observability(self, s: str) -> Observability:
        """Конвертировать строку в Observability."""
        if s == "high":
            return Observability.HIGH
        elif s == "medium":
            return Observability.MEDIUM
        else:
            return Observability.LOW

    def _confidence_order(self, c: Confidence) -> int:
        """Вернуть порядок confidence для сравнения (LOW < MEDIUM < HIGH)."""
        order = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
        return order.get(c, 0)

    def _observability_order(self, o: Observability) -> int:
        """Вернуть порядок observability для сравнения (LOW < MEDIUM < HIGH)."""
        order = {Observability.LOW: 0, Observability.MEDIUM: 1, Observability.HIGH: 2}
        return order.get(o, 0)

    def _min_confidence(self, c1: Confidence, c2: Confidence) -> Confidence:
        """Вернуть минимальную (худшую) confidence."""
        order1 = self._confidence_order(c1)
        order2 = self._confidence_order(c2)
        return c1 if order1 <= order2 else c2

    def _worst_confidence(self, equipment: Sequence[ObservedEquipmentInput]) -> Confidence:
        """Вернуть худшую confidence среди оборудования."""
        if not equipment:
            return Confidence.HIGH

        confidences = [self._str_to_confidence(eq.confidence) for eq in equipment]
        return min(confidences, key=self._confidence_order)
