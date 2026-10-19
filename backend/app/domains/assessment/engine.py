"""Двигатель расчёта статусов этапов и отклонений от плана."""

import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from enum import StrEnum

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
    is_specific: bool = False
    # Группа взаимозаменяемой техники: для «Неполного комплекта» хватает любой её машины
    group: str | None = None


@dataclass(frozen=True)
class KitInput:
    """Набор оборудования для подтверждения этапа."""

    position: int
    requirements: Sequence[EquipmentRequirementInput]


@dataclass(frozen=True)
class RuleInput:
    """Правило методологии для входа движка."""

    stage_id: uuid.UUID
    rule_id: uuid.UUID
    is_verifiable: bool
    unverifiable_reason: str | None
    requirements: Sequence[EquipmentRequirementInput]
    kits: Sequence[KitInput] = ()

    @property
    def effective_kits(self) -> Sequence[KitInput]:
        """Вернуть kits если непусто, иначе один kit с flat requirements."""
        if self.kits:
            return self.kits
        return (KitInput(position=0, requirements=self.requirements),)


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
    # «Не начат» — только по стольким рабочим дням окна с высокой наблюдаемостью:
    # один день с кадрами не доказывает, что этап не начался
    window_dates: int = 3
    # «Критично» — не раньше стольких дней от начала этапа и, у отклонений по замеченной
    # машине, только когда она видна столько дат подряд: один случайный день — «Внимание»
    critical_days: int = 3
    # Вне своего окна этап сравнивается с этапами, закончившимися или начинающимися в
    # пределах стольких дней: техника недавно закончившегося этапа скорее его, чем чужая
    lookback_days: int = 14


@dataclass(frozen=True)
class StageStatusResult:
    """Результат расчёта статуса этапа."""

    stage_id: uuid.UUID
    status: StageStatusValue
    delay_days: int | None
    confidence: Confidence
    confidence_reason: str | None
    basis_dates: tuple[date, ...]
    # delay_days — нижняя граница («от N дней»): этап не начат, конец сдвига неизвестен
    delay_open: bool = False
    # Сдвиг интервалом, как Delay в clean-mvp: None — граница неизвестна («до N», «от N»).
    # delay_days — одно число для прежних экранов: верхняя граница, а если её нет — нижняя
    delay_min: int | None = None
    delay_max: int | None = None
    # Факт по маркеру: первая подтверждённая маркерная дата (clean-mvp, start_fact)
    start_fact: date | None = None
    # Маркеры этапа: техника, которая хоть когда-то в его окне отличает его от соседних
    markers: frozenset[uuid.UUID] = frozenset()
    # Когда машина — маркер этапа: (машина, с, по), подряд идущие дни окна (clean-mvp)
    marker_periods: tuple[tuple[uuid.UUID, date, date], ...] = ()


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
    # Короткий заголовок строки списка, как в clean-mvp («Буровая установка: техника этапа
    # «Сваи»», «Неполный комплект: не виден бульдозер»)
    title: str = ""
    # Машина отклонения: доказательства — кадры с её рамкой
    equipment_type_id: uuid.UUID | None = None
    # Возможная причина: отстающий этап, чья техника ещё на площадке
    cause_stage_id: uuid.UUID | None = None


class Verdict(StrEnum):
    """Итог по объекту."""

    BEHIND = "behind"
    NO_DEVIATIONS = "no_deviations"
    INSUFFICIENT_DATA = "insufficient_data"


@dataclass(frozen=True)
class SummaryResult:
    """Итог по объекту: худший этап с отставанием или причина, почему итога нет."""

    verdict: Verdict
    delay_days_min: int | None
    delay_days_max: int | None
    stage_id: uuid.UUID | None
    reason: str
    # Опорная дата расчёта — «данные на» на экранах
    as_of: date | None = None


@dataclass(frozen=True)
class _Plan:
    """Этапы с методикой и общие для расчёта справочники (маркеры на дату, как в clean)."""

    stages: Sequence[StageInput]
    rules: Mapping[uuid.UUID, RuleInput]
    stationary: frozenset[uuid.UUID]
    tolerance_days: int
    lookback_days: int
    # «Тип не определён» → конкретные классы, которые он закрывает в комплекте
    coarse: Mapping[uuid.UUID, frozenset[uuid.UUID]] = field(default_factory=dict)

    @staticmethod
    def normative(rule: RuleInput) -> frozenset[uuid.UUID]:
        return frozenset(
            r.equipment_type_id
            for kit in rule.effective_kits
            for r in kit.requirements
            if r.obligation == "normative"
        )

    @staticmethod
    def classes(rule: RuleInput) -> frozenset[uuid.UUID]:
        ids = {r.equipment_type_id for r in rule.requirements}
        for kit in rule.effective_kits:
            ids.update(r.equipment_type_id for r in kit.requirements)
        return frozenset(ids)

    @staticmethod
    def in_window(stage: StageInput, day: date, margin: int) -> bool:
        if stage.planned_start is None or stage.planned_end is None:
            return False
        t = timedelta(days=margin)
        return stage.planned_start - t <= day <= stage.planned_end + t

    def markers_on(self, stage: StageInput, day: date) -> frozenset[uuid.UUID]:
        """Маркеры этапа на дату: нормативная техника, которой нет у этапов, идущих в этот
        день. Неподвижная (башенный кран) о том, какой этап идёт, не говорит ничего."""
        rule = self.rules.get(stage.stage_id)
        if rule is None or not rule.is_verifiable:
            return frozenset()
        own_window = self.in_window(stage, day, self.tolerance_days)
        margin = self.tolerance_days if own_window else self.lookback_days
        shared: set[uuid.UUID] = set()
        for other in self.stages:
            other_rule = self.rules.get(other.stage_id)
            if other.stage_id == stage.stage_id or other_rule is None:
                continue
            if not other_rule.is_verifiable:
                continue
            if self.in_window(other, day, margin):
                shared |= self.classes(other_rule)
        return self.normative(rule) - shared - self.stationary

    def marker_periods(self, stage: StageInput) -> tuple[tuple[uuid.UUID, date, date], ...]:
        """Периоды, когда машина — маркер этапа: подряд идущие дни окна (план ± допуск).

        Методика показывает их инженеру («маркер 07.04–11.05»): вне периода машину делят
        соседние этапы, и по ней этап не отличить.
        """
        if stage.planned_start is None or stage.planned_end is None:
            return ()
        t = timedelta(days=self.tolerance_days)
        day, end = stage.planned_start - t, stage.planned_end + t
        open_: dict[uuid.UUID, tuple[date, date]] = {}
        periods: list[tuple[uuid.UUID, date, date]] = []
        while day <= end:
            today = self.markers_on(stage, day)
            for kind in [k for k in open_ if k not in today]:
                start, last = open_.pop(kind)
                periods.append((kind, start, last))
            for kind in today:
                start, _ = open_.get(kind, (day, day))
                open_[kind] = (start, day)
            day += timedelta(days=1)
        periods.extend((kind, start, last) for kind, (start, last) in open_.items())
        return tuple(sorted(periods, key=lambda p: (p[1], str(p[0]))))

    def markers_for(self, stage: StageInput) -> frozenset[uuid.UUID]:
        """Объединение маркеров по дням окна этапа (clean-mvp, markers_for)."""
        if stage.planned_start is None or stage.planned_end is None:
            return frozenset()
        t = timedelta(days=self.tolerance_days)
        day, end = stage.planned_start - t, stage.planned_end + t
        found: set[uuid.UUID] = set()
        while day <= end:
            found |= self.markers_on(stage, day)
            day += timedelta(days=1)
        return frozenset(found)


