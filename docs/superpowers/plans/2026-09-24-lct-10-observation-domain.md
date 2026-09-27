# LCT-10 · Observation domain — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** New domain `observation` that folds `photo`/`detections` of one site into one row per day
(`observations` + `observed_equipment`): equipment count as "not less than" (max over frames, never
sum), observability level, and equipment activity. Recompute triggers automatically from `photo` on
upload and on manual date edit, idempotently (same `(site_id, observed_on)` never duplicates).

**Architecture:** Mirrors the existing `methodology → assessment` forward-reference pattern already in
this codebase (`app/domains/methodology/recalculator.py`: `StatusRecalculator` Protocol +
`NoopStatusRecalculator`, called by `MethodologyService`, real impl to be wired by the not-yet-built
`assessment` domain). Same shape here: `photo` defines `ObservationRecalculator` (Protocol) and calls it
after every batch upload / date edit; `photo`'s own provider binds it to a no-op by default so `photo`
never imports `observation`. `observation`'s provider binds the *real* implementation to the same
Protocol type and is registered **after** `PhotoProvider` in `create_container()` — confirmed by a local
dishka probe that a later-registered provider overrides an earlier one for the same interface type, even
across different scopes (APP → REQUEST override works).

**Tech Stack:** Python 3.12+, FastAPI, Dishka 1.10, SQLAlchemy 2.0 async, Alembic, PostgreSQL (prod) /
aiosqlite (tests), pytest + pytest-asyncio + httpx, uv, ruff.

**Spec:** the "Specification" section below. Task decomposition implements it.

## Global Constraints

- Backend layout: `docs/architecture.md` §6.1–§6.3, `.claude/rules/backend/architecture.md`. One domain
  = one flat directory in `app/domains/<domain>/`; only the six canonical files
  (`models.py/schemas.py/repository.py/service.py/router.py/provider.py`), omit what's unused.
- DI scopes: `Scope.APP` — settings, engine, sessionmaker, stateless parsers/policies, reference caches.
  `Scope.REQUEST` — session, repositories, services. `ObservationRepository`/`ObservedEquipmentRepository`/
  `ObservationService` are REQUEST. `AggregationPolicy`/`ObservabilityPolicy`/`ActivityPolicy` are APP
  (pure, stateless, constructor takes only config values — no DB, no session).
- Services own `AsyncSession` and call `commit()`; repositories only stage (`add`/`delete` + `flush()`).
- Every domain repository inherits `BaseRepository[Model]` (`app/core/repository.py`).
- Routers only build schemas from service results; access control goes through
  `SiteAccessGuard.require(site_id)` injected into the *service*, exactly like `photo`/`schedule`.
- `app/models.py` must import every domain's `models` module (Alembic autogenerate visibility) —
  **the tree must stay importable after every task**: `backend/tests/conftest.py` imports `app.main`,
  which transitively imports every domain, so no task may leave a dangling import.
- New migration file `backend/migrations/versions/0007_observation.py`, `down_revision = "0006"`,
  same style as `0006_photo.py` (raw `op.create_table` + explicit indexes/constraints, no ORM reflection).
- ruff: line-length 100, target py312. `uv run ruff check . && uv run ruff format --check .`
  (`make check` from repo root) must stay green after every task.
- Docstrings/comments in Russian, matching the surrounding domains (`photo`, `methodology`). Commit
  messages in English.
- `backend/uv.lock` is gitignored — never stage it.
- Business rules that MUST hold (`docs/architecture.md` §8, quoted in Specification below):
  count = max over frames, never sum; a frame without detections stays in the data; low observability
  must be a self-describing flag downstream consumers can key off; output must be deterministic
  (pure functions, no model-generated text, no randomness).

## Review Focus

Failure modes the spec implies that a happy-path test would not catch. Each assigned to the task that
owns the code.

1. **Sum instead of max.** Two photos of the same date each showing 2 excavators must give
   `count_min = 2`, not 4; five photos of the *same* excavator must give `count_min = 1`, not 5.
   → Task 3: `test_aggregation_policy_uses_max_not_sum`.
2. **Recompute creates a second row instead of updating.** Calling `ObservationService.recompute` twice
   for the same `(site_id, observed_on)` — including with a *different* photo set the second time — must
   update the existing `Observation.id`, never insert a second row (`UNIQUE(site_id, observed_on)` is the
   backstop, but the service must not rely on the DB to raise — it must `get_by_site_and_date` first).
   → Task 5: `test_recompute_is_idempotent_same_id`.
