# Spec: LCT-12 — ML integration via the adapter (phases 1–2)

Source plan: `docs/superpowers/plans/2026-09-25-ml-integration.md` (branch
`claude/funny-hopper-cw4i4l`). Phase 3 (date stamp) is split out to LCT-13 and is
**out of scope** here.

Decisions: Q1 — `*_unknown` go into the equipment catalog with `is_coarse=true`;
Q2 — two-stage confidence (service cuts at 0.25, backend keeps its own thresholds);
Q3 — `class_raw` is not stored.

Code comments and docstrings follow the surrounding code (Russian). Keep style
consistent with neighbours. Run `make check` (ruff) and `uv run pytest` in `backend/`.

---

## A. ML service (`ml/service`) — contract `detect/v1`

### `service/detector.py`
- `Detector.__post_init__`: compute `weights_sha256` (hex sha256 of the weights file,
  streamed in chunks) and store it. Property `model_id` = `f"{Path(weights).stem}@{sha256[:12]}"`.
- `class_names` property: `[names[i] for i in sorted(names)]` from `self.model.names`
  (dict id → name), i.e. list ordered by class id.
- `predict_bytes`: `Image.open(...)`, then `ImageOps.exif_transpose(img)`, then `.convert("RGB")`.
  `width/height` in the result are therefore post-EXIF.
- `_predict` result dict additionally contains `"model": self.model_id`.
  Detections sorted by `conf` descending.
- `meta()` returns existing keys plus `weights_sha256`, `model`, `contract: "detect/v1"`,
  `class_names`. Keep a module constant `CONTRACT = "detect/v1"`.
- The sha/weights-exists check must be testable: tests construct a `Detector` pointing at a
  temp file with fake bytes and monkeypatch `_model` with a fake object exposing `names`
  and `predict(...)`.

### `service/app.py`
- `FrameResult` gains `model: str`.
- Nothing else changes in `/health`, `/report`.

### Tests `ml/tests/test_service.py` (new; add `ml/tests/__init__.py` if needed, and a
`ml/pytest.ini` or `conftest.py` so `from service...` imports work with `cd ml && python -m pytest tests`)
- Use `fastapi.testclient.TestClient` with the module-global `_detector` replaced by a
  fake detector (skip the lifespan: set `service.app._detector` directly and don't use the
  context manager, or patch `Detector` so lifespan builds the fake).
- Cases: `/detect` returns `model`, `width`, `height`, `detections`; empty file → 400;
  over `MAX_BYTES` → 413; predict raising → 422; `_detector=None` → 503;
  `/meta` contains `contract == "detect/v1"`, `class_names`, `model`, `weights_sha256`.
- Unit test for `Detector` with a fake model: `model_id` format `stem@<12 hex>`, EXIF
  orientation 6 image (build with PIL, set EXIF 0x0112=6) yields swapped width/height.
- Tests must not need ultralytics/torch/weights. If fastapi/pillow are missing locally,
  install them into a venv for running; do not add heavy deps.

---

## B. Backend adapter (`backend/app/adapters/ml`)

### `base.py`
```python
class DetectorError(Exception):
    def __init__(self, message: str, *, transient: bool = False) -> None: ...
    transient: bool   # True → worth retrying later (503, timeout, connect, 5xx)

@dataclass(frozen=True)
class RawDetection: class_ours: str; conf: float; bbox: tuple[float, float, float, float]

@dataclass(frozen=True)
class DetectionResult:
    model_version: str
    detections: list[RawDetection]
    width: int | None = None
    height: int | None = None

@dataclass(frozen=True)
class DetectorInfo:
    model_version: str
    class_names: tuple[str, ...]
    conf_threshold: float | None
    device: str | None
    contract: str | None

class DetectorClient(Protocol):
    async def detect(self, image: bytes, filename: str, content_type: str | None = None) -> DetectionResult | None: ...
    async def info(self) -> DetectorInfo | None: ...   # None: disabled or unreachable
    async def ready(self) -> bool: ...                  # False: disabled/unreachable/model not loaded
```
Export `DetectorInfo` from `__init__.py`.

### `null.py`
`NullDetector.info()` → `None`, `ready()` → `False`.

### Settings (`app/core/settings.py`, `DetectorSettings`)
```
url: str | None = None          # BASE url, e.g. http://ml:8000
timeout_s: float = 30.0         # read timeout
connect_timeout_s: float = 2.0
max_concurrency: int = 2
retry_503: int = 3              # attempts after the first on HTTP 503
retry_other: int = 1            # attempts after the first on timeout/connect/other 5xx
retry_backoff_s: tuple[float, ...] = (2.0, 5.0, 10.0)
retry_budget_s: float = 20.0    # total sleep budget per detect() call
```