@dataclass(frozen=True)
class SiteComputation:
    """Результат расчёта для объекта."""

    statuses: list[StageStatusResult]
    deviations: list[DeviationResult]
    summary: SummaryResult


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
        coarse: Mapping[uuid.UUID, frozenset[uuid.UUID]] | None = None,
        stationary: frozenset[uuid.UUID] = frozenset(),
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
            coarse: Класс «тип не определён» → конкретные классы, с которыми он
                совместим («Экскаватор (тип не определён)» подходит этапу с
                гусеничным экскаватором).
            stationary: Неподвижная техника (башенный кран): маркером этапа не бывает.

        Returns:
            SiteComputation с статусами и отклонениями.
        """
        names = equipment_names or {}
        statuses: list[StageStatusResult] = []
        deviations: list[DeviationResult] = []

        # Наблюдения отсортированы по дате
        sorted_observations = sorted(observations, key=lambda o: o.observed_on)
        plan = _Plan(
            stages=stages,
            rules=rules_by_stage,
            stationary=stationary,
            tolerance_days=self.config.tolerance_days,
            lookback_days=self.config.lookback_days,
            coarse=coarse or {},
        )

        # Расчёт статусов этапов
        for stage in stages:
            status = self._compute_stage_status(
                stage, rules_by_stage.get(stage.stage_id), sorted_observations, today, plan
            )
            if status is not None:
                if status.status != StageStatusValue.NOT_CHECKED:
                    status = replace(
                        status,
                        markers=plan.markers_for(stage),
                        marker_periods=plan.marker_periods(stage),
                    )
                statuses.append(status)

        # Устаревшие данные — единственное отклонение: выводы по старым кадрам о сегодняшнем
        # дне ничего не говорят (как в clean-mvp)
        stale = self._check_stale_data(sorted_observations, today)
        if stale:
            summary = replace(
                summarize(stages, statuses, sorted_observations, today, self.config), as_of=today
            )
            return SiteComputation(statuses=statuses, deviations=stale, summary=summary)

        # Отклонения по этапам
        for stage in stages:
            rule = rules_by_stage.get(stage.stage_id)

            # Проверяем, что статус был выдан для этого этапа и он верифицируемый
            stage_status = next((s for s in statuses if s.stage_id == stage.stage_id), None)

            # Отклонения выдаются только для верифицируемых этапов (имеющих статус != NOT_CHECKED)
            if stage_status is not None and stage_status.status != StageStatusValue.NOT_CHECKED:
                deviations.extend(
                    self._check_stage_deviations(
                        stage,
                        rule,
                        sorted_observations,
                        today,
                        stage_status.basis_dates,
                        names,
                        plan,
                    )
                )
                deviations.extend(
                    self._check_schedule_delay(
                        stage, rule, stage_status, sorted_observations, today
                    )
                )

        # Чужая техника — одна строка на машину, а не на каждый идущий этап
        deviations.extend(
            self._check_mismatch_and_extra(
                stages,
                rules_by_stage,
                statuses,
                sorted_observations,
                names,
                coarse or {},
                stationary,
            )
        )

        summary = replace(
            summarize(stages, statuses, sorted_observations, today, self.config), as_of=today
        )
        return SiteComputation(statuses=statuses, deviations=deviations, summary=summary)

    def _compute_stage_status(
        self,
        stage: StageInput,
        rule: RuleInput | None,
        observations: Sequence[ObservationInput],
        today: date,
        plan: _Plan,
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

        # Проверяем наличие нормативных требований в наборах
        effective_kits = rule.effective_kits
        # Только наборы с нормативными требованиями считаются
        kits_with_normative = [
            kit
            for kit in effective_kits
            if any(r.obligation == "normative" for r in kit.requirements)
        ]
        if not kits_with_normative:
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

        # Шаг 3: Маркерные даты — набор выполнен и в нём есть машина, отличающая этап
        # в этот день от идущих одновременно (иначе экскаватор свай «начинал» котлован)
        # Снизу — как у поиска начала: технику задолго до окна объясняют отклонения. Сверху
        # не ограничено: машины этапа после конца — это и есть затянувшийся этап
        since, _ = self._search_window(stage)
        marker_dates = [
            o.observed_on
            for o in observations
            if since <= o.observed_on and self._is_marker_day(stage, kits_with_normative, o, plan)
        ]
        first_marker = self._find_start(stage, kits_with_normative, observations, plan)

        # Шаг 4: Проверяем, прошёл ли плановый конец
        end_passed = stage.planned_end is not None and today > stage.planned_end + timedelta(
            days=self.config.tolerance_days
        )

        # Маркер в последних датах наблюдений: этап ещё идёт (смены техники не видно)
        tail = observations[-self.config.window_dates :]
        seen_recently = [o.observed_on for o in tail if o.observed_on in marker_dates]
        delay_min: int | None = None
        delay_max: int | None = None

        # Шаг 5: Выбираем статус по приоритету
        if end_passed and first_marker is not None and seen_recently:
            # a. Конец прошёл, маркер ещё виден в последних датах (clean-mvp, _overrun):
            # этап затянулся минимум до последнего дня с маркером и максимум до опорной даты
            assert stage.planned_end is not None
            status = StageStatusValue.BEHIND
            delay_min = max(0, (seen_recently[-1] - stage.planned_end).days)
            delay_max = (today - stage.planned_end).days
            delay_days = delay_max
            confidence, reason = self._compute_confidence_for_status(
                marker_dates, first_marker, observations, kits_with_normative
            )
        elif (
            stage.planned_start is not None
            and first_marker is not None
            and first_marker > stage.planned_start + timedelta(days=self.config.tolerance_days)
            and not any(stage.planned_start <= o.observed_on < first_marker for o in observations)
        ):
            # b0. Маркер позже плана, но снимков до него нет: позднее начало не доказано —
            # этап мог идти с планового начала, просто съёмка началась позже
            status = StageStatusValue.ON_TRACK
            delay_days = None
            confidence, _ = self._compute_confidence_for_status(
                marker_dates, first_marker, observations, kits_with_normative
            )
            confidence = self._min_confidence(confidence, Confidence.MEDIUM)
            reason = (
                f"маркерная техника видна с {first_marker:%d.%m} — с первых снимков: "
                "начало могло быть по плану"
            )
        elif (
            stage.planned_start is not None
            and first_marker is not None
            and first_marker > stage.planned_start + timedelta(days=self.config.tolerance_days)
        ):
            # b. Маркер после planned_start + tolerance. Нижняя граница — последний день без
            # маркера после планового начала, когда этап был отличим (clean-mvp, _start_delay)
            status = StageStatusValue.BEHIND
            without = [
                o.observed_on
                for o in observations
                if stage.planned_start <= o.observed_on < first_marker
                and plan.markers_on(stage, o.observed_on)
                and o.observed_on not in marker_dates
            ]
            delay_min = (
                (without[-1] + timedelta(days=1) - stage.planned_start).days if without else None
            )
            delay_max = (first_marker - stage.planned_start).days
            delay_days = delay_max
            confidence, reason = self._compute_confidence_for_status(
                marker_dates, first_marker, observations, kits_with_normative
            )
        elif (
            stage.planned_start is not None
            and first_marker is not None
            and first_marker < stage.planned_start - timedelta(days=self.config.tolerance_days)
        ):
            # c. Маркер раньше planned_start - tolerance
            status = StageStatusValue.AHEAD
            delay_days = (stage.planned_start - first_marker).days
            delay_min = delay_max = delay_days
            confidence, reason = self._compute_confidence_for_status(
                marker_dates, first_marker, observations, kits_with_normative
            )
        elif first_marker is not None:
            # d. Маркер в окне
            status = StageStatusValue.ON_TRACK
            delay_days = None
            confidence, reason = self._compute_confidence_for_status(
                marker_dates, first_marker, observations, kits_with_normative
            )
        else:
            # e. Маркер никогда не видели
            return self._check_not_started_vs_not_observed(stage, observations, today, plan)

        # Шаг 6-8: Возвращаем результат для a/b/c/d
        return StageStatusResult(
            stage_id=stage.stage_id,
            status=status,
            delay_days=delay_days,
            confidence=confidence,
            confidence_reason=reason,
            basis_dates=tuple(marker_dates),
            delay_min=delay_min,
            delay_max=delay_max,
            start_fact=first_marker,
        )

    @staticmethod
    def _countable(eq: ObservedEquipmentInput, stationary: frozenset[uuid.UUID]) -> bool:
        """Машина, которую можно предъявлять основанием: не слабая и не неподвижная."""
        return (
            eq.count_min >= 1 and eq.confidence != "low" and eq.equipment_type_id not in stationary
        )

    def _is_marker_day(
        self,
        stage: StageInput,
        kits: Sequence[KitInput],
        observation: ObservationInput,
        plan: _Plan,
    ) -> bool:
        """День говорит, что идёт именно этот этап.

        Выполнен набор, и в нём есть нормативная машина, которой в этот день нет у идущих
        одновременно этапов (маркер, как в clean-mvp). Если этап в этот день по технике не
        отличить, нужен весь набор сразу — нормативная и логическая техника: одна общая
        машина ничего не говорит.
        """
        markers = plan.markers_on(stage, observation.observed_on)
        present = {
            eq.equipment_type_id
            for eq in observation.equipment
            if self._countable(eq, plan.stationary)
        }
        if not markers:
            # Этап в этот день не отличить: нужен весь его комплект сразу — нормативная и
            # логическая техника всех наборов (clean-mvp, kit_of). Одна общая машина, хоть
            # и выполняющая свой набор, ничего не говорит; неподвижная в комплект не входит
            whole = {
                r.equipment_type_id
                for kit in kits
                for r in kit.requirements
                if r.obligation in ("normative", "logical")
            } - plan.stationary
            return bool(whole) and whole <= present
        for kit in kits:
            if not self._is_kit_fulfilled(kit, observation):
                continue
            normative = {
                r.equipment_type_id for r in kit.requirements if r.obligation == "normative"
            }
            if normative & markers & present:
                return True
        return False

    def _search_window(self, stage: StageInput) -> tuple[date, date]:
        """От «плановое начало − lookback» до «конец окна + lookback»: технику задолго до
        или после окна объясняют отклонения, а не этот этап."""
        lookback = timedelta(days=self.config.lookback_days)
        tolerance = timedelta(days=self.config.tolerance_days)
        since = stage.planned_start - lookback if stage.planned_start else date.min
        until = stage.planned_end + tolerance + lookback if stage.planned_end else date.max
        return since, until

    def _find_start(
        self,
        stage: StageInput,
        kits: Sequence[KitInput],
        observations: Sequence[ObservationInput],
        plan: _Plan,
    ) -> date | None:
        """Начало этапа (clean-mvp, find_start_fact): первая маркерная дата.

        Ищется от «плановое начало − lookback» до «конец окна + lookback»: технику,
        замеченную много раньше или позже, объясняют отклонения, а не старт этапа. Одной
        даты хватает, если машина уверенная и работает; иначе маркер должен быть виден и на
        следующей дате наблюдения.
        """
        since, until = self._search_window(stage)
        relevant = [o for o in observations if since <= o.observed_on <= until]
        for i, current in enumerate(relevant):
            if not self._is_marker_day(stage, kits, current, plan):
                continue
            markers = plan.markers_on(stage, current.observed_on)
            sure = any(
                eq.confidence == "high"
                and eq.activity == "works"
                and (not markers or eq.equipment_type_id in markers)
                for eq in current.equipment
                if self._countable(eq, plan.stationary)
            )
            following = relevant[i + 1] if i + 1 < len(relevant) else None
            if sure or (
                following is not None and self._is_marker_day(stage, kits, following, plan)
            ):
                return current.observed_on
        return None

    def _has_equipment(
        self, observation: ObservationInput, requirement: EquipmentRequirementInput
    ) -> bool:
        """Проверить, есть ли в наблюдении оборудование, соответствующее требованию."""
        for obs_eq in observation.equipment:
            if (
                obs_eq.equipment_type_id == requirement.equipment_type_id
                and obs_eq.count_min >= requirement.min_count
            ):
                return True
        return False

    def _is_kit_fulfilled(self, kit: KitInput, observation: ObservationInput) -> bool:
        """Проверить, выполнены ли ВСЕ нормативные требования набора в наблюдении."""
        normative_reqs = [r for r in kit.requirements if r.obligation == "normative"]
        if not normative_reqs:
            return False

        return all(self._has_equipment(observation, req) for req in normative_reqs)

    def _is_kit_strong(self, kit: KitInput, observation: ObservationInput) -> bool:
        """Проверить, является ли выполненный набор STRONG.

        Набор strong если:
        - Содержит нормативное требование с is_specific=True, ИЛИ
        - ВСЕ его логические требования присутствуют с достаточным count_min.
        """
        # Проверяем is_specific
        has_specific_normative = any(
            r.obligation == "normative" and r.is_specific for r in kit.requirements
        )
        if has_specific_normative:
            return True

        # Проверяем логические требования
        logical_reqs = [r for r in kit.requirements if r.obligation == "logical"]
        if not logical_reqs:
            # Нет логических требований -> считаем как all present
            return True

        return all(self._has_equipment(observation, req) for req in logical_reqs)

    def _extract_marker_dates_for_kits(
        self, observations: Sequence[ObservationInput], kits: Sequence[KitInput]
    ) -> list[date]:
        """Извлечь отсортированные даты, когда выполнен хотя бы один набор."""
        marker_dates = []
        for obs in observations:
            # Проверяем, выполнен ли хотя бы один набор
            if any(self._is_kit_fulfilled(kit, obs) for kit in kits):
                marker_dates.append(obs.observed_on)
        return sorted(marker_dates)

    def _compute_confidence_for_status(
        self,
        marker_dates: list[date],
        first_marker: date | None,
        observations: Sequence[ObservationInput],
        kits: Sequence[KitInput] | None = None,
    ) -> tuple[Confidence, str]:
        """Рассчитать confidence и причину для статуса со статусом (AHEAD/ON_TRACK/BEHIND).

        Шаг 6-7 алгоритма. С поддержкой kit strength.
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

        # Проверка kit strength: если ни один marker_date не is_strong, ограничиваем confidence
        if kits is not None:
            # Проверяем, есть ли strong marker date
            has_strong_marker_date = False
            for marker_date in marker_dates:
                marker_obs = next((o for o in observations if o.observed_on == marker_date), None)
                if marker_obs and any(
                    self._is_kit_fulfilled(kit, marker_obs) and self._is_kit_strong(kit, marker_obs)
                    for kit in kits
                ):
                    has_strong_marker_date = True
                    break

            # Если нет strong marker date, ограничиваем confidence до LOW
            if not has_strong_marker_date:
                final_confidence = self._min_confidence(final_confidence, Confidence.LOW)
                reason = "подтверждено только универсальной техникой"

        return final_confidence, reason

    def _check_not_started_vs_not_observed(
        self,
        stage: StageInput,
        observations: Sequence[ObservationInput],
        today: date,
        plan: _Plan,
    ) -> StageStatusResult | None:
        """Маркер этапа ни разу не виден: «Не начат», «Не наблюдалось» или ещё рано.

        «Не начат» — только когда плановое начало прошло больше чем на допуск и в окне
        этапа не меньше `window_dates` рабочих дней, все с высокой наблюдаемостью. Тогда
        отставание — «от N дней»: сколько этап уже не начат, а не итоговый сдвиг. Один
        день с кадрами ничего не доказывает (Березники на стенде: один день — критично).
        """
        tolerance = timedelta(days=self.config.tolerance_days)
        window_start = stage.planned_start or (
            observations[0].observed_on if observations else today
        )
        in_window = [
            o
            for o in observations
            if window_start <= o.observed_on <= today
            and o.observed_on.weekday() in self.config.workdays
        ]
        # Только дни, когда этап отличим по технике: в остальные отсутствие маркера ничего
        # не говорит о том, начат ли этап
        window = [o for o in in_window if plan.markers_on(stage, o.observed_on)]
        basis_dates = tuple(o.observed_on for o in window)

        def result(
            status: StageStatusValue,
            confidence: Confidence,
            reason: str,
            delay_days: int | None = None,
        ) -> StageStatusResult:
            return StageStatusResult(
                stage_id=stage.stage_id,
                status=status,
                delay_days=delay_days,
                confidence=confidence,
                confidence_reason=reason,
                basis_dates=basis_dates,
                delay_open=delay_days is not None,
                delay_min=delay_days,
            )

        if stage.planned_start is not None and today <= stage.planned_start + tolerance:
            # Срок допуска ещё не прошёл: отсутствие маркера пока ни о чём не говорит
            return result(
                StageStatusValue.NOT_OBSERVED,
                Confidence.LOW,
                "срок допуска после планового начала ещё не прошёл",
            )
        if len(window) >= self.config.window_dates and all(
            o.observability == Observability.HIGH.value for o in window
        ):
            return result(
                StageStatusValue.NOT_STARTED,
                Confidence.HIGH,
                "маркерная техника не наблюдается при высокой наблюдаемости всех рабочих дней окна",
                (today - stage.planned_start).days if stage.planned_start else None,
            )
        if window:
            return result(
                StageStatusValue.NOT_OBSERVED,
                Confidence.MEDIUM,
                "наблюдаемость в окне этапа не высокая или дней с кадрами меньше "
                f"{self.config.window_dates}",
            )
        if in_window:
            # Снимки в окне есть, а отличить этап не по чему: он идёт одновременно с этапами
            # с той же техникой. «Мало снимков» здесь было бы неправдой
            return result(
                StageStatusValue.NOT_OBSERVED,
                Confidence.LOW,
                "не отличить по технике от этапов, идущих одновременно",
            )
        return result(StageStatusValue.NOT_OBSERVED, Confidence.LOW, "в окне этапа нет кадров")

    def _check_schedule_delay(
        self,
        stage: StageInput,
        rule: RuleInput | None,
        status: StageStatusResult,
        observations: Sequence[ObservationInput],
        today: date,
    ) -> list[DeviationResult]:
        """Отклонение behind_schedule: этап со статусом «Отстаёт» и числом дней отставания."""
        if status.status != StageStatusValue.BEHIND or not status.delay_days:
            # «Не начат» строкой отставания не бывает: срок у него — нижняя граница, и он
            # уже в статусе этапа и в итоге
            return []
        if status.delay_days <= 0 or not status.basis_dates:
            return []

        tolerance = timedelta(days=self.config.tolerance_days)
        end_passed = stage.planned_end is not None and today > stage.planned_end + tolerance
        last_seen = status.basis_dates[-1]
        if end_passed and stage.planned_end is not None and last_seen > stage.planned_end:
            # a. План закончился, а маркерная техника ещё видна после конца
            planned_end = stage.planned_end
            expected = f"Этап завершён по графику к {planned_end:%d.%m.%Y}"
            observed = (
                f"Маркерная техника видна и {last_seen:%d.%m.%Y}, отставание {delay_text(status)}"
            )
            period_start, period_end = planned_end, last_seen
        else:
            # b. Работы начались позже плана
            first_marker = status.basis_dates[0]
            expected = (
                f"Начало работ по графику {stage.planned_start:%d.%m.%Y}"
                if stage.planned_start
                else "Начало работ по графику"
            )
            observed = (
                f"Маркерная техника впервые замечена {first_marker:%d.%m.%Y}, "
                f"отставание {delay_text(status)}"
            )
            period_start = stage.planned_start or first_marker
            period_end = first_marker

        return [
            DeviationResult(
                stage_id=stage.stage_id,
                type=DeviationType.BEHIND_SCHEDULE,
                is_hypothesis=False,
                # Как в clean-mvp (severity_for): «Критично» от critical_days доказанной
                # задержки при уверенности не ниже средней и высокой наблюдаемости
                severity=self._severity(status.delay_min or 0, status.confidence, observations[-1]),
                confidence=status.confidence,
                period_start=period_start,
                period_end=max(period_start, period_end),
                expected=expected,
                observed=observed,
                limits_text=(
                    "Оценка по снимкам: техника могла появиться или уйти между съёмками, "
                    "поэтому срок отставания приблизителен."
                ),
                rule_id=rule.rule_id if rule else None,
                evidence_dates=status.basis_dates[-self.config.window_dates :],
                title=f"Отставание: {stage.name}",
            )
        ]

    def _check_stale_data(
        self, observations: Sequence[ObservationInput], today: date
    ) -> list[DeviationResult]:
        """Проверить отклонение stale_data (один раз для всего объекта)."""
        # Без наблюдений данные не «устарели», их просто нет: статусы этапов
        # в этом случае «Не наблюдалось», а критичное отклонение было бы шумом.
        if not observations:
            return []

        latest_obs_on = observations[-1].observed_on

        if (today - latest_obs_on).days > self.config.stale_data_days:
            period_start = latest_obs_on
            period_end = today

            return [
                DeviationResult(
                    stage_id=None,
                    type=DeviationType.STALE_DATA,
                    is_hypothesis=False,
                    severity=Severity.ATTENTION,
                    confidence=Confidence.HIGH,
                    period_start=period_start,
                    period_end=period_end,
                    expected="Актуальные данные съёмки",
                    observed=f"Последнее наблюдение {latest_obs_on:%d.%m.%Y}",
                    limits_text=(
                        "Не доказывает текущее состояние объекта — "
                        "техника могла измениться после последней съёмки."
                    ),
                    rule_id=None,
                    evidence_dates=(),
                    title="Данные устарели",
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
        plan: _Plan,
    ) -> list[DeviationResult]:
        """Проверить отклонения по одному верифицируемому этапу."""
        deviations: list[DeviationResult] = []

        if not observations:
            return deviations

        latest_obs_on = observations[-1].observed_on
        latest_obs = observations[-1]

        if rule is None:
            return deviations

        # Техника последнего наблюдения сравнивается с методикой этапа, только
        # если этап в это время идёт по графику (или его маркеры ещё видны).
        # Иначе завершённый или будущий этап получает «несоответствие» по снимку,
        # который к нему не относится.
        tolerance = timedelta(days=self.config.tolerance_days)
        in_window = (
            stage.planned_start is None or latest_obs_on >= stage.planned_start - tolerance
        ) and (stage.planned_end is None or latest_obs_on <= stage.planned_end + tolerance)
        if not in_window and latest_obs_on not in status_basis_dates:
            if len(observations) >= 2:
                deviations.extend(self._check_no_progress(observations, stage, rule))
            return deviations

        # 2. missing_equipment — по окну последних дат, а не по одному дню
        deviations.extend(self._check_missing_equipment(stage, observations, rule, plan))

        # 2b. Неполный комплект (clean-mvp) вместо прежней гипотезы «Нет ожидаемой
        # техники»: маркер этапа виден, а машины комплекта нет на последних датах
        deviations.extend(
            self._check_incomplete_kit(stage, rule, observations, equipment_names, plan)
        )

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
                    title=f"Простой: {idle_names}",
                    equipment_type_id=idle_eq[0].equipment_type_id,
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
                    title=f"Вне зоны: {out_zone_names}",
                    equipment_type_id=out_zone_eq[0].equipment_type_id,
                )
            )

        # 7. no_progress
        if len(observations) >= 2:
            deviations.extend(self._check_no_progress(observations, stage, rule))

        return deviations

    def _check_missing_equipment(
        self,
        stage: StageInput,
        observations: Sequence[ObservationInput],
        rule: RuleInput,
        plan: _Plan,
    ) -> list[DeviationResult]:
        """«Нет маркерной техники» (как в clean-mvp): по окну дат, а не по одному дню.

        Срабатывает, когда допуск после планового начала прошёл и последние `window_dates`
        дат наблюдений — внутри этапа, все с высокой наблюдаемостью и ни в одну не выполнен
        ни один набор. Один день без маркера ничего не доказывает: техника могла работать
        вне кадра (Березники на стенде: «Критично» по одному дню, датированному по имени
        файла).
        """
        kits = [
            kit
            for kit in rule.effective_kits
            if any(r.obligation == "normative" for r in kit.requirements)
        ]
        latest = observations[-1]
        day = latest.observed_on
        tolerance = timedelta(days=self.config.tolerance_days)
        if (
            not kits
            or stage.planned_start is None
            or day <= stage.planned_start + tolerance
            or day.weekday() not in self.config.workdays
        ):
            return []
        tail = observations[-self.config.window_dates :]
        if len(tail) < self.config.window_dates:
            return []
        # Каждый день окна должен отличать этап: иначе отсутствие маркера ничего не значит
        if any(
            o.observed_on < stage.planned_start
            or o.observability != Observability.HIGH.value
            or not plan.markers_on(stage, o.observed_on)
            or self._is_marker_day(stage, kits, o, plan)
            for o in tail
        ):
            return []

        def no_marker(o: ObservationInput) -> bool:
            return o.observed_on >= (stage.planned_start or o.observed_on) and not (
                self._is_marker_day(stage, kits, o, plan)
            )

        days = (day - stage.planned_start).days
        tail_dates = tuple(o.observed_on for o in tail)
        return [
            DeviationResult(
                stage_id=stage.stage_id,
                type=DeviationType.MISSING_EQUIPMENT,
                is_hypothesis=False,
                severity=self._severity(days, Confidence.HIGH, latest),
                confidence=Confidence.HIGH,
                period_start=self._streak_start(observations, no_marker),
                period_end=day,
                expected="Присутствие маркерной техники этапа",
                observed=(
                    "Маркерная техника не найдена ни на одном снимке за "
                    f"{len(tail)} {_dates_word(len(tail))}: "
                    + ", ".join(f"{d:%d.%m}" for d in tail_dates)
                ),
                limits_text=(
                    "Не доказывает остановку работ вне времени и мест съёмки — "
                    "техника могла работать вне зоны обзора камер."
                ),
                rule_id=rule.rule_id,
                evidence_dates=tail_dates,
                title="Маркерная техника не найдена",
            )
        ]

    def _severity(self, days: int, confidence: Confidence, latest: ObservationInput) -> Severity:
        """«Критично» — только при уверенности не ниже средней, высокой наблюдаемости
        последнего дня и не раньше `critical_days` от начала этапа (или подряд)."""
        if (
            days >= self.config.critical_days
            and confidence != Confidence.LOW
            and latest.observability == Observability.HIGH.value
        ):
            return Severity.CRITICAL
        return Severity.ATTENTION

    @staticmethod
    def _streak_start(
        observations: Sequence[ObservationInput], holds: Callable[[ObservationInput], bool]
    ) -> date:
        """Первый день непрерывной серии с конца, на которой условие выполняется."""
        start = observations[-1].observed_on
        for current in reversed(observations):
            if not holds(current):
                break
            start = current.observed_on
        return start

    @staticmethod
    def _stage_classes(rule: RuleInput) -> frozenset[uuid.UUID]:
        """Вся техника методики этапа: требования и наборы."""
        ids = {r.equipment_type_id for r in rule.requirements}
        for kit in rule.effective_kits:
            ids.update(r.equipment_type_id for r in kit.requirements)
        return frozenset(ids)

    @staticmethod
    def _fits(
        equipment_type_id: uuid.UUID,
        classes: frozenset[uuid.UUID],
        coarse: Mapping[uuid.UUID, frozenset[uuid.UUID]],
    ) -> bool:
        """Подходит ли машина этапу: тот же класс или «тип не определён» того же рода."""
        return equipment_type_id in classes or bool(
            coarse.get(equipment_type_id, frozenset()) & classes
        )

    def _check_mismatch_and_extra(
        self,
        stages: Sequence[StageInput],
        rules_by_stage: Mapping[uuid.UUID, RuleInput],
        statuses: Sequence[StageStatusResult],
        observations: Sequence[ObservationInput],
        names: Mapping[uuid.UUID, str],
        coarse: Mapping[uuid.UUID, frozenset[uuid.UUID]],
        stationary: frozenset[uuid.UUID] = frozenset(),
    ) -> list[DeviationResult]:
        """«Несоответствие этапу» и «Лишняя техника» по машинам последнего дня.

        Как в clean-mvp: машина, которой нет ни в одном идущем по плану этапе, — одна
        строка на машину. Есть в методике другого этапа — «Несоответствие» к идущим этапам;
        нет ни в одном этапе — гипотеза «Лишняя техника». Машины вне рабочей зоны не
        считаются: они ни о чём на площадке не говорят. «Критично» — только когда машина
        видна `critical_days` дат подряд; один снимок — «Внимание». Машина затянувшегося
        этапа без идущих этапов — это уже «Отставание», второй строкой не повторяется.
        """
        if not observations:
            return []
        latest = observations[-1]
        day = latest.observed_on
        tolerance = timedelta(days=self.config.tolerance_days)
        # Этапы с методикой — и ещё не наступившие: их машина тоже «чужая» для идущих
        not_checked = {s.stage_id for s in statuses if s.status == StageStatusValue.NOT_CHECKED}
        checked = [
            s
            for s in stages
            if (rule := rules_by_stage.get(s.stage_id)) is not None
            and rule.is_verifiable
            and s.stage_id not in not_checked
            and any(
                r.obligation == "normative" for kit in rule.effective_kits for r in kit.requirements
            )
        ]
        classes = {s.stage_id: self._stage_classes(rules_by_stage[s.stage_id]) for s in checked}
        expected = [
            s
            for s in checked
            if (s.planned_start is None or day >= s.planned_start - tolerance)
            and (s.planned_end is None or day <= s.planned_end + tolerance)
        ]
        all_classes = frozenset().union(*classes.values()) if classes else frozenset()
        lagging = {s.stage_id for s in statuses if s.status == StageStatusValue.BEHIND}
        plan_now = ", ".join(f"«{s.name}»" for s in expected)
        expected_text = (
            f"Техника этапов, идущих по плану на {day:%d.%m}: {plan_now}."
            if expected
            else f"По плану на {day:%d.%m} этапов с техникой нет."
        )
        observability = self._str_to_confidence(latest.observability)

        out: list[DeviationResult] = []
        for eq in sorted(latest.equipment, key=lambda e: names.get(e.equipment_type_id, "")):
            code = eq.equipment_type_id
            # Неподвижная техника (башенный кран) стоит весь срок и о том, какой этап
            # идёт, не говорит ничего: ни «несоответствия», ни «лишней техники» (clean-mvp)
            if code in stationary:
                continue
            if eq.in_zone is False or any(
                self._fits(code, classes[s.stage_id], coarse) for s in expected
            ):
                continue
            name = names.get(code, str(code))

            def seen(o: ObservationInput, code: uuid.UUID = code) -> bool:
                """Машина в зоне, и в этот день её не объясняет ни один идущий этап (clean-mvp,
                _sees_unexplained): 09–10.09 буровая своя у свай, серия — с 16.09."""
                return any(
                    e.equipment_type_id == code and e.in_zone is not False for e in o.equipment
                ) and not any(
                    self._fits(code, classes[s.stage_id], coarse)
                    for s in checked
                    if (s.planned_start is None or o.observed_on >= s.planned_start - tolerance)
                    and (s.planned_end is None or o.observed_on <= s.planned_end + tolerance)
                )

            start = self._streak_start(observations, seen)
            streak = tuple(o.observed_on for o in observations if start <= o.observed_on <= day)
            confidence = self._min_confidence(self._str_to_confidence(eq.confidence), observability)
            if not self._fits(code, all_classes, coarse):
                out.append(
                    DeviationResult(
                        stage_id=None,
                        type=DeviationType.EXTRA_EQUIPMENT,
                        is_hypothesis=True,
                        severity=Severity.ATTENTION,
                        confidence=self._min_confidence(confidence, Confidence.MEDIUM),
                        period_start=start,
                        period_end=day,
                        expected="Техника из методики одного из этапов графика.",
                        observed=(
                            f"{name} (не менее {eq.count_min}) не входит ни в один этап графика."
                        ),
                        limits_text=(
                            "Гипотеза — не доказывает незапланированные работы, "
                            "техника могла быть на соседнем объекте или проезжать мимо."
                        ),
                        rule_id=None,
                        evidence_dates=streak,
                        title=f"{name}: нет в графике",
                        equipment_type_id=code,
                    )
                )
                continue
            owner = min(
                (s for s in checked if self._fits(code, classes[s.stage_id], coarse)),
                key=lambda s: (s.stage_id not in lagging, s.position),
            )
            if owner.stage_id in lagging and not expected:
                continue
            targets: list[StageInput | None] = list(expected) or [None]
            for target in targets:
                days = 0
                if target is not None and target.planned_start is not None:
                    days = min(len(streak), (day - target.planned_start).days)
                rule = rules_by_stage[(target or owner).stage_id]
                out.append(
                    DeviationResult(
                        stage_id=target.stage_id if target else None,
                        type=DeviationType.STAGE_MISMATCH,
                        is_hypothesis=False,
                        severity=self._severity(days, confidence, latest),
                        confidence=confidence,
                        period_start=start,
                        period_end=day,
                        expected=expected_text,
                        observed=(
                            f"{name} (не менее {eq.count_min}) — техника этапа "
                            f"«{owner.name}», который по плану сейчас не идёт."
                        ),
                        limits_text=(
                            "Не доказывает завершённость этапа или смену техники — "
                            "техника могла быть вне зоны обзора камер."
                        ),
                        rule_id=rule.rule_id,
                        evidence_dates=streak,
                        title=f"{name}: техника этапа «{owner.name}»",
                        equipment_type_id=code,
                        cause_stage_id=owner.stage_id if owner.stage_id in lagging else None,
                    )
                )
        return out

    def _check_incomplete_kit(
        self,
        stage: StageInput,
        rule: RuleInput,
        observations: Sequence[ObservationInput],
        names: Mapping[uuid.UUID, str],
        plan: _Plan,
    ) -> list[DeviationResult]:
        """«Неполный комплект» (clean-mvp, _incomplete_kit).

        Последние `window_dates` дат — все с высокой наблюдаемостью, в одну из них виден
        маркер этапа, а нормативной (или логической) машины его комплекта нет ни в одну.
        Нормативная и логическая нехватка — разные строки; логическая — пример из ТЗ:
        экскаватор в котловане есть, самосвалов нет — темп работ может упасть.
        """
        tail = observations[-self.config.window_dates :]
        if len(tail) < self.config.window_dates or any(
            o.observability != Observability.HIGH.value for o in tail
        ):
            return []
        # Только этап, идущий по плану в последний день: у закончившегося нехватка машин —
        # не отклонение (clean-mvp, ctx.expected)
        if not plan.in_window(stage, tail[-1].observed_on, self.config.tolerance_days):
            return []
        kits = [
            kit
            for kit in rule.effective_kits
            if any(r.obligation == "normative" for r in kit.requirements)
        ]
        if not kits or not any(
            plan.markers_on(stage, o.observed_on) and self._is_marker_day(stage, kits, o, plan)
            for o in tail
        ):
            return []

        def ids(*obligations: str) -> frozenset[uuid.UUID]:
            return frozenset(
                r.equipment_type_id
                for kit in kits
                for r in kit.requirements
                if r.obligation in obligations
            )

        normative = ids("normative") - plan.stationary
        logical = ids("logical") - normative - plan.stationary
        groups: dict[str, frozenset[uuid.UUID]] = {}
        for kit in kits:
            for r in kit.requirements:
                if r.group:
                    groups[r.group] = groups.get(r.group, frozenset()) | {r.equipment_type_id}

        def present(o: ObservationInput) -> set[uuid.UUID]:
            # «Экскаватор (тип не определён)» закрывает гусеничный экскаватор комплекта
            # (clean-mvp, covering): нехватки такой машины нет
            seen = {eq.equipment_type_id for eq in o.equipment if eq.count_min >= 1}
            return seen.union(*(plan.coarse.get(code, frozenset()) for code in seen))

        out: list[DeviationResult] = []
        tail_dates = tuple(o.observed_on for o in tail)
        for needed, kind, pace in (
            (normative, "нормативная", ""),
            (logical, "логическая", " Без этой техники возможно снижение темпа работ."),
        ):
            missing = frozenset(needed).difference(*(present(o) for o in tail))
            # Группа взаимозаменяемой техники (сваебойная) не нехватка, пока в каждый день
            # есть хоть одна её машина (clean-mvp: требование на группу)
            for members in groups.values():
                if any(members & present(o) for o in tail):
                    missing -= members
            if not missing:
                continue
            listed = self._format_equipment_names(missing, names)
            lowered = ", ".join(n[:1].lower() + n[1:] for n in listed.split(", "))

            def holds(o: ObservationInput, missing: frozenset[uuid.UUID] = missing) -> bool:
                return self._is_marker_day(stage, kits, o, plan) and not (missing & present(o))

            out.append(
                DeviationResult(
                    stage_id=stage.stage_id,
                    type=DeviationType.INCOMPLETE_KIT,
                    is_hypothesis=False,
                    severity=Severity.ATTENTION,
                    confidence=Confidence.HIGH,
                    period_start=self._streak_start(observations, holds),
                    period_end=tail_dates[-1],
                    expected=f"{listed} — {kind} техника этапа «{stage.name}».",
                    observed=(
                        f"Маркер этапа виден, а {lowered} — нет ни на одном снимке за "
                        f"{len(tail)} {_dates_word(len(tail))}: "
                        + ", ".join(f"{d:%d.%m}" for d in tail_dates)
                        + f".{pace}"
                    ),
                    limits_text=(
                        "Не доказывает, что техники нет на площадке: она могла работать вне "
                        "кадра или между съёмками."
                    ),
                    rule_id=rule.rule_id,
                    evidence_dates=tail_dates,
                    title=(
                        f"Неполный комплект: {'не виден' if len(missing) == 1 else 'не видны'} "
                        f"{lowered}"
                    ),
                    # Недостающая машина (первая по названию) — для устойчивого ключа
                    # отклонения: два «Неполных комплекта» этапа иначе делили бы id и решение
                    equipment_type_id=min(missing, key=lambda i: (names.get(i, ""), str(i))),
                )
            )
        return out

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
                            title="Нет прогресса",
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


