# LCT-22: assistant panel on the site overview screen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A question/answer panel for the report assistant on the site overview screen: hidden when the assistant is unavailable, shows the answer with a visible verification verdict and the `limits` line, links "этап N" in the answer to that stage in the stage table, handles waiting/cancel/errors, and never stores or prints the answer.

**Architecture:** `features/assistant/` holds four focused units — a pure `linkifyAnswer`, `AssistantQuestionForm`, `AssistantAnswer`, and `AssistantPanel` (status gate + wiring of the LCT-21 hooks). Rendering is driven by `useAssistantStatus()` and `useAskAssistant(siteId)` (`failure.kind`, `answer`, `isPending`, `ask`, `cancel`); no request logic in components. The panel is mounted at the end of `SiteOverviewPage`.

**Tech Stack:** React 19, TypeScript strict, React Router 7, TanStack Query 5, CSS Modules + tokens, Vitest 5 + Testing Library + user-event + MSW.

**Spec:** Linear LCT-22 (https://linear.app/kaiangel/issue/LCT-22/assistent-frontend-panel-voprosa-i-otveta-na-ekrane-obuekta), parent LCT-17; `ml/docs/ASSISTANT.md` §4 and §6; the LCT-21 API layer (`frontend/src/api/assistant.ts`, PR #38).

**Base:** branch from `origin/feat-ai-assist` (LCT-18…21 are merged there). The branch is created without tracking; push with an explicit branch name.

## Decisions (where the plan interprets or extends the issue text)

- **Placement: the end of the overview page**, after "Последнее наблюдение". The panel appears only after the status query resolves; putting it at the bottom means its appearance shifts nothing above it ("не сдвигает основной контент, не мигает"). While the status is pending or `enabled: false`, **nothing** is rendered — no heading, no placeholder.
- **Links go to the stage row on the same page.** The answer's `stages: [{ref, stage_id}]` (backend) tells which "этап N" are real. Each stage row of `StageStatusTable` gets `id="stage-{stage_id}"` (+ `tabIndex={-1}` for focus) and a `:target` highlight; the answer renders plain `<a href="#stage-{stage_id}">` so the browser scrolls, focuses and `:target` styles the row. A reference not present in `answer.stages` stays plain text.
- **The site label (`p1`) is not turned into a link:** the report is always about the site that is open on the screen, so a link would only point to the page itself. It stays plain text. (The issue's "метки площадки → ссылки" is meaningful only for multi-site reports, which the backend does not produce.)
- **One small new UI primitive:** `TextAreaField` (same label/hint/error contract as `TextField`, shared `Field.module.css`), because Enter/Shift+Enter needs a multi-line field.
- **Retry re-asks the last question**, kept only in component memory (never in storage); offered only for `failure.retryable` (timeout).
- **Panel hides itself on `failure.kind === "unavailable"`** (503 on the question); `cancelled` renders nothing; `invalid_question` is shown inline at the field.
- **Printing:** the panel section is `display: none` under `@media print`; a test pins that rule in the CSS text.
- No "copy" button (YAGNI; the issue says only "if needed").

## Global Constraints

- Russian comments, docstrings, test names and all user-facing strings, matching neighbouring code. CSS Modules + tokens from `src/styles/tokens.css`; existing components first (`Callout`, `Button`, `SectionHeader`, `Icon`); no new dependencies.
- **Answer text is rendered as text nodes only** (React escaping); never `dangerouslySetInnerHTML`.
- Tools: `pnpm exec` / `pnpm check` **fail in this environment** — never run any pnpm command (never `pnpm install`; if `frontend/pnpm-workspace.yaml` appears, delete it). Run from `frontend/`: `./node_modules/.bin/vitest run [files]` (coverage: `--coverage`), `./node_modules/.bin/tsc -b`, `./node_modules/.bin/eslint . --max-warnings=0`, `./node_modules/.bin/prettier --check src` (never on `.`). Baseline: 32 files / 247 tests, coverage statements 94.94 %, all clean; thresholds 90/85/90/90 are not lowered.
- **No `eslint-disable` of any kind.** Fix root causes. No vacuous tests (no `expect` inside `if`/`try`); every behaviour pinned by a test that fails if the behaviour is removed. Use a typed helper instead of `.catch((e) => e)`.
- Mutation state from TanStack reaches React with a delay after `act` — in tests use `findBy…`/`waitFor`, never read state right after an action.
- Stage `git add` with **explicit paths only** (the sandbox hides `.env*`, so `git add -A` would record deletions). Do not read, list or touch `.env*`.
- Run git operations that write `.git/config` outside the sandbox only if they fail with "Operation not permitted".

## Review Focus

1. **No flash, no shift:** first render and `no_llm`/`unavailable` status render nothing (no heading, no textbox, no console error); the panel comes after "Последнее наблюдение" in DOM order. (Task 4)
2. **Verification is not decoration:** `verified:false` → an `alert` with icon + text "не прошёл проверку", both number lists shown, "сверьтесь с отчётом"; `verified:true` → no alert; `limits` is in the visible DOM in both cases and appears in no `title`/`aria-label`. (Tasks 3, 4)
3. **Paid call safety:** double click and Enter-while-pending produce one request; the submit button is disabled while pending. (Tasks 2, 4)
4. **Keyboard:** Enter submits, Shift+Enter inserts a newline without submitting, Enter during IME composition does not submit; after an answer arrives focus moves to the answer region. (Tasks 2, 4)
5. **Links are honest:** "Этап 3", "этапа 3", "этап №3", "ЭТАП 3" link; "этап 30" is not read as 3; a reference absent from `answer.stages` is plain text; concatenating all parts gives back the original text. (Task 1)
6. **Injection in the answer** (`<img src=x onerror=…>`, `**bold**`) shows as literal text. (Task 3)
7. **Errors:** timeout → message + "Повторить" (re-asks the same question and, on success, replaces the error); rate limit / out of scope / too large → server text without retry; unavailable on a question → panel disappears; user cancel → no error text. (Task 4)
8. **Ephemeral:** no `localStorage`/`sessionStorage`; the panel section is hidden in print. (Task 4)

---

### Task 1: `linkifyAnswer` and stage-row anchors

**Files:**
- Create: `frontend/src/features/assistant/linkifyAnswer.ts`
- Modify: `frontend/src/features/overview/StageStatusTable.tsx` (row `id`, `tabIndex`), `frontend/src/features/overview/Overview.module.css` (`:target` highlight)
- Test: `frontend/src/features/assistant/linkifyAnswer.test.ts` (create), extend `frontend/src/pages/SiteOverviewPage.test.tsx` (row ids)

**Interfaces:**
- Consumes: `AssistantStageRef` (`@/api/schemas`).
- Produces:
  - `type AnswerPart = { kind: 'text'; text: string } | { kind: 'stage'; text: string; stageId: string }`
  - `linkifyAnswer(answer: string, stages: readonly AssistantStageRef[]): AnswerPart[]` — regex `(?<!\w)этап[а-яё]*\s*№?\s*(\d{1,4})(?!\d)` (case-insensitive, the same as the backend's `referenced_stages`); a match becomes a `stage` part only if some `stages[i].ref` equals `этап {number}`; everything else is `text`; adjacent text is merged; empty answer → `[]`; `parts.map(p => p.text).join('') === answer` always.
  - `stageAnchorId(stageId: string): string` = `` `stage-${stageId}` `` (used by the table row and the link).
  - `StageStatusTable` rows: `<tr id={stageAnchorId(row.stage_id)} tabIndex={-1}>`; `Overview.module.css`: `.table tbody tr:target { background: var(--caution-soft); }` and a visible focus outline for the focused row using `--focus-ring`.

- [ ] **Step 1: Write the failing tests.** `linkifyAnswer.test.ts` (stages `[{ref:'этап 3', stage_id:'s3'}, {ref:'этап 4', stage_id:'s4'}]`): `it.each` of "Этап 3", "этапа 3", "этап №3", "ЭТАП 3", "этап3" → one `stage` part with `stageId 's3'` and the matched text preserved verbatim; `"этап 30"` and `"этап 99"` → only `text`; two different stages and a repeated one → three `stage` parts in order; text around and punctuation ("Этап 3, этап 4.") preserved; `stages: []` → a single `text` part; `''` → `[]`; a property test over 6 sample strings that `join` equals the input; `stageAnchorId('s3') === 'stage-s3'`. In `SiteOverviewPage.test.tsx`: the row of "Разработка котлована" has `id="stage-site-berezniki-stage-2"` (use the actual demo stage id: the mock builds `site-berezniki-stage-{n}` from `STAGE_TEMPLATE`, check the second template stage's name first) and `tabindex="-1"`.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** the function, the anchor helper (exported from `linkifyAnswer.ts`), the row attributes and the CSS.
- [ ] **Step 4: Run** the two files, then the full checks (`tsc`, `eslint`, `prettier --check src`, full vitest with coverage).
- [ ] **Step 5: Commit.**
  ```bash
  git add frontend/src/features/assistant/linkifyAnswer.ts frontend/src/features/assistant/linkifyAnswer.test.ts frontend/src/features/overview/StageStatusTable.tsx frontend/src/features/overview/Overview.module.css frontend/src/pages/SiteOverviewPage.test.tsx
  git commit -m "feat(frontend): разбор ответа ассистента в ссылки на этапы и якоря строк этапов (LCT-22)"
  ```

---

### Task 2: `TextAreaField` and `AssistantQuestionForm`

**Files:**
- Create: `frontend/src/components/ui/TextAreaField.tsx`, `frontend/src/components/ui/TextAreaField.test.tsx`, `frontend/src/features/assistant/AssistantQuestionForm.tsx`, `frontend/src/features/assistant/AssistantQuestionForm.module.css`
- Modify: `frontend/src/components/ui/Field.module.css` (`.textarea`: same look as `.input`, `min-height`, `resize: vertical`, `padding` from tokens)
- Test: `frontend/src/features/assistant/AssistantQuestionForm.test.tsx` (create)

**Interfaces:**
- Produces:
  - `TextAreaField({ label, hint, error, id, className, ref, ...textarea }: TextAreaFieldProps)` — same label/hint/error/`aria-describedby`/`aria-invalid` contract as `TextField` (`extends TextareaHTMLAttributes<HTMLTextAreaElement>`).
  - `AssistantQuestionForm({ pending, error, onSubmit, onCancel }: { pending: boolean; error?: string; onSubmit(question: string): void; onCancel(): void })`. Renders: a labelled textarea ("Вопрос по отчёту"), a live counter text `"{n} / 500"` where `n` is the trimmed length (uses `ASSISTANT_QUESTION_MAX`; counter has the error style when `n > 500`), example buttons "где отставание и на сколько" and "что с этой площадкой" (click **fills the field and focuses it**, does not send), a submit button "Спросить" and — while `pending` — a button "Отменить" calling `onCancel`. While `pending` the submit button is `disabled`, the textarea is `readOnly`. `error` is passed to the field's `error`.
  - Validation: on submit, `assistantQuestionSchema.safeParse(text)` fails → show "Вопрос должен быть от 3 до 500 символов" at the field and do **not** call `onSubmit`; otherwise call `onSubmit(parsed.data)` (trimmed). Keyboard: `Enter` (no shift, not `nativeEvent.isComposing`) → same as submit with `preventDefault`; `Shift+Enter` → default newline.

- [ ] **Step 1: Write the failing tests.** `TextAreaField.test.tsx`: label is associated with the textarea; hint shown and referenced by `aria-describedby`; error shown, `aria-invalid="true"`, error replaces hint. `AssistantQuestionForm.test.tsx` (user-event): typing then clicking "Спросить" calls `onSubmit` once with the trimmed text; `'  ab  '` → error text shown and `onSubmit` not called; 500 chars accepted, 501 → not called with the error; `Enter` submits (`onSubmit` once) and produces no newline in the value; `Shift+Enter` inserts a newline and does not submit; Enter during composition (`fireEvent.keyDown(textarea, {key:'Enter', isComposing:true})`) does not submit; counter shows `"3 / 500"` for `"  abc "` and the over-limit state for 501; clicking an example fills the textarea with exactly that text, focuses it and does not call `onSubmit`; `pending` → "Спросить" is disabled, "Отменить" is present and calls `onCancel`, the textarea is read-only, and `Enter` does not call `onSubmit`; when not pending there is no "Отменить"; `error` prop text is displayed.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** the primitive, its CSS and the form (CSS Module for the layout of counter/examples/actions; tokens only).
- [ ] **Step 4: Run** the new files, then the full checks.
- [ ] **Step 5: Commit.**
  ```bash
  git add frontend/src/components/ui/TextAreaField.tsx frontend/src/components/ui/TextAreaField.test.tsx frontend/src/components/ui/Field.module.css frontend/src/features/assistant/AssistantQuestionForm.tsx frontend/src/features/assistant/AssistantQuestionForm.module.css frontend/src/features/assistant/AssistantQuestionForm.test.tsx
  git commit -m "feat(frontend): поле TextAreaField и форма вопроса ассистенту (LCT-22)"
  ```

---

### Task 3: `AssistantAnswer`

**Files:**
- Create: `frontend/src/features/assistant/AssistantAnswer.tsx`, `frontend/src/features/assistant/AssistantAnswer.module.css`
- Test: `frontend/src/features/assistant/AssistantAnswer.test.tsx` (create)

**Interfaces:**
- Consumes: `linkifyAnswer`, `stageAnchorId` (Task 1); `AssistantAnswer` type (`@/api/schemas`); `Callout` (`tone="caution"`); `Icon`.
- Produces: `AssistantAnswerView({ answer }: { answer: AssistantAnswer })` (component name `AssistantAnswerView` to avoid clashing with the type; file `AssistantAnswer.tsx`). Renders inside a container with `tabIndex={-1}` and a `ref` forwarded by a prop `containerRef?: Ref<HTMLDivElement>` (the panel focuses it): (1) if `!answer.verified` a `Callout tone="caution"` titled "Ответ не прошёл проверку" with text "Сверьтесь с отчётом: эти числа в нём не найдены." plus two lists — "Чисел нет в отчёте: …" (`numbers_not_in_report`) and "Числа относятся к другой площадке: …" (`numbers_of_other_site`), each list shown only if non-empty; (2) the answer text as `linkifyAnswer` parts — `stage` parts as `<a href={'#' + stageAnchorId(stageId)}>` with the matched text, `text` parts as plain text, whitespace/newlines preserved (`white-space: pre-wrap`); (3) `answer.limits` as a paragraph `className="sm muted"` **in the page flow** under the answer (no `title`, no tooltip, no `aria-label`); (4) no verdict marker at all when `verified` (the absence of the alert is the "ok" state).

- [ ] **Step 1: Write the failing tests.** `verified:true` → no `alert` role, the `limits` text is in the document and its element (and no ancestor within the component) has neither `title` nor `aria-label`; `verified:false` with both lists → `getByRole('alert')` contains "Ответ не прошёл проверку" and "Сверьтесь с отчётом", the alert contains an svg icon (`[data-icon="alert"]`), lists show `999` and `p1: 5` with their captions; only one list non-empty → the other caption absent; answer "Этап 3 отстаёт, этап 4 нет, этап 99 нет." with stages for 3 and 4 → two links with `href="#stage-s3"` / `"#stage-s4"` and text "Этап 3" / "этап 4", and "этап 99" is not a link (`queryByRole('link', {name: /99/})` null); no `stages` → no links; injection `'<img src=x onerror=alert(1)> **жирный**'` → the literal string is present as text and `container.querySelector('img')` is null; `limits` is rendered even when `answer.limits` is empty string? — no: an empty `limits` renders no paragraph (assert absent).
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** the component and its CSS Module (tokens only; `overflow-wrap: anywhere` for long text).
- [ ] **Step 4: Run** the file, then the full checks.
- [ ] **Step 5: Commit.**
  ```bash
  git add frontend/src/features/assistant/AssistantAnswer.tsx frontend/src/features/assistant/AssistantAnswer.module.css frontend/src/features/assistant/AssistantAnswer.test.tsx
  git commit -m "feat(frontend): ответ ассистента — пометка проверки, limits, ссылки на этапы (LCT-22)"
  ```

---

### Task 4: `AssistantPanel`, integration, page tests, docs

**Files:**
- Create: `frontend/src/features/assistant/AssistantPanel.tsx`, `frontend/src/features/assistant/AssistantPanel.module.css`, `frontend/src/features/assistant/AssistantPanel.test.tsx`
- Modify: `frontend/src/pages/SiteOverviewPage.tsx` (mount after `LastObservation`), `frontend/src/pages/SiteOverviewPage.test.tsx` (page-level cases), `docs/architecture-frontend.md` (§2 features list, §3 note on the panel, §8 nothing)

**Interfaces:**
- Consumes: `useAssistantStatus`, `useAskAssistant`, `AssistantFailure`, `AssistantFailureKind` (`@/api/assistant`); `AssistantQuestionForm` (T2); `AssistantAnswerView` (T3); `SectionHeader`, `Callout`, `Button`.
- Produces: `AssistantPanel({ siteId }: { siteId: string })`. Two-level structure: `AssistantPanel` calls `useAssistantStatus()` and returns `null` unless `enabled`; the inner section calls `useAskAssistant(siteId)` and additionally returns `null` when `failure?.kind === 'unavailable'`. The section: `<section aria-labelledby>` with `SectionHeader` title "Ассистент по отчёту" and a one-line description that it retells the report and that the source is the report itself; the form; a status line while pending (`role="status"`, "Ассистент отвечает. Это может занять до двух минут."); an `aria-live="polite"` region that is **always rendered** and holds the answer view or the failure; the last question in `useRef`/`useState` (memory only) for retry. Failure rendering by `kind`: `cancelled` → nothing; `invalid_question` → not in the region but passed as the form's `error`; `timeout` → `Callout tone="caution"` with the server text and a "Повторить" button (re-asks the last question); `rate_limited`, `out_of_scope`, `too_large`, `not_found`, `bad_request`, `unknown` → `Callout tone="caution"` with `failure.message`, no retry. After a new `answer` appears, focus its container. CSS: the section has `@media print { display: none }`.

- [ ] **Step 1: Write the failing tests** (`AssistantPanel.test.tsx` with `renderWithProviders`; mock scenarios via `db.setAssistantScenario`; the demo site `BEREZNIKI`; a request counter via `server.use`):
  - Hidden: first render (status pending) → no heading "Ассистент по отчёту", no textbox; after status resolves with `no_llm` and `unavailable` → still nothing; the container element is empty (`container` has no children from the panel); `console.error` not called.
  - Enabled: heading and textbox appear after status resolves.
  - Success flow: type a question, click "Спросить" → the status line appears, then the answer text; `limits` visible; the answer container has focus; the stage link (`href` starts with `#stage-`) exists for the demo (the mock names the first stage that is `behind`).
  - Unverified scenario → alert "Ответ не прошёл проверку" with `999` and `p1: 5`.
  - `verified` scenario → `queryByRole('alert')` is null.
  - Pending: the submit button is disabled while waiting (gate handler that releases on command); a second click and `Enter` produce exactly one request; "Отменить" aborts (request aborted flag set), the status line disappears and no error text is shown, the form is usable again.
  - Errors: `timeout` → alert text "Модель не ответила. Повторите вопрос позже." and button "Повторить"; after `setAssistantScenario('ok')` clicking "Повторить" sends the **same question** (assert request body) and the error is replaced by the answer; `rate_limited`, `out_of_scope`, `too_large` → server text shown, **no** "Повторить"; `unavailable` on the question → the whole section disappears; a too-short question → inline error, zero requests.
  - Ephemeral: after an answer `localStorage.length === 0` and `sessionStorage.length === 0`; the CSS module text (`import css from './AssistantPanel.module.css?raw'`) contains `@media print` and `display: none`.
  - Page (`SiteOverviewPage.test.tsx`, `renderRoute('/sites/site-berezniki')`): with `no_llm` the page has no "Ассистент по отчёту" heading (looks as before); with the default scenario, after the status resolves the heading exists and comes **after** the heading "Последнее наблюдение · …" in document order (`compareDocumentPosition`); asking "где отставание и на сколько" shows an answer whose stage link `href` equals `#stage-` + the id of a row in the stage table (find the row by `document.getElementById` from the link's hash and assert it is inside the table named "Статусы этапов"); `limits` text is visible.
- [ ] **Step 2: Run to verify they fail.**
- [ ] **Step 3: Implement** the panel, CSS Module, and the one-line mount in `SiteOverviewPage.tsx` (inside `SiteShell`, after `<LastObservation …/>`).
- [ ] **Step 4: Docs** — `docs/architecture-frontend.md`: add `assistant` to the `features/` list in §2 and one paragraph in §3 (where the panel lives, that it is hidden without LLM, printing, the link-to-stage anchors).
- [ ] **Step 5: Run** the new/changed test files, then full checks (`tsc`, `eslint`, `prettier --check src`, full vitest with coverage; report `All files` line and the per-file lines for the new files). Verify by hand that every Review Focus item is pinned by a named test.
- [ ] **Step 6: Commit.**
  ```bash
  git add frontend/src/features/assistant/AssistantPanel.tsx frontend/src/features/assistant/AssistantPanel.module.css frontend/src/features/assistant/AssistantPanel.test.tsx frontend/src/pages/SiteOverviewPage.tsx frontend/src/pages/SiteOverviewPage.test.tsx docs/architecture-frontend.md
  git commit -m "feat(frontend): панель ассистента на экране объекта (LCT-22)"
  ```

---

## Self-Review

- **Issue coverage:** hidden when unavailable, incl. 503 on a question (T4); `verified:false` alert with both lists, icon + text (T3); `limits` in the flow, not from a constant (T3); links to stages, unknown → text, deterministic parse (T1, T3); waiting indicator, disabled button, cancel, error mapping incl. retry on timeout (T4); read-only, no storage, print hidden (T4); question field with counter, validation, Enter/Shift+Enter, examples, current-site context (T2, T4); a11y `aria-live`, focus after answer, keyboard (T2, T4); tests through `renderRoute` (T4); coverage held (every task). **Deviations, stated up front:** panel at the page bottom; site label not linked; a small `TextAreaField` primitive; no copy button.
- **Type consistency:** `stageAnchorId` is the single source for row `id` and link `href`; `AssistantFailureKind` values used in the panel are exactly those of `api/assistant.ts`; the form emits the trimmed value the hook re-validates.
- **Known limits:** `:target` styling relies on native fragment navigation (jsdom does not scroll — tests check `href`/`id`, the visual highlight and scroll need a manual check); focus-on-answer is asserted in jsdom only; the answer text is only as linked as the model's "этап N" wording; without the `stages` array from the backend there are no links.
- **Follow-ups (not built):** real authentication (LCT-20 note), multi-site labels, a copy button.
- **Proportion:** four tasks — pure parsing + anchors, input form, answer view, panel + integration.