### `http.py` — `HttpDetectorClient`
Constructor: `HttpDetectorClient(base_url: str, client: httpx.AsyncClient, settings: DetectorSettings, sleep=asyncio.sleep)`.
- `normalize_base_url(url)` (module function): strip whitespace and trailing `/`; if it
  ends with `/detect`, cut it and `logger.warning(...)`. 
- `detect`: `POST {base}/detect` multipart `file=(filename, image, content_type)`, guarded by
  an `asyncio.Semaphore(max_concurrency)`, timeout `httpx.Timeout(timeout_s, connect=connect_timeout_s)`.
  Retry loop:
  - 200 → parse; schema mismatch/invalid JSON → `DetectorError(transient=False)`, no retry, `logger.error`.
  - 400/413/422 (any other 4xx) → `DetectorError(transient=False)`, no retry.
  - 503 → retry up to `retry_503` times; other 5xx, `httpx.TimeoutException`,
    `httpx.TransportError` (connect etc.) → retry up to `retry_other` times.
    Sleep `retry_backoff_s[min(i, len-1)]` before retry i; if cumulative sleep would exceed
    `retry_budget_s`, stop retrying. Exhausted → `DetectorError(transient=True)`.
  - Sleep via injected `sleep` callable (tests pass a recorder, no real waiting).
- Response schema (pydantic, `extra="ignore"`): `model: str | None = None`,
  `width: int | None`, `height: int | None`, `detections: list[{class_ours, conf, bbox}]`
  (keep current validators: conf in [0,1], bbox 4 values, in [0,1] ±1e-6, x2>x1, y2>y1).
  `class_raw`, `image`, `speed_ms` ignored.
- Model version: `model` from the response; if missing/blank → `await self.info()` and use
  `info.model_version`; if that is None → `DetectorError(transient=True)`.
- Clamp bbox to [0,1], round bbox to 4 and conf to 3 digits (as now).
- One log line per frame at INFO: filename, model, detections count, `speed_ms.total` if present.
- `info()`: `GET {base}/meta`, cached in the instance after first success; on any error
  → reset cache, log warning, return `None`. `model_version` = `meta["model"]` or, if absent,
  `meta["weights"]`; `class_names` = tuple(`meta.get("class_names", [])`);
  `conf_threshold` = `meta.get("conf")`; `device`; `contract`.
  If `contract` is present and its major part (`detect/v1` → `detect`, `v1`) differs from
  `detect/v1` → `logger.error` (still return info).
- `ready()`: `GET {base}/health`, returns `bool(json["model_loaded"])`; any error → False.

### `factory.py`
`create_detector(settings, client: httpx.AsyncClient | None) -> DetectorClient`:
NullDetector if url blank or client is None, else `HttpDetectorClient(normalize_base_url(url), client, settings.detector)`.

### DI (`app/domains/photo/provider.py`)
- New APP-scope provider yielding a shared `httpx.AsyncClient` for the detector
  (define a `NewType`, e.g. `DetectorHttpClient = NewType("DetectorHttpClient", httpx.AsyncClient)`
  in `app/adapters/ml/http.py`), closed on container shutdown (`AsyncIterable` + `aclose`).
  Always create it (closing an unused client is cheap).
- `detector(settings, client)` → `create_detector(settings, client)`.
- Tests: `tests/conftest.py` overrides `DetectorClient` already — keep that working.

### Tests `backend/tests/test_ml_adapter.py` (rewrite fixtures to the REAL format)
Use `httpx.MockTransport`. Real response fixture (from `ml/service` `FrameResult`):
```json
{"model": "mocs_m_best@3f1c9a0b7e21", "image": "Screenshot_26.png", "width": 1219, "height": 809,
 "speed_ms": {"preprocess": 3.1, "inference": 41.2, "postprocess": 1.4, "total": 64.7},
 "detections": [{"class_raw": "drilling_rig", "class_ours": "drilling_rig", "conf": 0.88, "bbox": [0.5396, 0.0, 0.6227, 0.6529]},
                {"class_raw": "crane_unknown", "class_ours": "crane_unknown", "conf": 0.41, "bbox": [0.1, 0.1, 0.2, 0.5]}]}
```
Cases: parse real response incl. width/height and `*_unknown`; missing `model` → `/meta`
fallback (and `weights` fallback); URL normalization (`/detect` suffix, trailing slash);
503×N then 200 → success with recorded sleeps; 503 exhausted → `transient=True`; 422 → no retry,
`transient=False`; timeout → 1 retry then transient; budget caps retries; invalid schema →
permanent; semaphore limits concurrency (count in-flight in transport handler with
`max_concurrency=2`, run 5 concurrent detects); `info()` caching and reset on error;
`ready()` true/false/error; NullDetector info/ready; factory choices.