def delay_text(status: StageStatusResult) -> str:
    """«14–74 дн.», «от 60 дн.», «до 63 дн.» или «7 дн.» — как format_delay в clean-mvp."""
    lo, hi = status.delay_min, status.delay_max
    if lo is None and hi is None:
        return f"{status.delay_days} дн."
    if lo is not None and hi is not None:
        return f"{lo} дн." if lo == hi else f"{lo}–{hi} дн."
    return f"от {lo} дн." if lo is not None else f"до {hi} дн."


def _dates_word(n: int) -> str:
    """«дату», «даты», «дат» для «за N …»."""
    if n % 10 == 1 and n % 100 != 11:
        return "дату"
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return "даты"
    return "дат"


def _insufficient(reason: str) -> SummaryResult:
    return SummaryResult(Verdict.INSUFFICIENT_DATA, None, None, None, reason)


def _explain_behind(stage: StageInput, status: StageStatusResult, today: date) -> str:
    """Пояснение итога по этапу с наибольшим отставанием."""
    prefix = f"Измерено по этапу «{stage.name}»"
    accuracy = "Точность не выше частоты съёмки."
    if status.status == StageStatusValue.NOT_STARTED:
        start = f"{stage.planned_start:%d.%m}" if stage.planned_start else "—"
        return (
            f"{prefix}: плановое начало {start}, к {today:%d.%m} маркерная техника этапа "
            "не найдена при высокой наблюдаемости. Это нижняя граница."
        )
    first = status.basis_dates[0] if status.basis_dates else None
    if (
        stage.planned_start is not None
        and first is not None
        and status.delay_days == (first - stage.planned_start).days
    ):
        return (
            f"{prefix}: плановое начало {stage.planned_start:%d.%m}, маркерная техника "
            f"появилась {first:%d.%m}. {accuracy}"
        )
    last = status.basis_dates[-1] if status.basis_dates else today
    end = f"{stage.planned_end:%d.%m}" if stage.planned_end else "—"
    return (
        f"{prefix}: плановый конец {end}, маркерная техника наблюдается и {last:%d.%m}. {accuracy}"
    )


