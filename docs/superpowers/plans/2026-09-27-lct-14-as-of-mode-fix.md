# LCT-14: Дата расчёта per-площадке (last_observation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Дать возможность считать статусы/отклонения от опорной даты, специфичной для каждой площадки (дата последнего наблюдения на ней — как в ML-отчёте), чтобы демо на площадках из разных лет (2023–2026) не показывало ложный `stale_data`/сплошной `behind` только из-за возраста данных.

**Architecture:** Новый режим `AsOfMode` в настройках (`today`/`last_observation`/`fixed`), новый `AsOfConfig`, разрешаемый в `RecomputeCoordinator._resolve_as_of()` перед вызовом движка. `RuleEngine` не меняется — получает уже готовую дату.

**Tech Stack:** Python 3.11/3.12, pydantic-settings, Dishka, pytest.

**Spec:** `docs/superpowers/plans/2026-09-27-lct-14-as-of-mode-spec.md`

**База:** ветка `claude/laughing-hypatia-20ipgi` (PR #20). **Этот PR отдельный поверх #20** — по итогам ревью PR #20 в него больше не докидываем задачи.

## Global Constraints

- `RuleEngine`/`engine.py` не трогать — они получают уже вычисленную конкретную `date`.
- Существующее поведение по умолчанию (`AsOfMode.TODAY`) обязано быть побитово тем же, что сейчас: `date.today()` через `Clock`, без изменений для вызовов, не указавших `as_of_config`.
- `RecomputeCoordinator.__init__`: новый параметр `as_of_config` обязан иметь значение по умолчанию, чтобы все существующие прямые конструирования (тесты) не ломались.
- `test_ml_parity.py` не трогать.

## Review Focus

- `last_observation` без наблюдений на площадке не должен падать — тихий fallback на `today`.
- `fixed` без настроенной `as_of_override` не должен падать — тихий fallback на `today` (документировано в спеке, не баг).
- `max(observed_on)` берётся по ВСЕМ наблюдениям площадки, а не по какому-то подмножеству (например, не только по наблюдениям с высокой observability) — семантика должна совпадать с ML: `as_of = states[-1]["date"]`, последняя дата в хронологии.
- Циклический импорт: `core/settings.py` не должен зависеть от `domains/assessment` — только наоборот.

---

## Task 1: `AsOfMode`/`AsOfConfig` + `_resolve_as_of` в координаторе

**Files:**
- Modify: `backend/app/core/settings.py`
- Modify: `backend/app/domains/assessment/coordinator.py`
- Modify: `backend/app/domains/assessment/provider.py`
- Modify: `.env.dist`
- Test: `backend/tests/test_assessment_coordinator.py`

**Interfaces:**
- Consumes: `ObservationInput` (уже существует в `engine.py`, есть `observed_on: date`).
- Produces: `AsOfConfig` — потребляется только `RecomputeCoordinator`, не публичный API для других доменов.

- [ ] **Step 1: Добавить `AsOfMode` и поля в `AssessmentSettings`**

В `backend/app/core/settings.py` добавь импорт `StrEnum` и `date`:

```python
from datetime import date
from enum import StrEnum
from functools import lru_cache
```

Перед классом `AssessmentSettings` добавь:

```python
class AsOfMode(StrEnum):
    """Режим определения опорной даты расчёта отклонений (LCT-14).

    today — обычное поведение, date.today(). last_observation — дата
    последнего наблюдения НА КОНКРЕТНОЙ площадке (как в ML-отчёте:
    as_of = states[-1]["date"], ml/tools/match_schedule.py) — нужно для
    демо на площадках из разных лет, где одна общая дата не годится.
    fixed — одна дата на всё окружение (as_of_override).
    """

    TODAY = "today"
    LAST_OBSERVATION = "last_observation"
    FIXED = "fixed"
```

Замени класс `AssessmentSettings` на:

```python
class AssessmentSettings(BaseModel):
    """Пороги для расчёта статусов этапов и отклонений."""

    tolerance_days: int = 3
    stale_data_days: int = 7
    no_progress_window_days: int = 5
    min_confirming_observations: int = 2
    # Режим опорной даты расчёта (LCT-14) — см. AsOfMode.
    as_of_mode: AsOfMode = AsOfMode.TODAY
    # Используется только при as_of_mode == "fixed".
    as_of_override: date | None = None
```

- [ ] **Step 2: Добавить `AsOfConfig` и `_resolve_as_of` в `RecomputeCoordinator`**

В `backend/app/domains/assessment/coordinator.py`:

1. Добавь импорт `Sequence` и `AsOfMode`:

```python
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Protocol, cast

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.settings import AsOfMode
from app.domains.assessment.engine import (
```
(остальные импорты из `app.domains.assessment.engine` и далее — без изменений, просто добавляется `from collections.abc import Sequence`, `from dataclasses import dataclass` и `from app.core.settings import AsOfMode` к уже существующим импортам в начале файла.)

2. Сразу после класса `Clock` (перед `class RecomputeCoordinator`) добавь:

```python
@dataclass(frozen=True)
class AsOfConfig:
    """Настройка режима опорной даты расчёта (LCT-14). См. AsOfMode."""

    mode: AsOfMode
    fixed_date: date | None
```

3. В `RecomputeCoordinator.__init__` добавь новый параметр с дефолтом `None` в конец списка параметров (после `today: Clock = date.today,`):

```python
        today: Clock = date.today,
        as_of_config: AsOfConfig | None = None,
    ) -> None:
```

В теле `__init__`, после `self._today = today`, добавь:

```python
        self._as_of_config = as_of_config or AsOfConfig(mode=AsOfMode.TODAY, fixed_date=None)
```

Добавь `as_of_config` в docstring `__init__` рядом с `today`:
```
            as_of_config: AsOfConfig — режим опорной даты (default: today, как раньше).
```

4. Добавь новый метод `_resolve_as_of` сразу после `__init__` (перед `recompute_site`):

```python
    def _resolve_as_of(self, observations: Sequence[ObservationInput]) -> date:
        """Определить опорную дату расчёта для площадки (LCT-14).

        last_observation — дата последнего наблюдения НА ЭТОЙ площадке
        (как в ML-отчёте: as_of = states[-1]["date"]). Нужно для демо на
        площадках из разных лет — общая на всё окружение дата не подходит,
        а "последнее наблюдение" у каждой площадки согласовано с её же
        данными. Площадка без наблюдений — fallback на self._today()
        (мерить нечего). fixed без настроенной даты — тоже fallback на
        self._today() (тихо, не ошибка).
        """
        if self._as_of_config.mode == AsOfMode.LAST_OBSERVATION:
            if observations:
                return max(o.observed_on for o in observations)
            return self._today()

        if self._as_of_config.mode == AsOfMode.FIXED:
            if self._as_of_config.fixed_date is not None:
                return self._as_of_config.fixed_date
            return self._today()

        return self._today()
```

5. В `recompute_site`, замени:

```python
            # Шаг 5: Запустить engine
            computation = self._engine.compute_site(
                stages, rules_by_stage, observations, self._today()
            )
```

на:

```python
            # Шаг 5: Запустить engine
            reference_date = self._resolve_as_of(observations)
            computation = self._engine.compute_site(
                stages, rules_by_stage, observations, reference_date
            )
```

- [ ] **Step 3: Провайдер `AsOfConfig`**

В `backend/app/domains/assessment/provider.py`:

1. Замени импорт `from app.domains.assessment.coordinator import Clock, RecomputeCoordinator` на:

```python
from app.domains.assessment.coordinator import AsOfConfig, Clock, RecomputeCoordinator
```

2. Сразу после метода `clock` (внутри класса `AssessmentProvider`) добавь:

```python
    @provide(scope=Scope.APP)
    def as_of_config(self, settings: Settings) -> AsOfConfig:
        """Режим опорной даты расчёта (LCT-14) — из настроек."""
        return AsOfConfig(
            mode=settings.assessment.as_of_mode,
            fixed_date=settings.assessment.as_of_override,
        )
```

(`Settings` уже импортирован в этом файле для `engine_config`.)

- [ ] **Step 4: Написать тесты**

В `backend/tests/test_assessment_coordinator.py`:

1. Добавь импорт `AsOfConfig` и `AsOfMode`:
```python
from app.core.settings import AsOfMode
from app.domains.assessment.coordinator import AsOfConfig, RecomputeCoordinator
```
(строка с `RecomputeCoordinator` уже есть — просто добавь `AsOfConfig` в тот же импорт.)

2. Добавь параметр `as_of_config: AsOfConfig | None = None` в функцию `create_coordinator` и прокинь его в конструктор:

```python
async def create_coordinator(
    container: object, engine_config: EngineConfig, as_of_config: AsOfConfig | None = None
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
            session=session,
            as_of_config=as_of_config,
        )
        return coordinator
```

(это заменяет существующую функцию `create_coordinator` — единственные изменения: новый параметр в сигнатуре и передача `as_of_config=as_of_config` в конструктор; все остальные строки идентичны.)

3. Найди класс `TestRecomputeCoordinator` и посмотри, как существующие тесты заводят площадку с наблюдениями (график, этапы, наблюдения через `Observation`/`ObservedEquipment` из `app.domains.observation.models`, methodology через `MethodologyRule`/`EquipmentSet`/`EquipmentRequirement`/`EquipmentType`/`Obligation` из `app.domains.methodology.models` — см. импорты вверху файла). Используй тот же паттерн сидирования, что и в соседних тестах этого класса, чтобы завести площадку с graph/methodology/observations на разные даты (например: одно наблюдение с `observed_on=date(2023, 6, 1)`).

Добавь в `TestRecomputeCoordinator` новый вложенный класс с тестами (после существующих тестов класса, соблюдая отступы класса):

```python
class TestRecomputeCoordinatorAsOfMode:
    """Тесты режима опорной даты (LCT-14)."""

    async def test_last_observation_mode_uses_site_own_last_date(self, container):
        """last_observation берёт дату последнего наблюдения НА ЭТОЙ площадке,
        а не реальное "сегодня"."""
        # Реализуй сидирование площадки с графиком/методикой (маркерная
        # техника этапа) и двумя наблюдениями с этой техникой: более ранним
        # и более поздним, оба задолго до реального "сегодня" (например,
        # 2023 год) — если бы опорной датой было date.today(), stale_data
        # сработал бы. При as_of_config=AsOfConfig(mode=AsOfMode.LAST_OBSERVATION, fixed_date=None)
        # опорная дата должна оказаться датой ПОСЛЕДНЕГО из этих наблюдений,
        # и stale_data НЕ должен сработать (данные не "устарели" относительно
        # собственной опорной даты площадки).
        ...

    async def test_last_observation_mode_falls_back_to_today_without_observations(self, container):
        """Площадка без наблюдений в режиме last_observation — fallback на
        обычное поведение (self._today()), без падения."""
        ...

    async def test_default_mode_is_today_unchanged(self, container):
        """Без as_of_config (или явно AsOfMode.TODAY) — поведение как раньше,
        date.today(), регресс не допускается."""
        ...
```

Заполни тела этих трёх тестов реальным кодом (сидирование через `container`, вызов `await coordinator.recompute_site(site_id)`, затем чтение `StageStatusRepository`/`DeviationRepository` через `container` — по образцу существующих тестов `TestRecomputeCoordinator` в этом же файле), а не оставляй `...`. Ориентируйся на структуру уже существующих тестов этого класса — они показывают точный паттерн сидирования и проверки.

- [ ] **Step 5: Прогнать тесты**

Run: `cd backend && uv run pytest tests/test_assessment_coordinator.py -v`
Expected: PASS — все тесты, включая новые 3, зелёные.

Run: `cd backend && uv run pytest -q`
Expected: PASS — весь набор зелёный, включая `test_ml_parity.py` (не тронут, но зависит от `coordinator.py`).

Run: `cd backend && uv run mypy app/core/settings.py app/domains/assessment/coordinator.py app/domains/assessment/provider.py`
Expected: без новых ошибок.

Run: `cd backend && uv run ruff check . && uv run ruff format --check .`
Expected: без ошибок.

- [ ] **Step 6: Задокументировать переменные окружения**

В `.env.dist`, в логичном месте рядом с другими рантайм-настройками, добавь:

```
# Опорная дата расчёта отклонений (RecomputeCoordinator, LCT-14).
# today (по умолчанию) — date.today(). last_observation — своя дата для
# каждой площадки (последнее наблюдение на ней) — нужно для демо на
# площадках из разных лет. fixed — одна дата на всё окружение из
# ASSESSMENT__AS_OF_OVERRIDE ниже.
# ASSESSMENT__AS_OF_MODE=last_observation
# Используется только при ASSESSMENT__AS_OF_MODE=fixed. Формат: YYYY-MM-DD
# ASSESSMENT__AS_OF_OVERRIDE=2024-03-15
```

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/settings.py backend/app/domains/assessment/coordinator.py backend/app/domains/assessment/provider.py backend/tests/test_assessment_coordinator.py .env.dist
git commit -m "feat(assessment): per-site as-of date via last_observation mode (LCT-14)

A single environment-wide as-of override can't work for a demo whose
sites span 2023-2026: any one fixed date leaves some sites stale and
others still in the future. ML's own report already solves this per
site (as_of = states[-1][\"date\"], the site's own last observation
date) and the parity test in #20 checks against exactly that value.

ASSESSMENT__AS_OF_MODE=last_observation makes RecomputeCoordinator
resolve each site's reference date from its own last observation
instead of a global date.today(); unset (today, the default) keeps
existing behavior unchanged. A fixed third mode is also available for
a single environment-wide date if ever needed."
```