---

## C. Equipment catalog: coarse classes

- `EquipmentType.is_coarse: Mapped[bool]` (`default=False`, `server_default=false()`, not null).
- `EQUIPMENT_SEED` gains 5 entries with `"is_coarse": True`; existing entries get no key
  (treated as False). Titles: `excavator_unknown` «Экскаватор (тип не определён)»,
  `crane_unknown` «Кран (тип не определён)», `drilling_unknown` «Буровая техника (тип не определён)»,
  `truck_unknown` «Грузовик (тип не определён)», `loader_unknown` «Погрузчик (тип не определён)»;
  synonyms `[]`.
- Migration `backend/migrations/versions/0009_equipment_coarse.py` (down_revision = the id in
  `0008_assessment.py`): add column with server default false, insert the 5 rows (uuid4 ids,
  JSON synonyms `[]`, skip if code exists is not needed — fresh insert), downgrade deletes the 5
  codes and drops the column. Check with `uv run alembic upgrade --sql head` style used elsewhere
  if feasible.
- `EquipmentTypeInfo.is_coarse: bool = False` populated by the catalog; methodology equipment
  read schema (whatever exposes equipment types via API) gains `is_coarse: bool`.
- Methodology rule/requirement creation must reject coarse equipment codes with the domain's
  existing validation error style (422), because rules never reference coarse classes.
  Default rules (`defaults.py`) must not reference them (add a test).
- Whatever seeds the test DB from `EQUIPMENT_SEED` must pass `is_coarse` through.

---

## D. Photo domain

- `_run_detection` / `redetect`: after a successful result, if `result.width`/`height` are not
  None and differ from `photo.width/height` → `logger.warning` (no status change).
- `DetectorError` in upload: log with `transient` flag; status `failed` as now.
- Extract a shared `_apply_result(photo, result, replace: bool)` to remove duplication
  between `_run_detection` and `redetect` (same-version keep vs replace semantics preserved).
- New `PhotoService.detect_backlog(site_id, statuses: set[ProcessingStatus]) -> DetectBacklogReport`:
  - guard; if `detector.configured` is False → `AppError(409, "Детектор не настроен")`.
  - iterate site photos with `processing_status in statuses` (repository method
    `list_by_status(site_id, statuses)` ordered by `created_at`/id), load bytes from storage
    (StorageError → count as failed, continue), `detect`; `DetectorError` → mark failed, count
    failed; success → apply (replace semantics) and mark done; commit per photo.
  - After loop: recompute observations once per distinct `captured_on` (sorted), same error
    handling as `upload_batch`.
  - Returns `{processed, done, failed, skipped}`. After the first `transient=True` error, stop
    calling the detector and count the remaining photos as `skipped` (ML is down; don't spend
    N×retry budget). `processed = done + failed`.
- Router: `POST /sites/{site_id}/photos/detect?status=pending,failed` (comma-separated, default
  both; invalid value → 422). Response schema `DetectBacklogReport` in `schemas.py`.
  Register the route **before** `/{photo_id}` routes if path conflicts arise (it's POST
  `/detect` vs POST `/{photo_id}/detect` — no conflict, but verify).
- Tests in `tests/test_photo_service.py` / `test_photo_router.py` with fake detectors from
  `tests/fakes.py` (extend fakes with `info`/`ready` and a scripted detector).

---

## E. Observability and startup check (`utility` domain + `main.py`)

- `ReadyResponse`: `database: bool`, `detector: DetectorStatus` where
  `DetectorStatus = {configured: bool, ready: bool, model: str | None}`. HTTP 200/503 still
  depends on the DB only. `configured` = detector is not `NullDetector` (add
  `configured: bool` attribute/property to both detector classes and to the Protocol).
- `VersionResponse`: `version: str`, `model: str | None` (from `info()`, None if unavailable).
- `HealthService` receives `DetectorClient`.
- Startup (in `main.py` lifespan, after the stand user seed): `check_detector_classes(detector, catalog)`
  in a new module `app/domains/photo/startup.py`: `info()`; None → `logger.info("ML недоступен…")`;
  else compare `set(info.class_names)` with catalog codes: log one warning listing
  unknown-to-catalog and (non-coarse) catalog codes missing from the model. Must never raise and
  must not block startup longer than one `/meta` call (wrap in `asyncio.wait_for(..., 5)`).
- Tests: `test_utility_router.py` (ready with Null and fake configured detector; version model),
  `tests/test_photo_startup.py`.

---

## F. Deployment