def summarize(
    stages: Sequence[StageInput],
    statuses: Sequence[StageStatusResult],
    observations: Sequence[ObservationInput],
    today: date,
    config: EngineConfig,
) -> SummaryResult:
    """Итог по объекту (как в clean-mvp, engine/summary.py).

    Итог — интервал одного, худшего этапа, а не склейка границ разных этапов: пояснение под
    итогом говорит про тот же этап. «Не начат» с отставанием «от N дней» — тоже отставание,
    иначе итог «Отклонений нет» стоял бы рядом с критичными отклонениями этого этапа.
    """
    if not observations:
        return _insufficient("Снимков с датой нет.")
    latest = observations[-1]
    if (today - latest.observed_on).days > config.stale_data_days:
        return _insufficient(
            f"Данные устарели: последнее наблюдение {latest.observed_on:%d.%m.%Y}."
        )
    workdays = [o for o in observations if o.observed_on.weekday() in config.workdays]
    last_workday = workdays[-1] if workdays else latest
    # Низкая наблюдаемость последнего дня — оговорка к отставанию, а не его отмена: строка
    # отставания уже в отклонениях
    poorly_seen = last_workday.observability == Observability.LOW.value

    considered = [s for s in statuses if s.status != StageStatusValue.NOT_CHECKED]
    lagging = (
        (StageStatusValue.BEHIND,)
        if poorly_seen
        else (StageStatusValue.BEHIND, StageStatusValue.NOT_STARTED)
    )
    behind = [s for s in considered if s.status in lagging and s.delay_days]
    if behind:
        # Худший — с наибольшей нижней границей, при равной — без верхней границы
        # Худший — с наибольшей доказанной задержкой (нижняя граница), при равной — без
        # верхней границы или с большей (clean-mvp, worst_key)
        worst = max(
            behind,
            key=lambda s: (
                s.delay_min or 0,
                s.delay_max if s.delay_max is not None else 10**6,
            ),
        )
        stage = next(st for st in stages if st.stage_id == worst.stage_id)
        reason = _explain_behind(stage, worst, today)
        if poorly_seen:
            reason += " Наблюдаемость последнего рабочего дня низкая: оценка по прошлым снимкам."
        return SummaryResult(
            verdict=Verdict.BEHIND,
            delay_days_min=worst.delay_min,
            delay_days_max=worst.delay_max,
            stage_id=worst.stage_id,
            reason=reason,
        )

    if poorly_seen:
        return _insufficient("Наблюдаемость последнего рабочего дня низкая.")
    if not considered:
        return _insufficient("Нет этапов, которые проверяются по технике сейчас.")
    if all(s.status == StageStatusValue.NOT_OBSERVED for s in considered):
        return _insufficient("По идущим этапам наблюдаемость недостаточна.")
    return SummaryResult(Verdict.NO_DEVIATIONS, None, None, None, "Отклонений не выявлено.")
