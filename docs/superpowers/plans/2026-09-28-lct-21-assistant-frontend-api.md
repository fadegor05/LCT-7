# LCT-21: assistant frontend API layer — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The data layer the assistant panel (LCT-22) builds on: Zod schemas for the LCT-20 contract, an `ApiError` that keeps the backend `code`, typed failure classification, TanStack Query hooks (`useAssistantStatus`, `useAskAssistant`), cache keys, and MSW mocks with switchable scenarios. **No UI in this issue.**

**Architecture:** Follows `docs/architecture-frontend.md`: `api/client.ts` validates every response with Zod; one file per domain in `api/`; keys in `keys.ts`; mocks are an in-memory backend (`mocks/db.ts`) behind MSW handlers shared by browser and tests. Asking is a **mutation** (paid call: never triggered by focus/refetch/rerender), status is a query that fails closed (`enabled: false`).

**Tech Stack:** React 19, TypeScript strict, TanStack Query 5, Zod 4, MSW 2, Vitest 5 + Testing Library.

**Spec:** Linear LCT-21 (https://linear.app/kaiangel/issue/LCT-21/assistent-frontend-api-sloj-shema-zod-huk-kesh-klyuchi-msw-moki), parent LCT-17; backend contract from PR #37 (`ml/docs/ASSISTANT.md` §6).

**Base:** branch from `origin/feat-ai-assist` (LCT-18/19/20 are merged there). Push with an explicit branch name; never plain `git push` (no upstream is set on purpose).

## Decisions

- **`ApiError.code`.** Today `request()` drops the `code` field of the error body, but the whole LCT-20 contract is code-based (`out_of_scope`, `rate_limited`, …). `ApiError` gets `code: string | undefined` (only a string `code` is accepted).
- **Failure classification lives in `api/assistant.ts`** (`classifyAssistantError`), so LCT-22 renders by `kind` and never parses statuses. User-facing text: the server's Russian `detail` for coded errors; fixed client texts for validation, network and unknown errors.
- **Double submit is blocked in the hook**, not left to the UI: `ask()` while a request is in flight does nothing (TanStack mutations otherwise fire concurrently).
- **Cancel is client-side** (`AbortController` → `signal` into `request`); an aborted request is `kind: "cancelled"`, not an error to display.
- **Answers are ephemeral and site-bound.** They live only in the mutation state. They are dropped (`reset`, and an in-flight request is aborted) when `siteId` changes and when any query under `['site', siteId]` is invalidated — the frontend rule "any input edit invalidates the whole site" (architecture-frontend §4) applies to assistant answers too. Nothing is written to `localStorage`/`sessionStorage`/IndexedDB.
- **Scenario switch for mocks** is a function in the mock db (`setAssistantScenario`), reset by `resetDb()`; in the browser (non-test) the initial scenario can be set with `?assistant=<scenario>` for manual UI work in LCT-22. Components never know about scenarios.

## Global Constraints

- No new dependencies. Russian comments, docstrings, test names and user-facing strings, matching neighbouring code. Prettier/ESLint (`--max-warnings=0`)/tsc clean; coverage thresholds in `vite.config.ts` are not lowered.
- Verify with `cd frontend && pnpm check` (typecheck + lint + format:check + tests with coverage). `node_modules` is already installed; run `pnpm install` only if a command reports missing packages.
- Do not read, edit or list any `.env` file (`frontend/.env.development` and `.env.example` included).
- Types are inferred from Zod (`z.infer`), as in `schemas.ts`.

## Backend contract (from LCT-20)

`GET /api/assistant/status` → `{ enabled: boolean }`.
`POST /api/sites/{id}/assistant/ask` body `{ question }` (3..500 chars after trim) → `200`
`{ answer, verified, numbers_not_in_report: string[], numbers_of_other_site: string[], limits, site_label, stages: [{ ref, stage_id }] }`.
Errors: body `{ detail: string, code?: string }`, except question validation `422` where `detail` is a list and there is no `code`.

| status | code | kind (this issue) | retryable |
|---|---|---|---|
| 404 | – | `not_found` (server text) | no |
| 422 | – (`detail` list) | `invalid_question` ("Вопрос должен быть от 3 до 500 символов") | no |
| 422 | `out_of_scope` | `out_of_scope` (server text) | no |
| 429 | `rate_limited` | `rate_limited` (server text with seconds) | no |
| 413 | `report_too_large` | `too_large` (server text) | no |
| 503 | `assistant_unavailable` | `unavailable` (server text) | no |
| 504 | `assistant_timeout` | `timeout` (server text) | **yes** |
| 400 | `assistant_bad_request` | `bad_request` (server text) | no |
| network error (fetch rejects) | – | `unavailable` ("Нет связи с сервером") | no |
| aborted by the user | – | `cancelled` (empty text) | no |
| anything else | – | `unknown` ("Не удалось получить ответ") | no |

## Review Focus

1. Every backend `code` above reaches the UI as the right `kind` (test each); the list-`detail` 422 is not confused with `out_of_scope`. (Tasks 1, 3)
2. Status failures (fetch reject, 500, 503, 404, invalid JSON, contract mismatch) → `enabled: false`, **one** request (no retries), no unhandled rejection, no console error. (Task 3)
3. Double submit: a second `ask()` while pending sends exactly one network request in total. (Task 3)
4. Cancel: `cancel()` aborts the request, `isPending` becomes false, `failure.kind === "cancelled"`, no second request. (Task 3)
5. Local validation: `"  ab  "` and 501 chars never hit the network; 3 and 500 chars do; the sent question is trimmed. (Task 3)
6. Answer is not persisted anywhere and disappears on `reset()`, on `siteId` change, and on invalidation of `['site', siteId]`; an in-flight request is aborted in those cases and its late result never appears. (Task 3)
7. Contract drift: an answer without `stages` or with `verified: "yes"` → `ApiError` "не совпал с контрактом", not a half-rendered object. (Tasks 1, 3)
8. Unmount while pending: no state update warnings, no request left running. (Task 3)

---

### Task 1: `ApiError.code`, Zod schemas, mock error codes

**Files:**
- Modify: `frontend/src/api/client.ts` (`ApiError.code`, `request` reads `code`)
- Modify: `frontend/src/api/schemas.ts` (assistant schemas, question limits)
- Modify: `frontend/src/mocks/db.ts` (`MockError` optional `code`), `frontend/src/mocks/handlers.ts` (`handle()` emits `code`)
- Test: `frontend/src/api/client.test.ts` (extend), `frontend/src/api/assistantSchemas.test.ts` (create)

**Interfaces:**
- Produces:
  - `class ApiError`: constructor `(status: number, message: string, detail?: unknown, code?: string)`; `readonly code: string | undefined`. `request()` sets it from `data.code` only when `typeof === "string"`. Existing call sites keep working.
  - `schemas.ts`: `ASSISTANT_QUESTION_MIN = 3`, `ASSISTANT_QUESTION_MAX = 500`; `assistantQuestionSchema = z.string().trim().min(3, "Вопрос должен быть от 3 до 500 символов").max(500, <same text>)`; `assistantStageRefSchema = z.object({ ref: z.string(), stage_id: z.string() })`; `assistantAnswerSchema = z.object({ answer: z.string(), verified: z.boolean(), numbers_not_in_report: z.array(z.string()), numbers_of_other_site: z.array(z.string()), limits: z.string(), site_label: z.string(), stages: z.array(assistantStageRefSchema) })`; `assistantStatusSchema = z.object({ enabled: z.boolean() })`; types `AssistantAnswer`, `AssistantStageRef`, `AssistantStatus`.
  - `MockError(status: number, message: string, code?: string)` with `readonly code`; `handle()` returns `{ detail, code }` when the error has a code, `{ detail }` otherwise.

- [ ] **Step 1: Write failing tests.** `client.test.ts`: error body `{detail: "x", code: "rate_limited"}` → `ApiError` with `code === "rate_limited"`; body without `code` → `code === undefined`; `{code: 5}` (non-string) → `undefined`; 422 with list `detail` keeps `code === undefined`. `assistantSchemas.test.ts`: a valid answer parses; each of these fails: missing `stages`, `verified: "yes"`, `numbers_not_in_report: "1"`, missing `limits`; `assistantStatusSchema` accepts `{enabled: false}` and rejects `{}`; `assistantQuestionSchema`: `"  ab  "` fails, `"abc"` and a 500-char string pass, 501 fails, whitespace is trimmed in the output.
- [ ] **Step 2: Run to verify they fail.** `cd frontend && pnpm exec vitest run src/api/client.test.ts src/api/assistantSchemas.test.ts`.
- [ ] **Step 3: Implement** the interfaces above. Add a mock-level test in Task 2 for `handle()` emitting `code`.
- [ ] **Step 4: Run** the two files, then `pnpm check`.
- [ ] **Step 5: Commit.**
  ```bash
  git add frontend/src/api/client.ts frontend/src/api/schemas.ts frontend/src/api/client.test.ts frontend/src/api/assistantSchemas.test.ts frontend/src/mocks/db.ts frontend/src/mocks/handlers.ts
  git commit -m "feat(frontend): код ошибки в ApiError и Zod-схемы ассистента (LCT-21)"
  ```

---

### Task 2: MSW mocks with scenarios

**Files:**
- Modify: `frontend/src/mocks/db.ts` (scenario state + `assistantAsk`, `assistantEnabled`, `setAssistantScenario`, reset in `resetDb`), `frontend/src/mocks/handlers.ts` (two handlers)
- Test: `frontend/src/mocks/assistant.test.ts` (create)

**Interfaces:**
- Consumes: Task 1 (`MockError` with `code`, schemas), existing db helpers for site/schedule/stage statuses (read `db.ts`: `getSite`, `getSchedule`, and the statuses store used for `GET .../assessment/stages`).
- Produces (in `db.ts`):
  - `type AssistantScenario = "ok" | "unverified" | "out_of_scope" | "rate_limited" | "unavailable" | "timeout" | "too_large" | "no_llm" | "slow" | "unlinked"`
  - `setAssistantScenario(scenario: AssistantScenario): void`; `resetDb()` restores `"ok"` (in browser mode initial value may come from `?assistant=` if it is a valid scenario name; in tests always `"ok"`).
  - `assistantEnabled(): boolean` — `false` for `"no_llm"` and `"unavailable"`.
  - `assistantAsk(siteId: string, question: string): AssistantAnswer` mirroring backend order: `getSite` (404 "Стройка не найдена") → not enabled ⇒ `MockError(503, "Ассистент недоступен", "assistant_unavailable")` → `getSchedule` (404 "График не загружен") → scenario errors: `rate_limited` ⇒ `(429, "Слишком много вопросов. Повторите через 30 с.", "rate_limited")`, `timeout` ⇒ `(504, "Модель не ответила. Повторите вопрос позже.", "assistant_timeout")`, `out_of_scope` ⇒ `(422, "Ассистент отвечает только на вопросы по отчёту об этой площадке: этапы, отставание, отклонения, техника. Например: «где отставание и на сколько», «что с этапом 3».", "out_of_scope")`, `too_large` ⇒ `(413, "Отчёт слишком велик для ассистента", "report_too_large")`. Success: `stage_no` is the 1-based order of stages by `position`; the answer names the first stage whose status is `behind` as `Этап {n} «{name}» отстаёт на {delay_days} дней.` with `stages: [{ref: "этап {n}", stage_id}]`; if none is behind: `По площадке p1 отставаний не найдено.` and `stages: []`. `site_label: "p1"`. `limits` = the backend text `"Проверяются числа, а не смысл: верное число может быть отнесено не к тому этапу, и проверка этого не увидит. Источник истины — сам отчёт, ответ лишь пересказывает его."`. Scenario `unverified`: `verified: false`, `numbers_not_in_report: ["999"]`, `numbers_of_other_site: ["p1: 5"]`; `unlinked`: never returns `stages`; others: `verified: true`, empty lists.
  - Handlers: `GET {api}/assistant/status` → `{enabled: assistantEnabled()}`; `POST {api}/sites/:siteId/assistant/ask`: body `{question}` trimmed; length < 3 or > 500 ⇒ `422` with FastAPI-shaped list `detail` (`[{"loc": ["body","question"], "msg": "...", "type": "string_too_short" | "string_too_long"}]`) and **no** `code`; scenario `slow` waits 2 s (`delay(2000)`, skipped in tests by the existing `latency` convention — use a helper that is `Promise.resolve()` in test mode) before answering.

- [ ] **Step 1: Write failing tests** in `assistant.test.ts` using `request()` from `@/api/client` and `assistantAnswerSchema`/`assistantStatusSchema`: status `{enabled: true}` by default; `no_llm` and `unavailable` → `{enabled: false}`; success on the demo site (id from `mocks/fixtures` — the "Березники" demo, which has schedule and statuses) parses with the schema, `site_label === "p1"`, and every `stages[].stage_id` exists in `GET /sites/{id}/schedule`; a site without schedule (create a new site) → 404 "График не загружен"; unknown site → 404; each error scenario → the exact status, message and `ApiError.code` from the table; `unavailable` on ask → 503 `assistant_unavailable`; question `"ab"` and a 501-char question → 422 with `Array.isArray(detail)` and `code === undefined`; `unverified` returns the three fields; `unlinked` returns `stages: []`; `resetDb()` puts the scenario back to `ok` (set `timeout`, call `resetDb()`, ask succeeds); `handle()` includes `code` only for coded errors (covers Task 1 mock change).
- [ ] **Step 2: Run to verify they fail** (`pnpm exec vitest run src/mocks/assistant.test.ts`).
- [ ] **Step 3: Implement** db functions and handlers.
- [ ] **Step 4: Run** the file, then `pnpm check`.
- [ ] **Step 5: Commit.**
  ```bash
  git add frontend/src/mocks/db.ts frontend/src/mocks/handlers.ts frontend/src/mocks/assistant.test.ts
  git commit -m "feat(frontend): MSW-моки ассистента со сценариями (LCT-21)"
  ```

---

### Task 3: API functions, failure classification, hooks, keys, docs

**Files:**
- Create: `frontend/src/api/assistant.ts`
- Modify: `frontend/src/api/keys.ts`, `docs/architecture-frontend.md`
- Test: `frontend/src/api/assistant.test.tsx` (create)

**Interfaces:**
- Consumes: Tasks 1–2; `request`, `ApiError`, `keys`, `createTestQueryClient` (`src/test/render.tsx`), `setAssistantScenario`.
- Produces:
  - `keys.assistantStatus = ['assistant', 'status'] as const`; `keys.assistant = (siteId: string) => ['site', siteId, 'assistant'] as const` (used as `mutationKey`).
  - `assistantApi.status(signal?: AbortSignal)` → `request('/assistant/status', {schema: assistantStatusSchema, signal})`; `assistantApi.ask(siteId: string, question: string, signal?: AbortSignal)` → `POST /sites/{siteId}/assistant/ask` with `{question}`.
  - `type AssistantFailureKind = 'unavailable' | 'timeout' | 'rate_limited' | 'out_of_scope' | 'too_large' | 'not_found' | 'invalid_question' | 'bad_request' | 'cancelled' | 'unknown'`; `interface AssistantFailure { kind: AssistantFailureKind; message: string; retryable: boolean }`; `classifyAssistantError(error: unknown): AssistantFailure` per the contract table (an `AbortError` — `DOMException` with `name === 'AbortError'` — is `cancelled`; a non-`ApiError` from a rejected `fetch` (`TypeError`) is `unavailable`).
  - `useAssistantStatus(): { enabled: boolean; isPending: boolean }` — `useQuery` with `retry: false`, `staleTime: 30_000`, `refetchOnWindowFocus: false`; `enabled` is `true` only when the response says so; every error → `false`; no throw.
  - `useAskAssistant(siteId: string): { ask(question: string): Promise<AssistantAnswer | undefined>; cancel(): void; reset(): void; isPending: boolean; answer: AssistantAnswer | undefined; failure: AssistantFailure | undefined }`. `ask` returns `undefined` when ignored (already pending) or failed (the failure is in state), never rejects. Validation: `assistantQuestionSchema.safeParse(question)`; on failure state becomes `invalid_question` **without** a network call; the sent question is the trimmed value. Uses `useMutation({ mutationKey: keys.assistant(siteId), retry: false })` plus an `inFlight` ref and an `AbortController` per call; `cancel()` aborts; on `siteId` change and on a query-cache `invalidate` event whose `query.queryKey` starts with `['site', siteId]`, the hook aborts the request and resets the state (subscribe with `queryClient.getQueryCache().subscribe` inside an effect, clean up on unmount). A late result of an aborted/reset request is never stored.

- [ ] **Step 1: Write failing tests** (`renderHook` with `QueryClientProvider` and `createTestQueryClient()`; MSW handlers via `server.use` where a request counter is needed; the demo site id from fixtures):
  - `classifyAssistantError` table test for every row of the contract table (build `ApiError` values directly; `new DOMException('x', 'AbortError')`; `new TypeError('Failed to fetch')`; a plain `Error`); `timeout` is the only `retryable: true`.
  - `useAssistantStatus`: default → `enabled: true` after load, `isPending` true first; scenario `no_llm` → false; each of {handler returns 500, 503, 404, invalid JSON `"<html>"`, `{enabled: "yes"}`, `HttpResponse.error()`} → `enabled: false`, request counter exactly 1, no console error (spy `console.error`), no unhandled rejection.
  - `useAskAssistant` success: `ask("где отставание и на сколько")` → `answer` parses, `failure` undefined, `isPending` false at the end, request body was `{question: "где отставание и на сколько"}`; `ask("  ab  ")` → `failure.kind === 'invalid_question'` and counter 0; 3 and 500 chars → counter 1 each; a question with surrounding spaces is sent trimmed.
  - Errors: for each scenario `rate_limited`, `timeout`, `out_of_scope`, `too_large`, `unavailable` → `failure.kind` and `failure.message` from the mock; unknown site id → `not_found`; `HttpResponse.error()` → `unavailable`.
  - Double submit: with a handler that resolves after a controlled delay, call `ask()` twice synchronously → counter 1, the second call returns `undefined`.
  - Cancel: handler that never resolves; `ask()`, then `cancel()` → `isPending` false, `failure.kind === 'cancelled'`, counter 1, and a following `ask()` works.
  - Ephemeral: after success, `localStorage.length === 0` and `sessionStorage.length === 0`; `reset()` clears `answer`; changing `siteId` via `rerender` clears it; `queryClient.invalidateQueries({queryKey: ['site', siteId]})` (with a dummy active query under that key so the event fires) clears it; invalidating `['site', 'other']` does **not**; invalidation during a pending request aborts it and the late response never appears in `answer`.
  - Contract drift: handler returning an answer without `stages` → `failure.kind === 'unknown'` and the `ApiError.message` contains "не совпал с контрактом".
  - Unmount while pending: no React warning (spy `console.error`), request aborted.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** `assistant.ts` and the two keys.
- [ ] **Step 4: Docs** — `docs/architecture-frontend.md`: add `assistant.ts` to the `api/` tree in §2; add the two endpoints and one sentence on the error contract (`code`) to §4; add to §5 that `setAssistantScenario` / `?assistant=` switch mock scenarios.
- [ ] **Step 5: Run** the file, then `pnpm check` (coverage thresholds must hold), then `git status` — only intended files changed.
- [ ] **Step 6: Commit.**
  ```bash
  git add frontend/src/api/assistant.ts frontend/src/api/keys.ts frontend/src/api/assistant.test.tsx docs/architecture-frontend.md
  git commit -m "feat(frontend): API-слой ассистента — хуки, классификация ошибок, ключи (LCT-21)"
  ```

---

## Self-Review

- **Issue coverage (LCT-21):** schemas (T1); `useAssistantStatus` fail-closed without retries (T3); `useAskAssistant` as mutation, no auto-retries (T3); typed errors per status incl. 429 (T3 table); question validation 3–500 + trim (T1 schema, T3 hook); cache key bound to the site and dropped on input edits — implemented as the `['site', id, 'assistant']` mutation key plus reset-on-invalidate (T3, see Decisions: answers are not in the query cache); nothing persisted (T3 test); mocks with all scenarios incl. slow (T2); tests for success, each error, `enabled:false` on failure, no second request while pending (T3); coverage thresholds and `make front-check` (every task).
- **Beyond the issue text (needed for LCT-22):** `ApiError.code`, cancel, `retryable`, `?assistant=` dev switch.
- **Type consistency:** `AssistantAnswer` (Zod-inferred) is the mock `assistantAsk` return type and the hook `answer`; `AssistantFailure.kind` values are exactly those in the contract table; `keys.assistant(siteId)` is the same prefix the reset subscription matches (`['site', siteId]`).
- **Known limits:** the reset-on-invalidate fires only if a query under `['site', siteId]` is present in the cache (true on every site screen); the panel (LCT-22) should keep site queries mounted. Mock answers are canned; the real ML output shape is covered by the backend contract test in PR #37.
- **Proportion:** three tasks — error/contract foundation, mock backend, hooks + docs.
