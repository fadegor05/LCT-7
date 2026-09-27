# LCT-15: Имена техники в отклонениях + missing_logical_equipment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Отклонения показывают названия техники вместо сырых UUID, и отсутствие «логической» (ожидаемой, но не обязательной) техники методики на этапе даёт отдельное мягкое предупреждение.

**Architecture:** `RuleEngine.compute_site` получает опциональный `equipment_names` (dict UUID→имя), `RecomputeCoordinator` строит его из уже существующего `EquipmentCatalog` и передаёт. Новый `_check_missing_logical_equipment` в движке, новый `DeviationType`.

**Tech Stack:** Python 3.11/3.12, SQLAlchemy async (только для `EquipmentCatalog`, уже существует), pytest; TypeScript/Zod на фронте.

**Spec:** `docs/superpowers/plans/2026-09-27-lct-15-deviation-names-and-logical-spec.md`

**База:** ветка `claude/laughing-hypatia-20ipgi` (PR #20). **Отдельный PR поверх #20**, не зависит от LCT-14 и не докидывается в сам #20.

## Global Constraints

- `RuleEngine.compute_site` обязан оставаться совместим со старыми 4-позиционными вызовами (~36 существующих вызовов в тестах движка) — новый параметр `equipment_names` только keyword, с дефолтом.
- `_format_equipment_names` не должна падать на UUID, отсутствующем в словаре — fallback на `str(uuid)`.
- `MISSING_LOGICAL_EQUIPMENT`: `severity=Severity.ATTENTION`, `is_hypothesis=True` (мягкое предупреждение, не CRITICAL — logical-техника не обязательна для подтверждения этапа, в отличие от normative-маркеров).
- `AssessmentProvider` (DI) не меняется — `EquipmentCatalog` уже зарегистрирован в контейнере (`methodology/provider.py`), Dishka подключит его в `RecomputeCoordinator` по типу автоматически.
- Весь существующий тестовый набор доменов `assessment`/`methodology` обязан пройти без изменений, кроме явно перечисленных точечных правок тестовых хелперов.

## Review Focus

- Названия резолвятся детерминированно (сортировка) — тест не должен зависеть от порядка обхода set/dict.
- `_check_missing_logical_equipment` не должна срабатывать, если у правила вообще нет `logical`-требований (иначе — ложные предупреждения на каждом этапе без logical-техники в методике).
- `_check_missing_logical_equipment` должна учитывать `observability` так же строго, как `_check_missing_equipment` (только `"high"`) — иначе плохая наблюдаемость сама по себе будет давать предупреждение, что неверно.
- Blast radius на тесты: только `create_coordinator` (test_assessment_coordinator.py) и прямая конструкция в `test_ml_parity.py` нуждаются в новой зависимости `equipment_catalog` — оба уже используют `request_container.get(...)` для остальных зависимостей, добавить `EquipmentCatalog` тем же способом.

---

## Task 1: Имена техники + missing_logical_equipment в движке, координаторе и фронтенде

**Files:**
- Modify: `backend/app/domains/assessment/models.py`
- Modify: `backend/app/domains/assessment/engine.py`
- Modify: `backend/app/domains/assessment/coordinator.py`
- Modify: `backend/tests/test_assessment_coordinator.py`
- Modify: `backend/tests/test_ml_parity.py`
- Test: `backend/tests/test_assessment_engine_deviations.py`
- Modify: `frontend/src/api/schemas.ts`
- Modify: `frontend/src/lib/labels.ts`

**Interfaces:**
- Consumes: `EquipmentCatalog` (уже существует, `methodology/catalog.py`, `by_id`/`all`, APP-scope, кэш).
- Produces: `RuleEngine.compute_site(..., equipment_names=...)` — новый опциональный параметр, потребляется только `RecomputeCoordinator`.

- [ ] **Step 1: Новый `DeviationType`**

В `backend/app/domains/assessment/models.py`, в `class DeviationType(StrEnum)`, добавь новое значение сразу после `MISSING_EQUIPMENT`:

```python
class DeviationType(StrEnum):
    """Тип обнаруженного отклонения от плана."""

    MISSING_EQUIPMENT = "missing_equipment"
    MISSING_LOGICAL_EQUIPMENT = "missing_logical_equipment"
    STAGE_MISMATCH = "stage_mismatch"
    STALE_DATA = "stale_data"
    IDLE = "idle"
    EXTRA_EQUIPMENT = "extra_equipment"
    OUT_OF_ZONE = "out_of_zone"
    NO_PROGRESS = "no_progress"
```

- [ ] **Step 2: Написать падающие тесты движка**

Добавь в `backend/tests/test_assessment_engine_deviations.py`, в конец класса `TestDeviationStageMismatch` (после `test_stage_mismatch_wrong_equipment_type`), тест на резолвинг имени в `stage_mismatch`:

```python
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
```

Добавь новый класс в конец файла (после `TestNotCheckedStageProducesNoDeviations`):

```python
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
```

Run: `cd backend && uv run pytest tests/test_assessment_engine_deviations.py -v`
Expected: FAIL — `TypeError` (лишний позиционный аргумент `equipment_names`, которого ещё нет в сигнатуре `compute_site`) и/или `AttributeError`/`ImportError` для `MISSING_LOGICAL_EQUIPMENT`.

- [ ] **Step 3: Добавить `equipment_names` в `compute_site` и хелпер `_format_equipment_names`**

В `backend/app/domains/assessment/engine.py` замени импорт:

```python
from collections.abc import Sequence
```

на:

```python
from collections.abc import Iterable, Mapping, Sequence
```

Замени сигнатуру и первые строки `compute_site`:

```python
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
```

(Дальше в теле метода ничего не меняется до цикла отклонений по этапам.)

Замени вызов `_check_stage_deviations` внутри цикла:

```python
            if stage_status is not None and stage_status.status != StageStatusValue.NOT_CHECKED:
                deviations.extend(
                    self._check_stage_deviations(
                        stage, rule, sorted_observations, today, stage_status.basis_dates
                    )
                )
```

на:

```python
            if stage_status is not None and stage_status.status != StageStatusValue.NOT_CHECKED:
                deviations.extend(
                    self._check_stage_deviations(
                        stage, rule, sorted_observations, today, stage_status.basis_dates, names
                    )
                )
```

- [ ] **Step 4: Обновить `_check_stage_deviations`: сигнатура, имена вместо UUID, вызов нового чек-метода**

Замени сигнатуру `_check_stage_deviations`:

```python
    def _check_stage_deviations(
        self,
        stage: StageInput,
        rule: RuleInput | None,
        observations: Sequence[ObservationInput],
        today: date,
        status_basis_dates: tuple[date, ...],
    ) -> list[DeviationResult]:
```

на:

```python
    def _check_stage_deviations(
        self,
        stage: StageInput,
        rule: RuleInput | None,
        observations: Sequence[ObservationInput],
        today: date,
        status_basis_dates: tuple[date, ...],
        equipment_names: Mapping[uuid.UUID, str],
    ) -> list[DeviationResult]:
```

Сразу после блока `# 2. missing_equipment` (после `deviations.extend(self._check_missing_equipment(...))`), добавь новый шаг «2b»:

```python
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
```

Замени блок STAGE_MISMATCH (добавляется локальная переменная перед `deviations.append`, `observed=` использует её):

```python
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
```

(Только `observed=` изменился на `f"Техника: {mismatch_names}"` и добавлена строка `mismatch_names = ...` перед `deviations.append(...)` — остальное тело блока STAGE_MISMATCH, включая условие `if` и фильтрацию missing_equipment после него, не меняется.)

Замени блок IDLE:

```python
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
```

Замени блок EXTRA_EQUIPMENT:

```python
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
```

Замени блок OUT_OF_ZONE:

```python
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
```

- [ ] **Step 5: Добавить `_format_equipment_names` и `_check_missing_logical_equipment`**

Сразу после метода `_check_missing_equipment` (перед `_check_no_progress`), добавь:

```python
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
                    f"Не обнаружена: "
                    f"{self._format_equipment_names(missing_ids, equipment_names)}"
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
```

Добавь `_format_equipment_names` сразу после `_check_missing_logical_equipment`:

```python
    def _format_equipment_names(
        self, equipment_type_ids: Iterable[uuid.UUID], equipment_names: Mapping[uuid.UUID, str]
    ) -> str:
        """Отобразить типы техники по именам (LCT-15), а не по UUID.

        Каталог передаётся снаружи — движок не знает о БД. Отсутствующее в
        словаре имя — fallback на сам UUID (деградация, не падение).
        """
        names = sorted(equipment_names.get(eid, str(eid)) for eid in equipment_type_ids)
        return ", ".join(names)
```

- [ ] **Step 6: Прогнать тесты движка**

Run: `cd backend && uv run pytest tests/test_assessment_engine_deviations.py tests/test_assessment_engine_status.py -v`
Expected: PASS — все тесты обоих файлов зелёные, включая новые.

- [ ] **Step 7: Прокинуть `EquipmentCatalog` через `RecomputeCoordinator`**

В `backend/app/domains/assessment/coordinator.py`:

1. Добавь импорт:

```python
from app.domains.methodology.catalog import EquipmentCatalog
```

(рядом с существующим `from app.domains.methodology.repository import MethodologyRepository`)

2. В `__init__`, добавь параметр `equipment_catalog: EquipmentCatalog` **после** `detection_repo: DetectionRepository,` и **перед** `session: AsyncSession,` (обязательный параметр без дефолта, как и остальные репозитории — не опционально):

```python
        photo_repo: PhotoRepository,
        detection_repo: DetectionRepository,
        equipment_catalog: EquipmentCatalog,
        session: AsyncSession,
        today: Clock = date.today,
    ) -> None:
```

В теле `__init__`, после `self._detection_repo = detection_repo`, добавь:

```python
        self._equipment_catalog = equipment_catalog
```

Добавь `equipment_catalog` в docstring `__init__` рядом с остальными репозиториями:
```
            equipment_catalog: EquipmentCatalog — резолвинг названий техники для отклонений (LCT-15).
```

3. В `recompute_site`, перед шагом 5 (`computation = self._engine.compute_site(...)`), добавь построение словаря имён:

```python
            # Шаг 5: Запустить engine
            equipment_names = {item.id: item.title for item in await self._equipment_catalog.all()}
            computation = self._engine.compute_site(
                stages, rules_by_stage, observations, self._today(), equipment_names
            )
```

(это заменяет текущую строку `computation = self._engine.compute_site(stages, rules_by_stage, observations, self._today())`)

- [ ] **Step 8: Обновить тестовые хелперы, чтобы передавать `equipment_catalog`**

В `backend/tests/test_assessment_coordinator.py`:

1. Добавь импорт:

```python
from app.domains.methodology.catalog import EquipmentCatalog
```

2. В функции `create_coordinator`, добавь получение каталога из контейнера и передачу в конструктор:

```python
async def create_coordinator(
    container: object, engine_config: EngineConfig
) -> RecomputeCoordinator:
    """Создать RecomputeCoordinator из контейнера."""
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        stage_status_repo = StageStatusRepository(session)
        deviation_repo = DeviationRepository(session)
        deviation_evidence_repo = DeviationEvidenceRepository(session)
        status_basis_repo = StatusBasisRepository(session)
        schedule_repo = ScheduleRepository(session)
        methodology_repo = MethodologyRepository(session)
        observation_repo = ObservationRepository(session)
        observed_equipment_repo = ObservedEquipmentRepository(session)
        photo_repo = PhotoRepository(session)
        detection_repo = DetectionRepository(session)
        equipment_catalog = await request_container.get(EquipmentCatalog)

        engine = RuleEngine(engine_config)
        coordinator = RecomputeCoordinator(
            engine=engine,
            stage_status_repo=stage_status_repo,
            deviation_repo=deviation_repo,
            deviation_evidence_repo=deviation_evidence_repo,
            status_basis_repo=status_basis_repo,
            schedule_repo=schedule_repo,
            methodology_repo=methodology_repo,
            observation_repo=observation_repo,
            observed_equipment_repo=observed_equipment_repo,
            photo_repo=photo_repo,
            detection_repo=detection_repo,
            equipment_catalog=equipment_catalog,
            session=session,
        )
        return coordinator
```

(единственные изменения: новая строка `equipment_catalog = await request_container.get(EquipmentCatalog)` и новый аргумент `equipment_catalog=equipment_catalog,` в конструкторе — всё остальное идентично.)

В `backend/tests/test_ml_parity.py`:

1. Добавь импорт:

```python
from app.domains.methodology.catalog import EquipmentCatalog
```

2. Найди блок, где через `request_container.get(...)` собираются зависимости для `RecomputeCoordinator` (там же, где `detection_repo = await request_container.get(DetectionRepository)`), и добавь сразу после него:

```python
        equipment_catalog = await request_container.get(EquipmentCatalog)
```

3. В самом вызове `RecomputeCoordinator(...)` добавь `equipment_catalog=equipment_catalog,` (например, сразу после `detection_repo=detection_repo,`).

- [ ] **Step 9: Прогнать весь backend-набор**

Run: `cd backend && uv run pytest -q`
Expected: PASS — весь набор зелёный, включая `test_ml_parity.py` (может занять больше времени — там реальный прогон демо-детекций).

Run: `cd backend && uv run mypy app/domains/assessment/engine.py app/domains/assessment/coordinator.py app/domains/assessment/models.py`
Expected: без ошибок.

Run: `cd backend && uv run ruff check . && uv run ruff format --check .`
Expected: без ошибок (если форматирование многострочных f-строк не совпадёт — прогони `uv run ruff format .` и повтори check).

- [ ] **Step 10: Фронтенд — новый тип отклонения**

В `frontend/src/api/schemas.ts` найди:

```typescript
/** assessment.models.DeviationType */
export const deviationTypeSchema = z.enum([
  'missing_equipment',
  'stage_mismatch',
  'stale_data',
  'idle',
  'extra_equipment',
  'out_of_zone',
  'no_progress',
])
```

Замени на:

```typescript
/** assessment.models.DeviationType */
export const deviationTypeSchema = z.enum([
  'missing_equipment',
  'missing_logical_equipment',
  'stage_mismatch',
  'stale_data',
  'idle',
  'extra_equipment',
  'out_of_zone',
  'no_progress',
])
```

В `frontend/src/lib/labels.ts` найди:

```typescript
export const deviationTypeLabels: Record<DeviationType, string> = {
  missing_equipment: 'Нет нужной техники',
  stage_mismatch: 'Несоответствие этапу',
  stale_data: 'Данные устарели',
  idle: 'Простой техники',
  extra_equipment: 'Лишняя техника',
  out_of_zone: 'Вне рабочей зоны',
  no_progress: 'Нет прогресса',
}
```

Замени на:

```typescript
export const deviationTypeLabels: Record<DeviationType, string> = {
  missing_equipment: 'Нет нужной техники',
  missing_logical_equipment: 'Нет ожидаемой техники',
  stage_mismatch: 'Несоответствие этапу',
  stale_data: 'Данные устарели',
  idle: 'Простой техники',
  extra_equipment: 'Лишняя техника',
  out_of_zone: 'Вне рабочей зоны',
  no_progress: 'Нет прогресса',
}
```

- [ ] **Step 11: Прогнать фронтенд-проверку**

Run: `cd frontend && pnpm check`
Expected: PASS — tsc (в т.ч. `Record<DeviationType, string>` со всеми ключами), eslint, stylelint, prettier, vitest — без новых failures.

- [ ] **Step 12: Commit**

```bash
git add backend/app/domains/assessment/models.py backend/app/domains/assessment/engine.py backend/app/domains/assessment/coordinator.py backend/tests/test_assessment_engine_deviations.py backend/tests/test_assessment_coordinator.py backend/tests/test_ml_parity.py frontend/src/api/schemas.ts frontend/src/lib/labels.ts
git commit -m "feat(assessment): equipment names in deviation text, missing_logical_equipment (LCT-15)

Deviation evidence text (stage_mismatch/idle/extra_equipment/out_of_zone)
put raw equipment_type_id UUIDs into observed/expected instead of names,
even though EquipmentCatalog already existed elsewhere in the codebase
and just wasn't threaded through engine/coordinator. RuleEngine.compute_site
now takes an optional equipment_names dict (built by RecomputeCoordinator
from EquipmentCatalog) and a new _format_equipment_names helper resolves
IDs to names with a safe UUID fallback.

Also: obligation="logical" equipment (expected on a stage per methodology,
but not required to confirm it started) never produced its own signal —
only "normative" markers did. missing_logical_equipment adds a soft
ATTENTION/hypothesis warning when high-observability data shows the
normative marker but not the logical equipment, matching the ticket's
example ('excavator present, no dump trucks').

Deliberately out of scope (see spec ruling): per-site dedup of idle/
no_progress, and the markers_active_now window-scoping question — both
need a design decision this session couldn't get sign-off on, and both
touch already-tested status-computation logic where a wrong guess is
expensive to unwind."
```