3. **Zero-photo recompute leaves a ghost row.** If every photo for a date is redated away, the next
   recompute for that now-empty date must delete the `Observation` row, not leave `photo_count=0` behind.
   → Task 5: `test_recompute_with_zero_photos_deletes_existing`.
4. **`photo` must stay import-clean of `observation`.** `app/domains/photo/*.py` may only import
   `app.domains.photo.recalculator.ObservationRecalculator` (the Protocol it owns) — never
   `app.domains.observation.*`. → Task 2 self-review; Task 6 reviewer re-checks with
   `grep -rn "domains.observation" app/domains/photo/`.
5. **Provider override direction.** `ObservationProvider` must be registered strictly after
   `PhotoProvider` in `create_container()` (`app/plugins/di.py`) and in `conftest.py`'s `container`
   fixture — reversed order silently resurrects the no-op and DoD item 3 (dozagruzka updates the
   observation) would silently no-op without any test failure elsewhere.
   → Task 6: `test_observation_di.py::test_create_container_resolves_live_recalculator`.
6. **A pending/failed photo must still count toward `photo_count`** (rule: "кадр без находок остаётся в
   данных") but must **not** contribute detections to aggregation (it has none, or unreliable ones).
   → Task 5: `test_recompute_counts_pending_photo_but_no_detections_from_it`.

---

## Specification

### Overview

`backend/app/domains/observation/` sums one site's `photos` + `detections` for one calendar date into
one `Observation` row + its `ObservedEquipment` rows. It is a derived cache: fully recomputable from
`photos`/`detections`, uniquely keyed by `(site_id, observed_on)`. It does not know about `schedule` or
`methodology`; it does not set stage statuses or create deviations (`docs/architecture.md` §6.7 boundary
model, LCT-10 issue body).

Business rules that bind this domain (`docs/architecture.md` §8):
1. Equipment count for a date is the **maximum across frames**, never the sum — reported as "not less
   than" (`count_min`).
2. A frame with zero detections is still data — it still counts toward `photo_count`.
3. A frame without a date is excluded upstream by `photo` (`?undated=true` never reaches `observation`).
4. Low observability must be a flag, not silently dropped — the *assessment* domain (LCT-11, not built
   yet) reads it to decide whether to abstain from a verdict.
10. Output must be a deterministic function of the inputs — no LLM text generation, no randomness.

### Cross-domain hook: `photo → observation`

`backend/app/domains/photo/recalculator.py` (**new file**):

```python
"""Protocol для реакции на изменения дат фотографий (пересчёт наблюдений)."""

import uuid
from datetime import date
from typing import Protocol


class ObservationRecalculator(Protocol):
    """Пересчитать наблюдение стройки за дату.

    Реальная реализация предоставляется доменом observation (LCT-10).
    """

    async def recompute(self, site_id: uuid.UUID, observed_on: date) -> None: ...


class NoopObservationRecalculator:
    """No-op реализация (заглушка, пока observation не подключён в конкретном контейнере)."""

    async def recompute(self, site_id: uuid.UUID, observed_on: date) -> None:
        pass
```

`PhotoService.__init__` gains `recalculator: ObservationRecalculator`. Call sites, both wrapped in
`try/except Exception: logger.exception(...)` so a recompute failure never fails the photo request (same
defensive shape as `_run_detection`'s error handling):

- `upload_batch`, after the neighbours-dating block and the final DB reload (i.e. once `final_items` is
  known): collect `{item.photo.captured_on for item in final_items if item.photo and item.photo.captured_on}`
  and call `recalculator.recompute(site_id, d)` for each distinct date.
- `set_date`, after `await self._session.commit()`: capture `old_date = photo.captured_on` **before**
  mutating it; after commit, call `recompute(site_id, new_date)`, and if `old_date is not None and
  old_date != new_date` also call `recompute(site_id, old_date)` (clears the stale observation on the
  date the photo left).

`PhotoProvider` (`backend/app/domains/photo/provider.py`) gains:
```python
@provide(scope=Scope.APP, provides=ObservationRecalculator)
def observation_recalculator(self) -> ObservationRecalculator:
    """Заглушка по умолчанию — реальная реализация приходит из ObservationProvider."""
    return NoopObservationRecalculator()
```

### Settings (`backend/app/core/settings.py`)

Add:
```python
class ObservationSettings(BaseModel):
    """Пороги для расчёта наблюдаемости, уверенности и активности."""

    min_photos_medium: int = 1
    min_photos_high: int = 3
    min_score_high: float = 0.7
    min_score_medium: float = 0.4
    movement_threshold: float = 0.05
```
and on `Settings`: `observation: ObservationSettings = ObservationSettings()`.

### Models (`backend/app/domains/observation/models.py`)

```python
"""ORM-модели наблюдений: сведённая за дату картина по стройке."""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Observability(StrEnum):
    """Наблюдаемость стройки за дату."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Activity(StrEnum):
    """Активность техники в наблюдении."""

    WORKS = "works"
    IDLE = "idle"
    UNKNOWN = "unknown"


class Confidence(StrEnum):
    """Уверенность вывода."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Observation(Base):
    """Картина по стройке за одну дату (таблица observations)."""

    __tablename__ = "observations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True
    )
    observed_on: Mapped[date] = mapped_column(Date(), nullable=False)
    photo_count: Mapped[int] = mapped_column(Integer, nullable=False)
    observability: Mapped[str] = mapped_column(String(16), nullable=False)
    observability_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recomputed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("site_id", "observed_on", name="uq_observations_site_date"),
    )


class ObservedEquipment(Base):
    """Техника, зафиксированная в наблюдении (таблица observed_equipment)."""

    __tablename__ = "observed_equipment"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    observation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("observations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    equipment_type_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("equipment_types.id"), nullable=False
    )
    count_min: Mapped[int] = mapped_column(Integer, nullable=False)
    activity: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "observation_id", "equipment_type_id", name="uq_observed_equipment_obs_type"
        ),
        CheckConstraint("count_min >= 1", name="ck_observed_equipment_count_min"),
    )
```

Register in `app/models.py`: `from app.domains.observation import models as observation_models  # noqa: F401`.

Migration `backend/migrations/versions/0007_observation.py`: `revision = "0007"`,
`down_revision = "0005"`... **no** — `down_revision = "0006"` (chains after photo). Mirror
`0006_photo.py`'s structure: `op.create_table("observations", ...)` with the columns above (use
`sa.Date()`, `sa.Integer()`, `sa.String(length=16)`, `sa.Text()`, `sa.DateTime(timezone=True)`), FK with
`ondelete="CASCADE"` to `sites.id`, `sa.UniqueConstraint("site_id", "observed_on", name=...)`; index on
`site_id`. Then `op.create_table("observed_equipment", ...)`, FK `ondelete="CASCADE"` to
`observations.id`, plain FK (no cascade) to `equipment_types.id`, `sa.UniqueConstraint("observation_id",
"equipment_type_id", name=...)`, `sa.CheckConstraint("count_min >= 1", name=...)`, index on
`observation_id`. `downgrade()` drops in reverse order (tables then their indexes, matching `0006`'s
symmetry).

### Policies (`backend/app/domains/observation/policies.py`) — pure, `Scope.APP`, no I/O

```python
"""Чистые функции сведения наблюдений: агрегация, наблюдаемость, активность."""

import math
import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from app.domains.observation.models import Activity, Confidence, Observability


@dataclass(frozen=True)
class FrameEquipment:
    """Одна детекция одного кадра, минимум для агрегации."""

    equipment_type_id: uuid.UUID
    score: float


@dataclass(frozen=True)
class AggregatedEquipment:
    """Результат агрегации по одному типу техники за дату."""

    count_min: int
    confidence: Confidence


class AggregationPolicy:
    """Максимум по кадрам (не сумма) + уверенность по score детекции и источнику даты."""

    def __init__(self, min_score_high: float, min_score_medium: float) -> None:
        self._min_score_high = min_score_high
        self._min_score_medium = min_score_medium

    def aggregate(
        self,
        frames: Sequence[Sequence[FrameEquipment]],
        date_sources: Sequence[str | None],
    ) -> dict[uuid.UUID, AggregatedEquipment]:
        """frames: одна Sequence[FrameEquipment] на кадр этой даты (детекции этого кадра).
        date_sources: date_source всех кадров этой даты (photo.date_source), для потолка confidence.

        count_min(type) = max(Counter(детекций этого типа на одном кадре)) по всем кадрам.
        confidence(type) = min(score_confidence, source_confidence):
          - score_confidence — по лучшему score этого типа среди кадров, давших максимум:
            >= min_score_high -> HIGH, >= min_score_medium -> MEDIUM, иначе LOW.
          - source_confidence — HIGH, если во всех date_sources нет "stamp"/"neighbours",
            иначе MEDIUM (штамп/соседи — источник хуже, см. architecture.md §7.3/§7.4).
        Тип техники без детекций ни на одном кадре в результат не попадает.
        """
        ...  # implementer fills in


class ObservabilityPolicy:
    """Наблюдаемость по числу кадров за дату (без камер/зон — MVP-упрощение)."""

    def __init__(self, min_photos_medium: int, min_photos_high: int) -> None:
        self._min_photos_medium = min_photos_medium
        self._min_photos_high = min_photos_high

    def assess(self, photo_count: int) -> tuple[Observability, str | None]:
        """>= min_photos_high -> (HIGH, None).
        >= min_photos_medium -> (MEDIUM, f"недостаточно кадров для высокой наблюдаемости: {photo_count}").
        иначе -> (LOW, f"мало кадров за дату: {photo_count}, вывод по объекту делать нельзя")."""
        ...


class ActivityPolicy:
    """Активность по сдвигу среднего центра bbox между соседними датами (без зон камер)."""

    def __init__(self, movement_threshold: float) -> None:
        self._movement_threshold = movement_threshold

    def assess(
        self,
        current_bboxes: Sequence[Sequence[float]],
        previous_bboxes: Sequence[Sequence[float]] | None,
    ) -> Activity:
        """bbox формат [x1, y1, x2, y2] в долях кадра (как в detections.bbox).
        Нет previous_bboxes (None или пусто) или current_bboxes пуст -> UNKNOWN.
        Иначе: center(bboxes) = среднее ((x1+x2)/2, (y1+y2)/2) по всем bbox в списке.
        euclidean(center(current), center(previous)) >= movement_threshold -> WORKS, иначе UNKNOWN.
        (Простой ("idle") на источнике "фото" не выводится вообще — см. architecture.md §7.6,
        таблица: "нет + зона не задана" -> простой только на видео/потоке, на фото "неизвестно".)
        """
        ...
```

### Repositories (`backend/app/domains/observation/repository.py`)

```python
class ObservationRepository(BaseRepository[Observation]):
    model = Observation

    async def get_by_site_and_date(self, site_id: uuid.UUID, observed_on: date) -> Observation | None: ...
    async def list_by_site(self, site_id: uuid.UUID) -> Sequence[Observation]:
        """Упорядочено по observed_on убыв., потом по id."""
    async def get_previous(self, site_id: uuid.UUID, before: date) -> Observation | None:
        """Наблюдение того же сайта с наибольшим observed_on < before, или None."""


class ObservedEquipmentRepository(BaseRepository[ObservedEquipment]):
    model = ObservedEquipment

    async def list_by_observation(self, observation_id: uuid.UUID) -> Sequence[ObservedEquipment]: ...
    async def replace_for_observation(
        self, observation_id: uuid.UUID, rows: Sequence[ObservedEquipment]
    ) -> None:
        """DELETE WHERE observation_id=... , затем add_all(rows) + flush. Идемпотентная замена."""
```

### Schemas (`backend/app/domains/observation/schemas.py`)

```python
class ObservedEquipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    equipment_type_id: uuid.UUID
    equipment_code: str
    equipment_title: str
    count_min: int
    activity: str
    confidence: str


class ObservationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    site_id: uuid.UUID
    observed_on: date
    photo_count: int
    observability: str
    observability_notes: str | None
    recomputed_at: datetime
    equipment: list[ObservedEquipmentRead]
```
(`ObservedEquipmentRead`/`ObservationRead` are hand-built in the service, like `PhotoService.get_photo`
builds `DetectionRead` — `equipment_code`/`equipment_title` are not ORM columns, they come from
`EquipmentCatalog`, so `model_validate` alone cannot produce them.)

### Service (`backend/app/domains/observation/service.py`)

```python
class ObservationService:
    def __init__(
        self,
        repository: ObservationRepository,
        equipment_repo: ObservedEquipmentRepository,
        photos: PhotoRepository,
        detections: DetectionRepository,
        session: AsyncSession,
        guard: SiteAccessGuard,
        catalog: EquipmentCatalog,
        aggregation: AggregationPolicy,
        observability: ObservabilityPolicy,
        activity: ActivityPolicy,
    ) -> None: ...
```

- `async def recompute(self, site_id: uuid.UUID, observed_on: date) -> Observation | None:`
  No `guard.require` here — called from `photo`'s already-access-checked context. Steps:
  1. `all_photos = await self.photos.list_by_site(site_id)`; `day_photos = [p for p in all_photos if
     p.captured_on == observed_on]`.
  2. If `not day_photos`: `existing = await self.repository.get_by_site_and_date(site_id, observed_on)`;
     if found, `await self.repository.delete(existing)`, `await self.session.commit()`; return `None`.
  3. `frames = []`; `date_sources = [p.date_source for p in day_photos]`; for each `p` in `day_photos`
     where `p.processing_status == "done"`: `dets = await self.detections.list_by_photo(p.id)`; append
     `[FrameEquipment(d.equipment_type_id, d.score) for d in dets]` to `frames` (photos not yet
     `"done"` still count in `len(day_photos)` for `photo_count` but contribute no frame to aggregation
     — Review Focus #6).
  4. `level, notes = self.observability.assess(len(day_photos))`.
  5. `aggregated = self.aggregation.aggregate(frames, date_sources)`.
  6. `previous_obs = await self.repository.get_previous(site_id, observed_on)`; if found, build
     `previous_bboxes: dict[uuid.UUID, list[list[float]]]` by re-reading that date's photos+detections
     the same way (steps 1/3) filtered to `previous_obs.observed_on` — **not** from
     `ObservedEquipment` rows, which don't store bboxes. If no previous observation, `previous_bboxes = {}`.
  7. Build `current_bboxes` the same shape from `frames`-equivalent detections of `day_photos` (bbox
     needs `Detection.bbox`, which `FrameEquipment` does not carry — extend the per-photo collection in
     step 3 to also keep raw `Detection` objects, or fetch bboxes in a second pass keyed by
     `equipment_type_id`; either is fine as long as `FrameEquipment` used for `aggregate()` stays exactly
     the two fields specified above).
  8. `observation = await self.repository.get_by_site_and_date(site_id, observed_on)`; if `None`,
     construct `Observation(site_id=site_id, observed_on=observed_on)` and `self.session.add(...)`; set
     `photo_count=len(day_photos)`, `observability=level.value`, `observability_notes=notes`; `await
     self.session.flush()` (assigns `id` on insert).
  9. For each `equipment_type_id, agg in aggregated.items()`: `act = self.activity.assess(
     current_bboxes.get(equipment_type_id, []), previous_bboxes.get(equipment_type_id))`; build
     `ObservedEquipment(observation_id=observation.id, equipment_type_id=..., count_min=agg.count_min,
     activity=act.value, confidence=agg.confidence.value)`.
  10. `await self.equipment_repo.replace_for_observation(observation.id, rows)`.
  11. `await self.session.commit()`; return `observation`.

- `async def list_observations(self, site_id: uuid.UUID) -> list[ObservationRead]:` `guard.require`;
  `repository.list_by_site`; for each, build `equipment` via `equipment_repo.list_by_observation` +
  `catalog.by_id` lookup (unknown type → `logger.warning`, skip — matches `PhotoService.get_photo`'s
  handling of unknown equipment).

- `async def get_observation(self, site_id: uuid.UUID, observed_on: date) -> ObservationRead:`
  `guard.require`; `get_by_site_and_date`; `None` → `AppError("Наблюдение не найдено", status_code=404)`.

### `LiveObservationRecalculator` (`backend/app/domains/observation/recalculator.py`)

```python
"""Реализация ObservationRecalculator для photo: настоящий пересчёт через ObservationService."""

import uuid
from datetime import date

from app.domains.observation.service import ObservationService


class LiveObservationRecalculator:
    """Оборачивает ObservationService.recompute под протокол photo.recalculator.ObservationRecalculator."""

    def __init__(self, service: ObservationService) -> None:
        self._service = service

    async def recompute(self, site_id: uuid.UUID, observed_on: date) -> None:
        await self._service.recompute(site_id, observed_on)
```

### Provider (`backend/app/domains/observation/provider.py`)

```python
class ObservationProvider(Provider):
    """DI-провайдер домена observation."""

    @provide(scope=Scope.APP)
    def aggregation_policy(self, settings: Settings) -> AggregationPolicy:
        return AggregationPolicy(
            min_score_high=settings.observation.min_score_high,
            min_score_medium=settings.observation.min_score_medium,
        )

    @provide(scope=Scope.APP)
    def observability_policy(self, settings: Settings) -> ObservabilityPolicy:
        return ObservabilityPolicy(
            min_photos_medium=settings.observation.min_photos_medium,
            min_photos_high=settings.observation.min_photos_high,
        )

    @provide(scope=Scope.APP)
    def activity_policy(self, settings: Settings) -> ActivityPolicy:
        return ActivityPolicy(movement_threshold=settings.observation.movement_threshold)

    observation_repository = provide(ObservationRepository, scope=Scope.REQUEST)
    observed_equipment_repository = provide(ObservedEquipmentRepository, scope=Scope.REQUEST)
    service = provide(ObservationService, scope=Scope.REQUEST)

    @provide(scope=Scope.REQUEST, provides=ObservationRecalculator)
    def observation_recalculator(self, service: ObservationService) -> ObservationRecalculator:
        """Перекрывает NoopObservationRecalculator из PhotoProvider (регистрация после него)."""
        return LiveObservationRecalculator(service)
```
(`ObservationRecalculator` imported from `app.domains.photo.recalculator` — this is the one place
`observation` importing from `photo` is correct: `observation` depends on `photo`, per the issue body's
own dependency line "Пререквизит: photo".)

### Router (`backend/app/domains/observation/router.py`)

```python
router = APIRouter(prefix="/sites/{site_id}/observations", tags=["observations"])

@router.get("")
async def list_observations(site_id: uuid.UUID, service: FromDishka[ObservationService]) -> list[ObservationRead]:
    return await service.list_observations(site_id)

@router.get("/{observed_on}")
async def get_observation(
    site_id: uuid.UUID, observed_on: date, service: FromDishka[ObservationService]
) -> ObservationRead:
    return await service.get_observation(site_id, observed_on)
```
Both `@inject`-decorated per the `photo`/`schedule` router convention.

### Wiring

- `app/plugins/di.py`: `create_container()` gains `PhotoProvider()` (already present) then
  `ObservationProvider()` immediately after it in the argument list — order matters (Review Focus #5).
- `app/plugins/routing.py`: `api_router.include_router(observation_router)`.
- `app/models.py`: import `observation.models`.
- `backend/tests/conftest.py`:
  - `TestPhotoProvider.photo_service(...)` gains `recalculator: ObservationRecalculator` param, passed
    through to `PhotoService(...)`.
  - `TestPhotoProvider` gains the same `@provide(scope=Scope.APP, provides=ObservationRecalculator) ->
    NoopObservationRecalculator()` default as the real `PhotoProvider`.
  - `container` fixture: add `ObservationProvider()` to `make_async_container(...)`'s argument list,
    positioned after `TestPhotoProvider(...)` (same override-order requirement as production).

### Error handling

- `get_observation` 404 via `AppError("Наблюдение не найдено", status_code=404)`.
- `list_observations`/`get_observation` 404 via `guard.require(site_id)` (existing `AppError` from
  `SiteAccessGuard`, unchanged).
- `recompute` never raises `AppError` to its caller in a way that should reach an HTTP response — it's
  invoked from `photo`'s recalculator hook, which already wraps the call in `try/except Exception:
  logger.exception(...)`. `recompute` itself does not need its own additional try/except — let the
  exception propagate to the wrapper.

### Testing

- `test_observation_model.py` — constraints: `UNIQUE(site_id, observed_on)`, `UNIQUE(observation_id,
  equipment_type_id)`, `count_min >= 1` (IntegrityError on violation, in-memory sqlite honors these).
- `test_observation_policies.py` — no DB, plain unit tests:
  - `AggregationPolicy`: 5 frames, same equipment_type on every frame → `count_min == 1` (Review Focus
    #1, verbatim DoD case); 2 frames each with 2 of the same type → `count_min == 2` not 4; different
    types on different frames → each gets its own max; `date_sources` containing `"stamp"` or
    `"neighbours"` caps confidence at `MEDIUM` even with high scores; type absent from all frames is
    absent from the result dict.
  - `ObservabilityPolicy`: table-test the boundary values around `min_photos_medium`/`min_photos_high`.
  - `ActivityPolicy`: `previous_bboxes=None` → `UNKNOWN`; shift ≥ threshold → `WORKS`; shift < threshold
    → `UNKNOWN`; `current_bboxes=[]` → `UNKNOWN`.
- `test_observation_repository.py` — `get_by_site_and_date`, `get_previous` (returns the closest earlier
  date, not just any earlier one, when several exist), `replace_for_observation` (second call with a
  disjoint set of rows leaves exactly the new set, old rows gone).
- `test_observation_service.py` — `recompute` idempotency (Review Focus #2): call twice with identical
  inputs, `Observation.id` unchanged, exactly one row in `list_by_site`; zero-photos deletes existing row
  (Review Focus #3); pending-photo counts toward `photo_count` but contributes no detections (Review
  Focus #6); low observability sets `observability == "low"` with non-null `observability_notes`.
- `test_observation_router.py` — 404 on foreign/missing site, 404 on missing date, happy-path list+detail
  shape (`equipment_code`/`equipment_title` populated, not raw UUIDs only).
- `test_observation_di.py` — mirrors `test_photo_di.py`: `create_container()` resolves
  `ObservationRepository`/`ObservedEquipmentRepository` (REQUEST, distinct instances per request);
  policies (APP, same instance reused across request contexts); **and**
  `test_create_container_resolves_live_recalculator`: `await container.get(ObservationRecalculator)`
  `isinstance(..., LiveObservationRecalculator)`, not `NoopObservationRecalculator` (Review Focus #5).
- Update `test_photo_service.py`/`test_photo_router.py`: one happy-path test each asserting that after
  `upload_batch` (resp. `set_date`), `container.get(ObservationRepository)` (now resolvable — `conftest`
  wires `ObservationProvider`) finds an `Observation` row for the right `(site_id, captured_on)`, proving
  the hook actually fires end-to-end, not just that `Noop` swallows the call silently.
- Update `test_photo_di.py`: `create_container()` still resolves `PhotoService` (no regression from the
  new constructor param); add a case resolving `ObservationRecalculator` directly on a container built
  with *only* `PhotoProvider()` (no `ObservationProvider()`) and asserting it's `NoopObservationRecalculator`
  — proves `photo` alone still degrades gracefully.

**Acceptance criteria (from the LCT-10 issue body, Definition of Done):**
- [ ] One machine shot from five points gives `count_min = 1`, not 5 (test, Task 3).
- [ ] Low observability marks the observation so a future `assessment` consumer must abstain from a
  verdict — `observability == "low"` is set correctly and is a stored, queryable field (test, Task 5).
- [ ] Re-uploading a photo for the same date updates the observation, not creates a second one (test,
  Task 5 + Task 6 end-to-end).

---

## Task 1 — Settings, ORM models, migration

- [ ] Add `ObservationSettings` to `backend/app/core/settings.py` exactly as specified (field names,
  defaults) and wire it as `Settings.observation`.
- [ ] Create `backend/app/domains/observation/__init__.py` (empty, matching other domains).
- [ ] Create `backend/app/domains/observation/models.py` exactly as specified: `Observability`,
  `Activity`, `Confidence` (`StrEnum`), `Observation`, `ObservedEquipment` ORM classes with the exact
  columns, FKs, `UniqueConstraint`s and `CheckConstraint` given above.
- [ ] Register `observation.models` in `backend/app/models.py` (`# noqa: F401` import, alongside the
  existing domain imports, alphabetically among them).
- [ ] Create `backend/migrations/versions/0007_observation.py`, `revision = "0007"`,
  `down_revision = "0006"`, mirroring `0006_photo.py`'s structure (see Specification for exact table
  shape). `upgrade()` creates both tables + indexes + constraints; `downgrade()` reverses in the mirror
  order.
- [ ] `backend/tests/test_observation_model.py`: constraint tests listed under Testing above (in-memory
  sqlite via the existing `conftest.py` `engine`/`container` fixtures — no new fixtures needed for this
  task, `Base.metadata.create_all` already covers a newly-imported model module).
- [ ] Verify: `uv run pytest tests/test_observation_model.py -v`, `uv run ruff check .`, `uv run ruff
  format --check .`, and `uv run pytest` (full suite still green — this task only *adds* files/columns,
  it must not break anything already passing).
- [ ] Self-review, commit.

## Task 2 — `photo → observation` recalculator hook

- [ ] Create `backend/app/domains/photo/recalculator.py` exactly as specified: `ObservationRecalculator`
  Protocol, `NoopObservationRecalculator`.
- [ ] `PhotoService.__init__` (`backend/app/domains/photo/service.py`) gains `recalculator:
  ObservationRecalculator` parameter, stored as `self._recalculator`.
- [ ] Wire the two call sites exactly as specified in "Cross-domain hook: `photo → observation`" above
  (`upload_batch` after final reload; `set_date` after commit, old+new date when they differ), each
  wrapped in `try/except Exception: logger.exception(...)`.
- [ ] `PhotoProvider` (`backend/app/domains/photo/provider.py`) gains the
  `provide(scope=Scope.APP, provides=ObservationRecalculator) -> NoopObservationRecalculator()` binding
  and passes `recalculator` through to `PhotoService(...)` in its `photo_service` factory.
- [ ] Update `backend/tests/conftest.py`'s `TestPhotoProvider`: add the same
  `ObservationRecalculator`-providing method (returning `NoopObservationRecalculator()` for this task —
  Task 6 will add real `ObservationProvider` wiring to the `container` fixture, this task only needs
  `TestPhotoProvider` to keep constructing a valid `PhotoService`), and pass `recalculator` through in
  `photo_service(...)`.
- [ ] Update any existing photo tests that construct `PhotoService` directly (grep
  `tests/test_photo_service.py` and any other direct constructors) to supply a
  `NoopObservationRecalculator()` — do **not** change test behavior/assertions beyond the constructor
  signature.
- [ ] `grep -rn "domains.observation" backend/app/domains/photo/` must return nothing (Review Focus #4).
- [ ] Verify: `uv run pytest tests/test_photo_service.py tests/test_photo_router.py tests/test_photo_di.py
  -v` and full `uv run pytest` — must stay green (the hook is a no-op end-to-end at this point, since
  `observation` doesn't exist as a package yet; this task proves `photo` alone still works).
- [ ] Self-review, commit.

## Task 3 — Policies

- [ ] Create `backend/app/domains/observation/policies.py` exactly as specified:
  `FrameEquipment`, `AggregatedEquipment` dataclasses; `AggregationPolicy`, `ObservabilityPolicy`,
  `ActivityPolicy` classes with the exact constructor signatures and `assess`/`aggregate` semantics
  described in the docstrings above.
- [ ] `backend/tests/test_observation_policies.py`: all cases listed under Testing above. No DB, no
  fixtures beyond plain instantiation — these are pure unit tests.
- [ ] Verify: `uv run pytest tests/test_observation_policies.py -v`, `uv run ruff check .`, full `uv run
  pytest` green.
- [ ] Self-review, commit.

## Task 4 — Repositories and schemas

- [ ] Create `backend/app/domains/observation/repository.py`: `ObservationRepository`,
  `ObservedEquipmentRepository` exactly as specified (method names, signatures, ordering rules).
- [ ] Create `backend/app/domains/observation/schemas.py`: `ObservedEquipmentRead`, `ObservationRead`
  exactly as specified.
- [ ] `backend/tests/test_observation_repository.py`: cases listed under Testing above, using the
  existing `container`/`engine` fixtures from `conftest.py` (no `ObservationProvider` needed yet — build
  repositories directly with a session, same pattern as `test_photo_repository.py`).
- [ ] Verify: `uv run pytest tests/test_observation_repository.py -v`, ruff, full suite green.
- [ ] Self-review, commit.

## Task 5 — Service

- [ ] Create `backend/app/domains/observation/service.py`: `ObservationService` exactly as specified
  (constructor params, `recompute`/`list_observations`/`get_observation` behavior, all 11 steps of
  `recompute` as described).
- [ ] `backend/tests/test_observation_service.py`: cases listed under Testing above (idempotency,
  zero-photo deletion, pending-photo counting, low observability). Construct `ObservationService`
  directly with real `PhotoRepository`/`DetectionRepository`/`SiteAccessGuard` from the existing test
  container plus hand-built `ObservationRepository`/`ObservedEquipmentRepository`/policy instances — no
  `ObservationProvider` or router wiring required for this task (that's Task 6). Seed photos/detections
  directly via the ORM in the test (same pattern `test_photo_service.py` likely already uses — check it
  first).
- [ ] Verify: `uv run pytest tests/test_observation_service.py -v`, ruff, full suite green.
- [ ] Self-review, commit.

## Task 6 — Provider, router, DI wiring, end-to-end tests

- [ ] Create `backend/app/domains/observation/recalculator.py`: `LiveObservationRecalculator` exactly as
  specified.
- [ ] Create `backend/app/domains/observation/provider.py`: `ObservationProvider` exactly as specified,
  including the `ObservationRecalculator` override binding.
- [ ] Create `backend/app/domains/observation/router.py`: `list_observations`/`get_observation` routes
  exactly as specified, `@inject`-decorated, mounted at `/sites/{site_id}/observations`.
- [ ] `backend/app/plugins/di.py`: register `ObservationProvider()` in `create_container()`, positioned
  immediately after `PhotoProvider()`.
- [ ] `backend/app/plugins/routing.py`: `api_router.include_router(observation_router)`.
- [ ] `backend/tests/conftest.py`: add `ObservationProvider()` to the `container` fixture's
  `make_async_container(...)` call, positioned after `TestPhotoProvider(...)` (same order requirement).
- [ ] `backend/tests/test_observation_di.py`: cases listed under Testing above, including
  `test_create_container_resolves_live_recalculator` (Review Focus #5) using the real
  `app.plugins.di.create_container()` — not the test container — since that's what proves production
  wiring is correct.
- [ ] `backend/tests/test_observation_router.py`: cases listed under Testing above.
- [ ] Update `backend/tests/test_photo_service.py` and `backend/tests/test_photo_di.py` with the two
  end-to-end cases described under Testing above (hook actually fires; `photo`-only container still
  degrades to `Noop`).
- [ ] Verify: full `uv run pytest -v` green, `uv run ruff check .`, `uv run ruff format --check .`.
- [ ] Self-review, commit.
