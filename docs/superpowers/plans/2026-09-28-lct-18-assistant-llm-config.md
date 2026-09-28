# LCT-18: LLM provider from `.env` and assistant availability — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The LLM provider for the report assistant is configured only through `.env`, the key lives only in the `ml` container, `GET /meta` tells callers whether the assistant is available without a paid call, and the cross-site number check works for any `site_id` format.

**Architecture:** One helper in `ml/tools/ask_report.py` (`llm_config()`) replaces three duplicated `from_env` calls and feeds both `POST /ask` and `GET /meta`. The site-mismatch check derives site labels from the report instead of the hard-coded `p\d{2}`. Compose passes `LLM_*` to `ml` only and blanks them for `backend`, which reads the whole `.env` via `env_file`.

**Tech Stack:** Python 3.12, FastAPI, pytest (`fastapi.testclient`), Docker Compose.

**Spec:** Linear LCT-18 (https://linear.app/kaiangel/issue/LCT-18/assistent-provajder-llm-iz-env-i-status-dostupnosti-ml-deploy); parent LCT-17; `ml/docs/ASSISTANT.md` §3, §5. Design is decided in this plan; no separate spec doc.

## Global Constraints

- Provider variables are exactly `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (OpenAI `/chat/completions` format, `Authorization: Bearer`, `temperature: 0`); unchanged wire format.
- `POST /ask` contract (request/response fields, codes 400/422/503/504) does not change. Only `limits` text may gain one sentence (Task 1) and the 504 `detail` text changes (Task 2).
- The API key value never appears in any HTTP response, log line, or `GET /meta`.
- `LLM_*` are passed to the `ml` service only; the `backend` container must see them empty; `frontend` gets nothing.
- Code comments, docstrings, test names and user-facing strings are in Russian, matching the surrounding code (`ml/tests/test_pipeline.py` uses Russian test names).
- Python tests run with:
  `cd ml && uv run --no-project --python 3.12 --with pytest --with fastapi --with httpx --with pillow --with numpy --with python-multipart --with openpyxl python -m pytest <paths> -q`
  Baseline before this work: `tests/test_service.py tests/test_pipeline.py` → 86 passed, 1 skipped.
- Work happens on a branch named after the Linear task (`ivansaidyashev/lct-18-…`), created by the orchestrator before Task 1.

## Review Focus

Failure modes the spec implies but a naive implementation misses, most likely first. Each has a test in the owning task.

1. Site ids that are not `pNN` (`site-01`, UUID with hyphens, Cyrillic name): a number quoted after the wrong label must be flagged. (Task 1)
2. Prefix collision: sites `p1` and `p10` — "p10" must not be read as label `p1` followed by "0". (Task 1)
3. Answer names no site while the report has several: `verified` stays as level 1 says, but `limits` must say the per-site check was not performed; with a single-site report no such sentence. (Task 1)
4. `LLM_*` set to whitespace or empty string (compose interpolation of an unset variable yields `""`): treated as not configured, `assistant: false`. (Task 2)
5. Provider failure text carrying the key or provider host (`urllib` error messages include the host; a proxy error may echo headers): the client sees only a fixed category. (Task 2)
6. `backend` inherits the key through `env_file: .env`: compose must blank it. (Task 3)

---

### Task 1: Site labels from the report in the number check

**Files:**
- Modify: `ml/tools/ask_report.py` (`misattributed`, new `site_marks`, `mentions_site`, `LIMITS`, `limits_for`; CLI tail uses `limits_for`)
- Modify: `ml/service/app.py` (`/ask` uses `ask_report.limits_for` instead of the inline string)
- Test: `ml/tests/test_ask_check.py` (create)

**Interfaces:**
- Consumes: `numbers_by_site(data) -> dict[str, set[str]]` (existing; keys are `site_id`s plus `"_общие"`).
- Produces (all in `ask_report`):
  - `LIMITS: str` — the existing "Проверяются числа, а не смысл…" sentence, verbatim.
  - `NO_SITE_NOTE: str` = `"Ответ не называет площадку, поэтому числа не сверены по площадкам: они проверены только по отчёту в целом."`
  - `site_marks(answer: str, by_site: dict[str, set[str]]) -> list[re.Match[str]]` — mentions of real site ids, in order; ids that are purely digits are skipped (indistinguishable from numbers); `"_общие"` is not a site.
  - `mentions_site(answer: str, by_site: dict[str, set[str]]) -> bool`
  - `limits_for(answer: str, by_site: dict[str, set[str]]) -> str` — `LIMITS`, plus `" " + NO_SITE_NOTE` when the report has more than one real site and `mentions_site` is false.
  - `misattributed(answer, by_site) -> list[str]` — same signature and output format (`"p03: 114"`) as today, driven by `site_marks`.

- [ ] **Step 1: Write the failing tests** in `ml/tests/test_ask_check.py`. Fixture helper `by(*ids)` builds `{id: {"14","43"}, "_общие": {"47"}}` style dicts. Tests (names in Russian):
  - `test_метка_не_pNN_ловит_чужое_число[site-01|3f2a9c1e-7b64-4d0a-9e51-0c8d2b7a1f34|Стройка-Север]`: ids `A`, `B` from the parametrized set (A has `{"14"}`, B has `{"99"}`); `misattributed(f"{A} отстаёт на 99 дней.", by)` is non-empty and equals `[f"{A}: 99"]`.
  - `test_p1_и_p10_не_путаются`: sites `p1` (`{"5"}`) and `p10` (`{"77"}`); `misattributed("По p10 отставание 77.", by) == []` and `misattributed("По p1 отставание 77.", by) == ["p1: 77"]`.
  - `test_pNN_поведение_прежнее`: reuse the existing `ОТЧЁТ` figures — `"Площадка p08 отстаёт на 43 дня."` is flagged when 43 belongs to p03 only (mirror `test_число_чужой_площадки_ловится`).
  - `test_числовые_id_не_считаются_метками`: sites `1` and `2`; `site_marks("площадка 1: 14 дней", by) == []`.
  - `test_limits_без_названной_площадки_при_нескольких`: two sites, answer `"Отставание 14 дней."` → `limits_for(...) == LIMITS + " " + NO_SITE_NOTE`.
  - `test_limits_с_названной_площадкой_без_добавки`: same, answer `"По p03 отставание 14 дней."` → `limits_for(...) == LIMITS`.
  - `test_limits_одна_площадка_без_добавки`: one site, answer without label → `limits_for(...) == LIMITS`.

- [ ] **Step 2: Run to verify they fail**
  Run: `… python -m pytest tests/test_ask_check.py -q`
  Expected: FAIL/ERROR — `site_marks`, `limits_for`, `LIMITS` not defined; parametrized non-`pNN` cases fail against the old regex.

- [ ] **Step 3: Implement in `ml/tools/ask_report.py`.**
  `site_marks`: build one compiled pattern from the real ids (`re.escape`, sorted longest first so `p10` wins over `p1`), wrapped as `(?<![\w-])(?:…)(?![\w-])`; case-sensitive (as before). Return `[]` when there are no eligible ids. `misattributed` keeps its slicing logic (fragment after a mark up to the next mark), only the mark source changes from `\bp\d{2}\b` to `site_marks`. Update the `misattributed` docstring: labels come from the report. Move the `limits` string out of `app.py` into `LIMITS`; in the CLI tail print `limits_for(answer, by_site)` instead of the two fixed lines' first sentence (keep "Источник истины…" line).

- [ ] **Step 4: Wire `ml/service/app.py::ask_about_report`** to `"limits": ask_report.limits_for(answer, by_site)` where `by_site = ask_report.numbers_by_site(data)` is computed once and also passed to `misattributed`.

- [ ] **Step 5: Run to verify they pass**
  Run: `… python -m pytest tests/test_ask_check.py tests/test_pipeline.py tests/test_service.py -q`
  Expected: all pass (baseline 86 + new; the existing `TestПроверка…` cases still green).

- [ ] **Step 6: Commit**
  ```bash
  git add ml/tools/ask_report.py ml/service/app.py ml/tests/test_ask_check.py
  git commit -m "fix(ml): метки площадок в проверке чисел берутся из отчёта, а не из p\\d{2} (LCT-18)"
  ```

---

### Task 2: `llm_config()`, sanitized LLM errors, `assistant` flag in `/meta`

**Files:**
- Modify: `ml/tools/ask_report.py` (`LLMConfig`, `llm_config`, `describe_llm_error`; CLI uses `llm_config`)
- Modify: `ml/service/app.py` (`/meta`, `/ask`, module logger, lazy `ask_report` import helper)
- Modify: `ml/tests/conftest.py` (fixture `llm_env`)
- Test: `ml/tests/test_assistant_service.py` (create)

**Interfaces:**
- Consumes: `suggest_stage_mapping.from_env(key) -> str | None` (reads process env, then `ml/.env`; module global `ML` is the `.env` directory).
- Produces:
  - `ask_report.LLMConfig` — `NamedTuple(base_url: str, api_key: str, model: str)`.
  - `ask_report.llm_config() -> LLMConfig | None` — `None` if any of the three is missing or blank after `.strip()`. Not cached: env lookup plus a small file read per call; the value is fixed for the process lifetime anyway, and the `.env` fallback is only used outside containers.
  - `ask_report.describe_llm_error(exc: BaseException) -> str` — fixed category, never the exception text: `HTTPError` → `f"HTTP {exc.code}"`; timeout (`TimeoutError`, `socket.timeout`, or `URLError` whose `reason` is a timeout) → `"тайм-аут"`; other `URLError`/`OSError` → `"нет соединения с провайдером"`; `json.JSONDecodeError`/`KeyError`/`IndexError`/`TypeError` → `"неожиданный ответ провайдера"`; anything else → `"ошибка запроса"`. Check `HTTPError` before `URLError` (it is a subclass).
  - `conftest.py` fixture `llm_env(monkeypatch, tmp_path)` returning a setter `set(base_url=..., api_key=..., model=...)`: first `delenv`s the three vars and points `suggest_stage_mapping.ML` at `tmp_path` (so a developer's real `ml/.env` cannot leak into tests); `set(...)` then `setenv`s the given values.
  - `GET /meta` gains `"assistant": bool` (`llm_config() is not None`); no other value from the config is exposed.

- [ ] **Step 1: Write the failing tests.** `ml/tests/test_assistant_service.py` — pure tests plus endpoint tests through `TestClient(app)`; endpoint tests that need `/meta` install a `Detector` with `FakeModel` the same way `tests/test_service.py::test_meta_includes_stamp_flag` does (import `FakeModel` from `tests.test_service` or copy the 6-line setup into a local fixture `ready_detector`). `/ask` tests do not need a detector.
  - `test_llm_config_none_если_ничего_не_задано(llm_env)`; `test_llm_config_все_три_заданы(llm_env)` → `LLMConfig("https://x/v1", "k", "m")`.
  - `test_llm_config_пробелы_и_пусто_считаются_незаданными(llm_env)`: `set(base_url="https://x/v1", api_key="   ", model="m")` → `None`; `api_key=""` → `None`.
  - `test_llm_config_читает_ml_env_файл(llm_env, tmp_path)`: write `tmp_path/".env"` with the three lines, no env vars → config returned.
  - `test_describe_llm_error` parametrized: `HTTPError(url, 401, …)` → `"HTTP 401"`; `TimeoutError()` → `"тайм-аут"`; `URLError(TimeoutError())` → `"тайм-аут"`; `URLError("Name or service not known: secret-host.example")` → `"нет соединения с провайдером"` and `"secret-host"` not in result; `KeyError("choices")` → `"неожиданный ответ провайдера"`; `RuntimeError("Bearer sk-123")` → `"ошибка запроса"` and `"sk-123"` not in result.
  - `test_meta_assistant_false_без_настройки(llm_env, ready_detector)`: `/meta` → `data["assistant"] is False`.
  - `test_meta_assistant_true_и_без_секретов(llm_env, ready_detector)`: with `api_key="sk-SECRET"`, `data["assistant"] is True` and `"sk-SECRET" not in response.text` and `"https://x/v1" not in response.text`.
  - `test_ask_503_без_настройки(llm_env)`: valid body → 503, and `detail` mentions `LLM_BASE_URL`.
  - `test_ask_400_нет_площадки(llm_env)`: configured, `site_id="p99"` not in report → 400.
  - `test_ask_504_сообщение_без_секретов(llm_env, monkeypatch)`: configured with `api_key="sk-SECRET"`; monkeypatch `ask_report.ask` to raise `RuntimeError("401 Bearer sk-SECRET host llm.secret.example")` → 504, `"sk-SECRET" not in response.text`, `"llm.secret.example" not in response.text`, and `"ошибка запроса"` in `detail`.
  - `test_ask_успех_возвращает_limits_и_verified(llm_env, monkeypatch)`: monkeypatch `ask_report.ask` to return `"Площадка p03, этап 12.3.2 отстаёт на 14 дней."` for the sample report from `test_pipeline.ТестПроверка.ОТЧЁТ` shape (`p03`, `p08`) → 200, `verified is True`, `"Проверяются числа" in limits`.
  Use the `ОТЧЁТ` figures already in `test_pipeline.py` (copy the dict; do not import a test class).

- [ ] **Step 2: Run to verify they fail**
  Run: `… python -m pytest tests/test_assistant_service.py -q`
  Expected: FAIL — `llm_config`, `describe_llm_error` missing; `/meta` has no `assistant`; 504 detail currently embeds the raw exception.

- [ ] **Step 3: Implement in `ml/tools/ask_report.py`** (`LLMConfig`, `llm_config`, `describe_llm_error` as specified). CLI `main()` replaces its three `from_env` calls with `llm_config()`; the "не настроена" branch is unchanged.

- [ ] **Step 4: Implement in `ml/service/app.py`.**
  Add `logger = logging.getLogger(__name__)` if the module has none. Factor the existing `sys.path.insert(...)`/`import ask_report` block into a private helper `_ask_report_module()` (same lazy behaviour) used by both endpoints. `/meta` returns `{**detector().meta(), "stamp": True, "assistant": <llm_config() is not None>}`. `/ask`: use `llm_config()` (503 message unchanged), pass `cfg.base_url, cfg.api_key, cfg.model` to `ask_report.ask`, and on failure `raise HTTPException(504, f"языковая модель не ответила: {describe_llm_error(exc)}")`; log `logger.warning("/ask: вызов LLM не удался: %s", describe_llm_error(exc))` — never `exc` itself.

- [ ] **Step 5: Add the `llm_env` fixture** to `ml/tests/conftest.py` as specified.

- [ ] **Step 6: Run to verify they pass**
  Run: `… python -m pytest tests -q`
  Expected: all pass (no regressions in `test_service.py`, `test_pipeline.py`, `test_ask_check.py`).

- [ ] **Step 7: Commit**
  ```bash
  git add ml/tools/ask_report.py ml/service/app.py ml/tests/conftest.py ml/tests/test_assistant_service.py
  git commit -m "feat(ml): llm_config, assistant в /meta, /ask без утечки текста ошибок провайдера (LCT-18)"
  ```

---

### Task 3: `.env`, compose, docs

**Files:**
- Modify: `.env.dist` (root) — append the `LLM_*` block
- Modify: `ml/.env.dist` — make sure the same three keys are documented (add if missing)
- Modify: `deploy/docker/common/core.yaml` — `ml.environment` and `backend.environment`
- Modify: `deploy/README.md` — new subsection under "ML-детектор"
- Modify: `ml/docs/ASSISTANT.md` §5 — one paragraph: in Docker the variables come from the root `.env`; `GET /meta` → `assistant`

**Interfaces:**
- Consumes: `LLM_*` names from Task 2 (`llm_config()` reads exactly these).
- Produces: root `.env` keys `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (empty by default = assistant off); no code interface.

- [ ] **Step 1: Root `.env.dist`.** Append (values empty, comment in Russian): a block titled "Ассистент по отчёту (ml-сервис)" with the three keys, one line explaining the OpenAI-compatible `/chat/completions` format, cloud or local model, and that empty values simply disable the assistant. Note: the executing session may lack permission to read/write `.env.dist`; if so, stop and ask the human to append the block manually — do not work around it.

- [ ] **Step 2: `ml/.env.dist`.** Read it; add the three keys only if absent.

- [ ] **Step 3: Compose `deploy/docker/common/core.yaml`.**
  Under `ml.environment` add `LLM_BASE_URL: ${LLM_BASE_URL:-}`, `LLM_API_KEY: ${LLM_API_KEY:-}`, `LLM_MODEL: ${LLM_MODEL:-}`. Under `backend.environment` add the same three names set to `""` with a comment: `backend` reads all of `.env` via `env_file`, and the key must not reach it (`environment` overrides `env_file`). Do not touch `frontend`. `prod/core.yaml`, `prod/tunnel.yaml`, `dev/core.yaml` need no change (they inherit `common`).

- [ ] **Step 4: Verify with compose.**
  Use the exact `-f`/`--env-file` layers from the `makefile` `dev` target (read the file first). Ensure a `.env` exists (if none, create one from `.env.dist` for the check and remove it afterwards) and append `LLM_BASE_URL=https://llm.test/v1`, `LLM_API_KEY=sk-TEST`, `LLM_MODEL=m-test` to it.
  Run: `docker compose <layers> config --format json` and inspect `services.ml.environment` and `services.backend.environment`.
  Expected: `ml` has all three with the test values; `backend` has all three equal to `""`; `frontend` has none. Then repeat with the three lines removed: `ml` values are `""`.

- [ ] **Step 5: `deploy/README.md`.** Add "Ассистент по отчёту (LLM)" after the ML-детектор section: which three variables to set in the root `.env`; cloud vs local model (any server speaking `/chat/completions`); where the key lives (only `ml`); how to check — `GET /meta` on the `ml` service shows `"assistant": true|false`, and `python tools/suggest_stage_mapping.py --list-models` (run inside `ml/` with the variables in `ml/.env`) lists the provider's models; that without variables `POST /ask` answers 503 and this is the normal state. Update `ml/docs/ASSISTANT.md` §5 with the two facts from "Files".

- [ ] **Step 6: Commit**
  ```bash
  git add .env.dist ml/.env.dist deploy/docker/common/core.yaml deploy/README.md ml/docs/ASSISTANT.md
  git commit -m "feat(deploy): LLM_* из .env только в ml, документация подключения провайдера (LCT-18)"
  ```

---

## Self-Review

- **Spec coverage.** `.env.dist` (T3 S1–2); compose to `ml` only (T3 S3–4); README + `--list-models` (T3 S5); key not in logs/errors (T2: `describe_llm_error`, logger, tests); `assistant` in `/meta` (T2); single config read (T2 `llm_config`, decision on caching recorded); labels from report (T1); no-marks case reflected in `limits` (T1); tests for `p03`/`site-01`/UUID (T1); delimiter behaviour with hyphens/Cyrillic (T1 lookarounds, tests). DoD: empty vars → `assistant:false` + 503 (T2 tests); compose check (T3 S4); provider swap without code (config-only by construction, T2 `llm_config`); mismatch caught for any id format (T1).
- **Decision recorded.** "Read at start but do not cache forever" is resolved as *no cache*: the helper is called per request. It is a dict lookup plus an optional small file read, and it makes a changed `ml/.env` effective without a restart outside Docker.
- **Known limitation.** `GET /meta` returns 503 while the detector is still warming up (`detector()` raises), so the availability flag is briefly unavailable after start. Callers (LCT-20 status endpoint) must treat that as "not enabled yet" and re-check within their cache window. Not changed here to keep `/meta` semantics.
- **Type consistency.** `by_site` is `dict[str, set[str]]` everywhere; `limits_for`/`mentions_site`/`site_marks`/`misattributed` all take `(answer, by_site)`; `llm_config()` → `LLMConfig | None` used in `/meta`, `/ask`, CLI.
- **Proportion.** Three tasks, one per independently reviewable deliverable (check logic, config + error hygiene, deployment wiring).
