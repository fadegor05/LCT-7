# LCT-20: assistant backend — ML adapter and `assistant` endpoints — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `POST /api/sites/{site_id}/assistant/ask` and `GET /api/assistant/status`: the backend builds the report itself (LCT-19), calls the ML service `/ask` (LCT-18/19 guard included), and returns the answer with the number-check result untouched, plus links from "этап N" to stage ids.

**Architecture:** Adapter `app/adapters/ml/assistant.py` behind an `AssistantClient` Protocol (Http/Null, same style as the detector adapter, shared `httpx.AsyncClient`, **no retries**: every call is paid). Domain `app/domains/assistant/` gets `schemas.py`, `router.py` and an `AssistantService` that orchestrates: access guard → availability → rate limit → report → size cap → ML call → error mapping. Nothing is stored.

**Tech Stack:** Python 3.12, FastAPI, Dishka, httpx, pydantic v2, pytest (`httpx.MockTransport`, `ASGITransport`).

**Spec:** Linear LCT-20 (https://linear.app/kaiangel/issue/LCT-20/assistent-backend-adapter-ml-i-domen-assistant-ruchka-sprosit-po), parent LCT-17; `ml/docs/ASSISTANT.md`; LCT-19 plan `docs/superpowers/plans/2026-09-28-lct-19-assistant-report-and-scope-guard.md` (report shape, `stage_ids`, ML `422 out_of_scope`).

**Base:** branch from `origin/feat-ai-assist` (LCT-18 and LCT-19 are merged there). Push with an explicit branch name; never plain `git push` (no upstream is set on purpose).

## Decisions (where the plan differs from or extends the issue text)

- **No `401`.** The project has no authentication: `CurrentUser` always resolves to the stand user (`app/domains/user/provider.py`). "Без токена → 401" cannot be built here. Mitigations: ML is not published outside the compose network, rate limit, size cap, ML `max_tokens`. Real auth is a separate issue; the PR must say so.
- **`AppError` gets an optional `code`.** The global handler returns `{"detail": message}`; the frontend must tell `out_of_scope` from other 422s and `rate_limited` from other 4xx. Additive change: `{"detail": message, "code": code}` only when a code is set.
- **Response has `site_label` and `stages`.** `stages` = `[{"ref": "этап 3", "stage_id": <uuid>}]` for the stages actually mentioned in the answer (deterministic parse), so the UI links without a second model call.
- **Rate limit key = site owner id** (the stand user today, so effectively global). In-memory sliding window, per process. Default 10 requests / 60 s, configurable.
- **Order of checks** (cheap and non-consuming first): access guard (404) → availability (503, does not consume quota) → rate limit (429) → build report (404 no schedule) → size cap (413) → ML call.

## Global Constraints

- Code comments, docstrings, test names and user-facing strings in Russian, matching surrounding code. Ruff: line length 100, rules `E,F,I,UP,B`.
- The LLM key never appears in any response or log. The question, the answer text, the provider host and raw ML error text are never logged: log only `site_id`, question length, answer length, `verified`, duration in ms, status/code.
- No retries to ML on 503, 504, timeout, connect error (one HTTP call per user action).
- The ML answer fields `verified`, `numbers_not_in_report`, `numbers_of_other_site`, `limits` are passed through unchanged.
- Backend commands: `cd backend && uv run pytest -q`, `make check` from repo root.
- Do not read, edit or list any `.env` file except the root `.env.dist` (allowed by the user for documenting new variables).

## HTTP contract (LCT-21 / LCT-22 rely on it)

`POST /api/sites/{site_id}/assistant/ask`, body `{"question": str}`, 3..500 chars after strip → `200`:
```
{"answer": str, "verified": bool, "numbers_not_in_report": [str], "numbers_of_other_site": [str],
 "limits": str, "site_label": "p1", "stages": [{"ref": "этап 3", "stage_id": "<uuid>"}]}
```
`GET /api/assistant/status` → `{"enabled": bool}` (never spends a paid call).
Errors, body `{"detail": <message>, "code": <code>}` unless stated:

| status | code | when |
|---|---|---|
| 404 | – | foreign/missing site, no schedule (existing messages) |
| 422 | – | question length (FastAPI validation, `detail` is a list) |
| 422 | `out_of_scope` | ML refused: question or answer off-topic; `detail` = ML's `message` |
| 429 | `rate_limited` | limit exceeded; message says after how many seconds to retry |
| 413 | `report_too_large` | serialized report > `max_report_kb` |
| 503 | `assistant_unavailable` | not configured, ML down, ML 503, unexpected ML reply |
| 504 | `assistant_timeout` | ML 504 or read timeout: "Модель не ответила. Повторите вопрос позже." |
| 400 | `assistant_bad_request` | ML 400 or other 4xx |

## Review Focus

1. ML not configured / down: `status` → `enabled:false` without error; `ask` → 503 **and the report service is not called** (no DB work). (Tasks 4–5)
2. `verified:false` with both number lists reaches the client byte-for-byte. (Task 5)
3. ML `422 out_of_scope` → our 422 with `code:"out_of_scope"` and ML's message; distinguishable from validation 422. (Tasks 2, 5)
4. Secrets: ML replying `504` with `detail` containing `sk-SECRET` / a provider host → neither appears in our response or in captured logs. (Tasks 2, 5)
5. Exactly one HTTP call to ML on 503, 504, timeout (call counter). (Task 2)
6. Rate limit boundary: N allowed, N+1 → 429; window slides; keys independent. (Task 3)
7. Foreign site → 404 before any ML call and without consuming quota. (Task 4)
8. Question edges: `"  ab  "` → 422; 3 and 500 chars accepted; 501 → 422. (Task 5)
9. Stage links: "Этап 3" / "этапа 3" / "этап №3" resolve; "этап 99" (not in `stage_ids`) and duplicates are dropped. (Task 4)

---

### Task 1: Settings and `AppError.code`

**Files:**
- Modify: `backend/app/core/settings.py` (`AssistantSettings`, `Settings.assistant`)
- Modify: `backend/app/plugins/exceptions.py` (`AppError.code`, handler)
- Modify: `.env.dist` (root; comment block for `ASSISTANT__*`)
- Test: `backend/tests/test_assistant_settings.py` (create), `backend/tests/test_app_error_code.py` (create)

**Interfaces:**
- Produces:
  - `AssistantSettings(BaseModel)`: `timeout_s: float = 130.0`, `connect_timeout_s: float = 2.0`, `rate_limit_per_min: int = 10`, `max_report_kb: int = 512`, `status_cache_s: float = 30.0`, `status_retry_s: float = 5.0`; `Settings.assistant: AssistantSettings = AssistantSettings()`.
  - `AppError.__init__(self, message: str, status_code: int = 400, code: str | None = None)`; attribute `code`; the handler responds `{"detail": message}` plus `"code": code` only if `code` is not `None`.

- [ ] **Step 1: Write failing tests.** `test_assistant_settings`: defaults equal the values above; `ASSISTANT__RATE_LIMIT_PER_MIN=3` and `ASSISTANT__TIMEOUT_S=7` (monkeypatched env, fresh `Settings()`) override; `test_app_error_code`: a tiny FastAPI app with the registered handler and two routes raising `AppError("x", 429, code="rate_limited")` and `AppError("y", 404)` → bodies `{"detail":"x","code":"rate_limited"}` and `{"detail":"y"}` (no `code` key).
- [ ] **Step 2: Run to verify they fail.** `cd backend && uv run pytest tests/test_assistant_settings.py tests/test_app_error_code.py -q`.
- [ ] **Step 3: Implement** as specified; add to `.env.dist` a commented block: `# ASSISTANT__RATE_LIMIT_PER_MIN=10`, `# ASSISTANT__TIMEOUT_S=130`, `# ASSISTANT__MAX_REPORT_KB=512` with one Russian line of explanation each (no `.env` file may be read or written).
- [ ] **Step 4: Run** the two files plus the full suite; `make check`.
- [ ] **Step 5: Commit.**
  ```bash
  git add backend/app/core/settings.py backend/app/plugins/exceptions.py .env.dist backend/tests/test_assistant_settings.py backend/tests/test_app_error_code.py
  git commit -m "feat(backend): AssistantSettings и код в AppError (LCT-20)"
  ```

---

### Task 2: ML assistant adapter

**Files:**
- Create: `backend/app/adapters/ml/assistant.py`
- Modify: `backend/app/adapters/ml/factory.py` (`create_assistant`), `backend/app/adapters/ml/__init__.py` (exports, follow its existing style)
- Modify: `backend/tests/fakes.py` (`FakeAssistantClient`)
- Test: `backend/tests/test_ml_assistant_adapter.py` (create)

**Interfaces:**
- Consumes: `normalize_base_url` (`app.adapters.ml.http`), `AssistantSettings`, `Settings.detector.url`.
- Produces (module `assistant`):
  - `@dataclass(frozen=True) AssistantAnswer`: `answer: str`, `verified: bool`, `numbers_not_in_report: list[str]`, `numbers_of_other_site: list[str]`, `limits: str`.
  - `class AssistantError(Exception)`: `message: str`, `status_code: int`, `code: str`; subclasses `AssistantUnavailable` (503, `assistant_unavailable`), `AssistantTimeout` (504, `assistant_timeout`), `AssistantBadRequest` (default 400, `assistant_bad_request`; constructible with `status_code=422, code="out_of_scope"`).
  - `class AssistantClient(Protocol)`: `async def ask(self, question: str, report: dict, site_id: str | None = None) -> AssistantAnswer`, `async def available(self) -> bool`.
  - `HttpAssistantClient(base_url: str, client: httpx.AsyncClient, settings: AssistantSettings, clock=time.monotonic)`; `NullAssistantClient` (`available()` → `False`; `ask` raises `AssistantUnavailable("Ассистент не настроен")`).
  - `create_assistant(settings: Settings, client: httpx.AsyncClient | None) -> AssistantClient`: Http if `settings.detector.url` non-blank and `client` not None, else Null.
  - `FakeAssistantClient(answer: AssistantAnswer | None = None, error: AssistantError | None = None, enabled: bool = True)` in `tests/fakes.py`: records `calls: list[tuple[str, dict, str | None]]`.
  - Behaviour of `HttpAssistantClient.ask`: `POST {base}/ask`, json `{"question", "report", "site_id"}`, `httpx.Timeout(timeout_s, connect=connect_timeout_s)`, **one attempt**. `200` → parse into `AssistantAnswer` (pydantic model with `extra="ignore"`; missing/invalid fields → `AssistantUnavailable("Ассистент вернул неожиданный ответ")`). `503` and other `5xx` and `httpx.ConnectError/ConnectTimeout/TransportError` → `AssistantUnavailable("Ассистент временно недоступен")`; `504` and `httpx.ReadTimeout/TimeoutException` (not connect) → `AssistantTimeout("Модель не ответила. Повторите вопрос позже.")`; `422` whose JSON `detail` is an object with `code == "out_of_scope"` → `AssistantBadRequest(message=str(detail["message"])[:300], status_code=422, code="out_of_scope")`; any other `422`/`4xx` → `AssistantBadRequest("Ассистент не принял запрос")` with code `assistant_bad_request` (status 400). Raw ML text is never put into messages; log the ML status and `str(detail)[:200]` at warning only for 5xx/4xx non-scope cases (ML's `detail` is already sanitized, but it is still not shown to users).
  - `available()`: `GET {base}/meta` with the same timeouts; `True` iff HTTP 200 and JSON `assistant is True`; any exception/other status → `False`. Cached per `clock()`: True for `status_cache_s`, False for `status_retry_s`.

- [ ] **Step 1: Write failing tests** (`httpx.MockTransport`, a fake clock; a `call counter` on the transport):
  - `test_ask_успех`: 200 with the five fields → `AssistantAnswer` equal; request body has `question`, `report`, `site_id`; URL is `{base}/ask` (base given as `http://ml:8000/` normalises).
  - `test_verified_false_не_меняется`: 200 with `verified=false`, `numbers_not_in_report=["999"]`, `numbers_of_other_site=["p1: 5"]` → returned identically.
  - parametrized `test_ошибки_ml_маппятся`: ML 503 → `AssistantUnavailable`; 500 → `AssistantUnavailable`; 504 → `AssistantTimeout`; 400 → `AssistantBadRequest` (400, `assistant_bad_request`); 422 with detail list (validation) → `AssistantBadRequest` (400, `assistant_bad_request`); 422 with `{"detail": {"code": "out_of_scope", "message": "Только по отчёту"}}` → `AssistantBadRequest` with `status_code == 422`, `code == "out_of_scope"`, `message == "Только по отчёту"`.
  - `test_таймаут_чтения_504_а_коннект_503`: `httpx.ReadTimeout` → `AssistantTimeout`; `httpx.ConnectError` → `AssistantUnavailable`.
  - `test_ровно_один_вызов_при_ошибках`: for 503, 504 and `ReadTimeout` the transport counter is exactly 1.
  - `test_неверный_json_и_схема`: body `not json` and body `{"answer": 1}` → `AssistantUnavailable`.
  - `test_в_сообщениях_нет_секретов`: ML replies 504 with `{"detail": "языковая модель не ответила: sk-SECRET llm.secret.example"}` → `str(exc)`/`exc.message` contain neither string.
  - `test_available_true_false_и_кэш`: `/meta` → `{"assistant": true}` → True, second call within TTL does not hit the transport; after `status_cache_s` hits again; `{"assistant": false}` → False; connection error → False, and a retry after `status_retry_s` (< `status_cache_s`) hits the transport again.
  - `test_null_клиент`, `test_create_assistant_выбор`: blank/None `detector.url` or `client=None` → `NullAssistantClient`; otherwise `HttpAssistantClient`.
- [ ] **Step 2: Run to verify they fail** (module missing).
- [ ] **Step 3: Implement** the module, factory function, exports and `FakeAssistantClient`.
- [ ] **Step 4: Run** the new file, the whole suite, `make check`.
- [ ] **Step 5: Commit.**
  ```bash
  git add backend/app/adapters/ml backend/tests/fakes.py backend/tests/test_ml_assistant_adapter.py
  git commit -m "feat(backend): адаптер ассистента ML без ретраев, Null и Http клиенты (LCT-20)"
  ```

---

### Task 3: Rate limiter

**Files:**
- Create: `backend/app/core/rate_limit.py`
- Test: `backend/tests/test_rate_limit.py` (create)

**Interfaces:**
- Produces: `SlidingWindowRateLimiter(limit: int, window_s: float = 60.0, clock=time.monotonic)` with `def hit(self, key: str) -> float | None` — records a hit and returns `None` if allowed, else the number of seconds (float, > 0) until the oldest hit leaves the window (no hit is recorded on rejection). Old keys are pruned so memory stays bounded.

- [ ] **Step 1: Write failing tests** (fake clock): `limit=3`: three hits → `None`, fourth → a float in `(0, 60]`; after advancing by the returned value the next hit is allowed; sliding (hits at t=0,10,20 with window 60: at t=61 exactly one slot is free, not three); keys `"a"`/`"b"` independent; rejected hit is not recorded (still allowed exactly when the oldest expires); `limit=0`/negative → every hit rejected; pruning: after 10 000 distinct keys expire, internal storage size is 0 after one more `hit`.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** with `dict[str, deque[float]]`.
- [ ] **Step 4: Run** file, suite, `make check`.
- [ ] **Step 5: Commit.**
  ```bash
  git add backend/app/core/rate_limit.py backend/tests/test_rate_limit.py
  git commit -m "feat(backend): скользящий лимит частоты запросов (LCT-20)"
  ```

---

### Task 4: `AssistantService` and schemas

**Files:**
- Create: `backend/app/domains/assistant/schemas.py`, `backend/app/domains/assistant/ask_service.py`
- Test: `backend/tests/test_assistant_ask_service.py` (create)

**Interfaces:**
- Consumes: Tasks 1–3; `AssistantReportService.build(site_id) -> BuiltReport` (`report`, `stage_ids`); `SiteAccessGuard.require(site_id) -> Site` (`.owner_id`); `AssistantClient`; `SlidingWindowRateLimiter`; `Settings.assistant`; `SITE_LABEL` from `report.py`.
- Produces:
  - `schemas.py`: `AskRequest(question: str)` = pydantic model with `question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=500)]`; `StageRefRead(ref: str, stage_id: uuid.UUID)`; `AssistantAnswerRead(answer, verified, numbers_not_in_report, numbers_of_other_site, limits, site_label: str, stages: list[StageRefRead])`; `AssistantStatusRead(enabled: bool)`.
  - `ask_service.py`: `referenced_stages(answer: str, stage_ids: dict[int, uuid.UUID]) -> list[StageRefRead]` — regex `(?<!\w)этап[а-яё]*\s*№?\s*(\d{1,4})(?!\d)` (case-insensitive), first-appearance order, unique, only numbers present in `stage_ids`, `ref = f"этап {n}"`.
  - `class AssistantService`: `__init__(self, reports: AssistantReportService, client: AssistantClient, limiter: SlidingWindowRateLimiter, guard: SiteAccessGuard, settings: Settings)`; `async def status(self) -> AssistantStatusRead` (`enabled = await client.available()`); `async def ask(self, site_id: uuid.UUID, question: str) -> AssistantAnswerRead` implementing the order of checks from "Decisions", mapping: `AssistantError` → `AppError(error.message, error.status_code, code=error.code)`; rate limit → `AppError(f"Слишком много вопросов. Повторите через {ceil(wait)} с.", 429, code="rate_limited")`; unavailable-by-status → `AppError("Ассистент недоступен", 503, code="assistant_unavailable")`; size → `AppError("Отчёт слишком велик для ассистента", 413, code="report_too_large")` when `len(json.dumps(report, ensure_ascii=False).encode()) > max_report_kb * 1024`. Logging per Global Constraints (`logger.info("assistant.ask site=%s q_len=%d a_len=%d verified=%s ms=%d", ...)`). ML call: `client.ask(question, report, site_id=SITE_LABEL)`.

- [ ] **Step 1: Write failing tests** with stubs (`FakeAssistantClient`, a fake report service returning a fixed `BuiltReport`, a fake guard returning an object with `owner_id`, a real limiter with a fake clock, a call recorder on the report stub):
  - `test_успех_собирает_ответ_и_ссылки_на_этапы`: answer `"Этап 3 «Устройство свай» отстаёт. Этапа 3 и этап №4, этап 99."` with `stage_ids={3: id3, 4: id4}` → `stages == [ref "этап 3"→id3, ref "этап 4"→id4]`, `site_label == "p1"`.
  - `test_referenced_stages_регистры_и_дубли`: "Этап 3", "этапа 3", "этап №3", "ЭТАП 3" → one entry; "этап 99" dropped; "этап 30" not read as 3.
  - `test_verified_false_и_списки_без_изменений`.
  - `test_ml_не_настроен_503_и_отчёт_не_строится`: `client.available()` False → `AppError` 503 `assistant_unavailable`; report stub and `client.ask` calls == 0; limiter not consumed.
  - `test_чужая_площадка_404_до_всего`: guard raises `AppError(..., 404)` → propagated; report stub, client and limiter untouched.
  - `test_нет_графика_404`: report stub raises `AppError("График не загружен", 404)` → propagated, `client.ask` not called.
  - `test_лимит_частоты`: `rate_limit_per_min=2`: two asks pass, third → 429 `rate_limited`, message contains "Повторите через"; after the fake clock advances 61 s it passes again; `client.ask` call count == 2 before the advance.
  - `test_отчёт_слишком_велик_413`: `max_report_kb=1` and a 5 KB report → 413 `report_too_large`, `client.ask` not called.
  - parametrized `test_ошибки_клиента_маппятся_в_app_error`: `AssistantUnavailable`, `AssistantTimeout`, `AssistantBadRequest(422, out_of_scope, message)`, `AssistantBadRequest()` → `AppError` with the same status/code/message.
  - `test_в_логах_нет_текста_ответа_и_вопроса`: `caplog` at INFO, answer `"Секретный ответ p1"` and question `"Секретный вопрос"` → neither string in `caplog.text`; `verified` and lengths present.
  - `test_status`: `FakeAssistantClient(enabled=False)` → `enabled False`; `True` → `True`.
  - `test_askrequest_границы`: `"  ab  "` fails, `"abc"` passes and `"а"*500` passes, `"а"*501` fails, surrounding whitespace is stripped.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** schemas and service.
- [ ] **Step 4: Run** file, suite, `make check`.
- [ ] **Step 5: Commit.**
  ```bash
  git add backend/app/domains/assistant/schemas.py backend/app/domains/assistant/ask_service.py backend/tests/test_assistant_ask_service.py
  git commit -m "feat(backend): AssistantService — проверки, лимит, ссылки на этапы, маппинг ошибок (LCT-20)"
  ```

---

### Task 5: Router, providers, DI, HTTP tests, docs

**Files:**
- Create: `backend/app/domains/assistant/router.py`
- Modify: `backend/app/domains/assistant/provider.py` (split providers), `backend/app/plugins/di.py`, `backend/app/plugins/routing.py`
- Modify: `backend/tests/conftest.py` (test container includes assistant providers with `FakeAssistantClient`)
- Modify: `ml/docs/ASSISTANT.md` (§6: real endpoints and the error table from "HTTP contract")
- Test: `backend/tests/test_assistant_router.py` (create)

**Interfaces:**
- Produces:
  - `router.py`: `router = APIRouter(tags=["assistant"])`; `POST /sites/{site_id}/assistant/ask` (body `AskRequest`, response `AssistantAnswerRead`), `GET /assistant/status` (response `AssistantStatusRead`); handlers use `@inject` and `FromDishka[AssistantService]`. Registered in `routing.py` after `assessment_router`.
  - `provider.py`: `AssistantProvider` (keeps `AssistantReportService`; adds APP `rate_limiter(settings) -> SlidingWindowRateLimiter` built from `settings.assistant.rate_limit_per_min`, REQUEST `AssistantService`) and a separate `AssistantClientProvider` (APP: `assistant_client(settings, http_client: DetectorHttpClient) -> AssistantClient` via `create_assistant`, reusing the shared client from `PhotoProvider`). `create_container()` registers both. The existing LCT-19 DI tests must keep passing.
  - `conftest.py`: a `TestAssistantClientProvider` (APP: `AssistantClient` → a single `FakeAssistantClient`) replaces `AssistantClientProvider` in `_make_container` and the `container` fixture; `AssistantProvider()` is added to both. Fixture `assistant_client(container) -> FakeAssistantClient` for configuring answers/errors.

- [ ] **Step 1: Write failing HTTP tests** (`client` fixture; base `http://test/api`; seed with helpers imported from `tests.test_assessment_router`: `seed_stand_user`, `create_site_with_schedule`, `create_stage_status`):
  - `test_ask_успех`: site with 2 stages, one status; fake answer mentioning "этап 1" → 200; body has all seven fields, `site_label == "p1"`, `stages == [{"ref": "этап 1", "stage_id": <id of first stage by position>}]`; the fake received a `report` whose `sites[0].site_id == "p1"` and containing no UUID (`json.dumps` scan) and `site_id == "p1"` argument.
  - `test_verified_false_доходит_без_изменений` (both lists, `limits` intact).
  - parametrized `test_ошибки_ml`: fake raises `AssistantUnavailable` → 503 body `code == "assistant_unavailable"`; `AssistantTimeout` → 504 `assistant_timeout`; `AssistantBadRequest(status_code=422, code="out_of_scope", message="Только по отчёту")` → 422 `{"detail": "Только по отчёту", "code": "out_of_scope"}`; generic `AssistantBadRequest` → 400 `assistant_bad_request`.
  - `test_ml_не_настроен`: `FakeAssistantClient(enabled=False)` → `GET /assistant/status` = `{"enabled": false}` (200) and `ask` → 503 with `code`, fake `calls == []`.
  - `test_status_включён`: `{"enabled": true}`.
  - `test_вопрос_границы`: 2 chars → 422 (list `detail`, no `code`); `"  ab  "` → 422; 500 chars → 200; 501 → 422.
  - `test_чужая_и_несуществующая_площадка_404`: random uuid → 404, fake `calls == []`.
  - `test_нет_графика_404`: site without schedule → 404 `"График не загружен"`.
  - `test_лимит_429`: 10 successful asks, 11th → 429 `rate_limited`; `fake.calls` length 10.
  - `test_ключ_и_детали_не_в_ответе_и_логах`: fake raises `AssistantTimeout` whose internal attributes carry no secrets (assert body text lacks `sk-`) and `caplog` lacks the answer text on a successful call.
  - `test_ответ_не_сохраняется`: after a successful ask, no table gained rows (compare row counts of `photos`, `deviations`, `stage_statuses` before/after; there is no assistant table).
  - `test_openapi_содержит_ручки`: `/api/openapi.json` lists both paths.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** router, providers, DI/routing registration and conftest changes.
- [ ] **Step 4: Update `ml/docs/ASSISTANT.md` §6** — replace the "Ориентировочно" list with the implemented endpoints, response shape and the error table from this plan; note that there is no authentication yet (rate limit only).
- [ ] **Step 5: Run** the full backend suite and `make check`; run the ML suite once more (`cd ml && uv run --no-project --python 3.12 --with pytest --with fastapi --with httpx --with pillow --with numpy --with python-multipart --with openpyxl python -m pytest tests -q`) to confirm nothing on the ML side changed.
- [ ] **Step 6: Commit.**
  ```bash
  git add backend/app/domains/assistant backend/app/plugins backend/tests/conftest.py backend/tests/test_assistant_router.py ml/docs/ASSISTANT.md
  git commit -m "feat(backend): ручки ассистента, DI и HTTP-тесты (LCT-20)"
  ```

---

## Self-Review

- **Issue coverage (LCT-20):** adapter with Protocol/Http/Null, shared client, separate timeout, no retries (T2); exceptions mapped to 503/504/400/422 without secrets (T2, T4); size cap (T4); domain files schemas/service/router/provider, nothing stored (T4–T5); both endpoints (T5); site guard (T4); rate limit → 429 (T3–T4); site label + stage links (T4–T5); no full-answer logging (T4); registration in routing/DI (T5); `AssistantSettings` + `.env.dist` (T1); adapter/service/router/secret tests (T2, T4, T5). **Not built:** `401` (no auth in the project — see Decisions).
- **Type consistency:** `AssistantAnswer` (adapter) → `AssistantAnswerRead` (schema) field names identical; `AssistantError.status_code/code/message` → `AppError(message, status_code, code)`; `stage_ids: dict[int, UUID]` from LCT-19 `BuiltReport`; `SITE_LABEL` reused, not redefined.
- **Residual risks (stated in the PR):** rate limit is per process and keyed by the stand user; no authentication; `available()` cache means the UI may lag up to 30 s behind an ML restart; the `stages` parse depends on the model writing "этап N" (the ML prompt and answer gate require it).
- **Follow-ups for other issues:** LCT-21 implements the error table above (show `detail` for `out_of_scope`, hide the panel on `assistant_unavailable`, offer retry on `assistant_timeout`); LCT-22 uses `stages[].stage_id` for links; a separate issue for real authentication.
- **Proportion:** five tasks, each independently reviewable: config/error contract, adapter, limiter, orchestration, HTTP surface.