- `deploy/docker/common/core.yaml`: service `ml` —
  `image: ${REGISTRY}/ml:${ML_TAG:-latest}`, `build: ./ml`, `environment: {WEIGHTS: /weights/mocs_m_best.pt, MAX_UPLOAD_BYTES: 20971520}`,
  `volumes: [ml_weights:/weights:ro]`, `networks: [web]`, `restart: always`, no traefik labels.
  `backend.depends_on.ml: {condition: service_started, required: false}`.
  Top-level `volumes: {ml_weights: {}}` (check where other named volumes are declared and follow that).
- `deploy/docker/prod/core.yaml`: `ml: mem_limit: 1536m`.
- `deploy/docker/dev/core.yaml`: `ml: profiles: [ml]` (so `make dev` doesn't pull it by default).
- `makefile`: `ml-weights` target — run the ml image with the volume mounted **rw** at
  `/weights` (the service mount is ro) and `HF_TOKEN` passed:
  `$(COMPOSE) run --rm --no-deps -e HF_TOKEN -v <project>_ml_weights:/weights ml python tools/fetch_weights.py --out /weights`
  — inspect `ml/tools/fetch_weights.py` for real CLI args and adapt. Also `make dev-ml`
  (dev with `--profile ml`).
- `.env.dist`: block with `DETECTOR__URL=http://ml:8000` (comment: empty → NullDetector, frames stay pending),
  `DETECTOR__TIMEOUT_S`, `DETECTOR__MAX_CONCURRENCY`, `DETECTOR__RETRY_BUDGET_S` commented defaults,
  `# HF_TOKEN=` commented.
- `deploy/versions.env`: `ML_TAG=latest`.
- `.github/workflows/cd.yml`: add `ml` to the build matrix.
- `deploy/README.md`: section «ML-детектор»: weights, `make ml-weights`, profile in dev, memory,
  behaviour without ML, catch-up endpoint.
- Validate compose syntax with `docker compose ... config` if docker is available; otherwise
  with a YAML parser.

---

## G. Frontend

- `src/api/schemas.ts`: `detectBacklogReportSchema = z.object({processed, done, failed, skipped: z.number().int()})`.
- `src/api/frames.ts`: `framesApi.detectBacklog(siteId, statuses?)` → `POST /sites/{id}/photos/detect`
  with query `status` joined by comma; hook `useDetectBacklog(siteId)` via `useSiteMutation`.
- MSW handler in `src/mocks/handlers.ts` over `db.ts`: marks site photos with status
  pending/failed as done, returns counts.
- UI: on the observations screen, where non-`done` photos are shown (`NeedsReviewSection` or
  `PhotoStrip`), a button «Распознать необработанные» visible when any photo has status
  pending/failed; on success show a short result line («Обработано N: готово X, с ошибкой Y»);
  on 409 show «Детектор не настроен». Use existing UI kit components.
- Tests next to code; `pnpm check` must pass (tsc, eslint, stylelint, prettier, vitest thresholds).

---

## H. Parity test (backend vs ML `/report`)

- `ml/tools/export_parity_fixture.py`: builds `backend/tests/fixtures/ml_demo/` from
  `ml/data/processed/detections_mocs_m.json` + `ml/data/reference/sites.csv` +
  `schedule_demo.csv`, limited to sites present in `schedule_demo.csv` (p03, p05, …):
  `frames.json` (per-image: site, date, width, height, detections), `schedule_demo.csv`,
  `report.json` (= `service.pipeline.build_report(...)` output). Run it and commit the fixture.
- `backend/tests/test_ml_parity.py`: create sites, import schedule, insert photos with dates and
  detections through a scripted fake detector (or directly via repositories), run observation +
  assessment recalculation, map backend stage statuses to ML stage statuses and compare per
  (site, stage). Allowed differences are an explicit dict `{(site, stage_code): "reason"}`;
  any other mismatch fails the test, and an allowed difference that no longer differs also fails
  (keeps the list honest).

---

## Done criteria (tied to LCT-12)
- [ ] R1: adapter accepts real `/detect` response; missing `model` falls back to `/meta`.
- [ ] R2: `*_unknown` stored as detections of coarse equipment types.
- [ ] R3: model version `stem@sha12`.
- [ ] R4: adapter tests use the real response format.
- [ ] R5: one shared `AsyncClient` in `Scope.APP`, closed on shutdown.
- [ ] R6: 503 retried with backoff within budget; transient vs permanent errors.
- [ ] R7: `ml` in compose/CD, `DETECTOR__URL` in `.env.dist`, `make ml-weights`.
- [ ] R8: `exif_transpose` in ML, width/height mismatch warning in backend.
- [ ] `/api/ready` + `/api/version` detector block; class check at startup.
- [ ] Catch-up endpoint + frontend button.
- [ ] Parity test with explicit allowed differences.
- [ ] `make check`, backend pytest, ml pytest, `pnpm check` green.
