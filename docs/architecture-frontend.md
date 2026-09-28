# Архитектура фронтенда

Источники: `architecture.md` (требования UC-1…UC-10, словари §7, правила вывода §8), `DataModel.md`
(сущности и перечисления §5), макет «ЛЦТ — MVP: экраны» с дизайн-системой LCT-7.

## 1. Стек

| Задача | Решение | Почему |
|---|---|---|
| UI | React 19 + TypeScript (strict, `noUncheckedIndexedAccess`) | стандарт команды |
| Сборка | Vite 6 | уже в репо, dev-сервер за Traefik |
| Роутинг | React Router 7 (`createBrowserRouter`) | самый распространённый |
| Серверное состояние | TanStack Query 5 | кэш, инвалидация по стройке, состояния загрузки |
| Контракты | Zod 4 | ответ API проверяется схемой, типы выводятся из неё же |
| Формы | react-hook-form + `@hookform/resolvers/zod` | форма «Объект» на шаге 1 |
| Стили | CSS Modules + CSS-переменные из токенов LCT-7 | без runtime, 1:1 с макетом |
| Моки | MSW 2 | перехват `fetch` на сетевом уровне, одни хендлеры для браузера и тестов |
| Тесты | Vitest 5 + Testing Library + jsdom, покрытие v8 | нативно для Vite |
| Линтеры | ESLint 9 (typescript-eslint type-checked, react-hooks, jsx-a11y, TanStack Query, testing-library, vitest), Stylelint, Prettier | |

Глобального стора нет: всё серверное — в TanStack Query, локальное — `useState` в компонентах,
фильтр дня на «Наблюдениях» — в URL (`?date=`).

## 2. Структура `frontend/src`

```
main.tsx              точка входа; при VITE_USE_MOCKS=true сначала поднимает MSW
app/                  App (QueryClient + Router), routes.tsx, queryClient.ts
api/                  контракты и доступ к API
  client.ts           request(): fetch + разбор ошибок FastAPI + проверка Zod-схемой
  schemas.ts          Zod-схемы и типы — копия Pydantic-схем backend (app/domains/*/schemas.py)
  keys.ts             ключи TanStack Query
  sites.ts, schedule.ts, methodology.ts   функции API + хуки по доменам backend
  frames.ts           снимки (photo) и наблюдения (observation)
  deviations.ts       выводы (assessment): статусы этапов, отклонения, итог
  assistant.ts        ассистент: классификация ошибок по коду backend, useAssistantStatus, useAskAssistant
components/ui/        дизайн-система LCT-7: Button, Segmented, TextField, SelectField, Pill,
                      StatusBadge, ConfidenceMeter, DateSourceBadge, Callout, Card, Dialog,
                      Breadcrumbs, Stepper, FrameView, FileDrop, QueryState, Icon
components/layout/    AppLayout (шапка), PageHeader/SectionHeader, SiteShell (вкладки объекта)
features/<домен>/     составные компоненты экранов: assistant, sites, new-site, methodology,
                      overview, observations, deviations
pages/                по странице на экран макета, собирают features
lib/                  env, форматирование дат, подписи перечислений, сортировка отклонений
mocks/                fixtures.ts (демо «Березники»), db.ts (in-memory бэкенд с правилами backend), handlers.ts
styles/               tokens.css (токены LCT-7), global.css
test/                 setup.ts (MSW server + reset db), render.tsx (renderRoute / renderWithProviders)
```

Правило зависимостей: `pages → features → components/ui, api, lib`. `components/ui` не знает про API
и домены (кроме типов перечислений). Тесты лежат рядом с кодом (`*.test.tsx`).

## 3. Экраны и маршруты

| Макет | Маршрут | Страница | UC |
|---|---|---|---|
| 1 · Стройки | `/sites` | `SitesPage` | UC-9 |
| 2 · Новая стройка | `/sites/new`, `/sites/:id/setup` | `NewSitePage` | UC-1 |
| 3 · Методика (шаг 2) | `/sites/:id/setup/methodology` | `NewSiteMethodologyPage` | UC-2 |
| 3а · Методика объекта | `/sites/:id/methodology` | `MethodologyPage` | UC-2 |
| 5 · Обзор | `/sites/:id` | `SiteOverviewPage` | UC-4 |
| 6 · Наблюдения | `/sites/:id/observations?date=` | `ObservationsPage` + `AddFramesDialog` | UC-7, UC-3, UC-8 |
| 7 · Отклонение | `/sites/:id/deviations/:deviationId` | `DeviationPage` | UC-5 |

Стройка создаётся при первой загрузке графика (черновика в backend нет), после чего URL
становится `/sites/:id/setup`: шаг 1 можно открыть заново, «Далее» сохраняет название и адрес.
Шаг 2 правит методику уже созданной стройки; «Готово» ведёт на обзор.

Экраны макета без поддержки в backend не подключены: 4 «Камеры» (в backend нет камер и зон),
7а «Решение по гипотезе» (нет эндпоинтов решений), стримы и видео (backend принимает только фото).

**Ассистент на обзоре.** На экране 5 · Обзор внизу (после «Последнего наблюдения») появляется
панель ассистента, если LLM настроена. Панель скрыта без LLM и при печати. Ссылки в ответе
вида «этап N» перенаправляют на якоря строк таблицы «Статусы этапов» через `#stage-<id>`.
Ответы эфемерны и хранятся только в состоянии компонента (не в хранилище браузера).

## 4. Контракт API

Базовый путь — `VITE_API_BASE_URL` (по умолчанию `/api`). Поля в snake_case, как отдаёт Pydantic.
`src/api/schemas.ts` повторяет Pydantic-схемы backend один в один (ключи и nullable сверены с
OpenAPI backend), перечисления — StrEnum из `models.py` доменов. Эндпоинты, которые использует фронт:

| Метод и путь | Назначение |
|---|---|
| `GET /users/me` | стендовый пользователь |
| `GET/POST /sites`, `GET/PATCH /sites/{id}` | стройки: `name`, `address` |
| `GET /sites/{id}/schedule` (404 — графика нет), `POST /sites/{id}/schedule/import` (multipart `file`) | отчёт импорта: счётчики строк, этапы, `issues` |
| `PATCH /sites/{id}/schedule/stages/{stageId}` | ручные даты этапа (`dates_source = manual`) |
| `GET /equipment-types` | справочник техники |
| `GET /sites/{id}/methodology` | правила этапов с комплектами; сервер лениво создаёт их из базового набора |
| `PATCH /sites/{id}/methodology/rules/{ruleId}` | проверяется ли этап по технике и почему нет |
| `POST /sites/{id}/methodology/rules/{ruleId}/sets`, `PUT/DELETE /sites/{id}/methodology/sets/{setId}` | комплекты техники; без нормативной техники — 422 |
| `GET /sites/{id}/photos` (`?undated=true`), `POST /sites/{id}/photos` (multipart `files`) | снимки и загрузка пачки (`UploadReport` по каждому файлу) |
| `PATCH /sites/{id}/photos/{photoId}/date`, `POST /sites/{id}/photos/{photoId}/detect` | ручная дата снимка, повторная детекция |
| `GET /sites/{id}/photos/{photoId}/annotated` | снимок с рамками техники (PNG рисует сервер) |
| `GET /sites/{id}/observations`, `GET /sites/{id}/observations/{date}` | наблюдения по датам и техника за дату |
| `GET /sites/{id}/assessment/stages` (404 — графика нет) | статусы этапов; `status = null` — этап ещё не оценивался |
| `GET /sites/{id}/assessment/deviations`, `GET /sites/{id}/assessment/deviations/{id}` | отклонения стройки, карточка с доказательствами |
| `GET /sites/{id}/assessment/summary` | итог по объекту |
| `GET /assistant/status` | статус ассистента (`enabled: boolean`) |
| `POST /sites/{id}/assistant/ask` (body `{question}`, 3–500 символов после trim) | вопрос; ответ `{answer, verified, numbers_not_in_report, numbers_of_other_site, limits, site_label, stages}`. Ошибки отмечены кодом: `assistant_unavailable`, `assistant_timeout`, `rate_limited`, `out_of_scope`, `report_too_large`, `assistant_bad_request` |

Чего backend не отдаёт и что фронт собирает сам: итог и последнее наблюдение в списке строек —
отдельными запросами по каждой стройке; сквозной список отклонений — объединением списков строек;
заголовок отклонения — из типа и названия этапа; плановое окно в таблице статусов — из графика.

Инвалидация кэша: ключи строятся как `['site', id, …]`. Любая правка входа (график, методика,
дата снимка, новые снимки) сбрасывает `['site', id]` целиком — это повторяет серверное правило
«правка входа → пересчёт всех выводов стройки».

## 5. Моки и переключение на реальный API

- `VITE_USE_MOCKS=true` — `main.tsx` до первого рендера запускает MSW service worker
  (`public/mockServiceWorker.js`), и все запросы к `/api/*` обслуживает `src/mocks/handlers.ts`.
  В шапке виден бейдж «Моки».
- `VITE_USE_MOCKS=false` — MSW не загружается вовсе (в прод-сборку код моков не попадает
  благодаря dead-code elimination), запросы идут в backend через Traefik или прокси Vite.

Где задаётся флаг: `frontend/.env.development` (по умолчанию `true`), `.env` в корне для `make dev`
(`VITE_USE_MOCKS`), разово — `pnpm dev:mocks` / `pnpm dev:api`. Прод-образ собирается без флага.

Моки — это не статичные JSON, а маленький in-memory бэкенд (`mocks/db.ts`) с правилами backend:
404 для чужой стройки и отсутствующего графика, ленивое создание правил методики, валидация
комплектов (422), пересчёт наблюдений по снимкам (максимум по снимкам), ручная дата не в будущем.
Статусы этапов и отклонения демо-стройки — готовые выводы движка; у новых строек их нет.
Чтобы подключить реальный эндпоинт, код экранов не меняется: достаточно выключить флаг.

Сценарии ассистента для тестирования ошибок: в коде вызовите `setAssistantScenario()`, в браузере —
параметр `?assistant=<имя>` (сценарии: `ok`, `unverified`, `unavailable`, `timeout`, `rate_limited`,
`out_of_scope`, `too_large`, `no_llm`, `slow`, `unlinked`). `resetDb()` восстанавливает сценарий `ok`.

## 6. Тесты

- Vitest + Testing Library, окружение jsdom. MSW-сервер (`msw/node`) поднимается в `test/setup.ts`
  с теми же хендлерами, что и в браузере; перед каждым тестом `resetDb()`.
- Уровни: чистые функции (`lib/*.test.ts`, `api/client.test.ts`), каждый компонент дизайн-системы
  (`components/ui/*.test.tsx`), составные компоненты (`features/features.test.tsx`), страницы —
  интеграционно через `renderRoute(url)` поверх всего роутера и моков (`pages/*.test.tsx`),
  включая сквозное создание стройки.
- Пороги покрытия в `vite.config.ts`: statements 90, branches 85, functions 90, lines 90. CI падает
  при просадке. Текущее покрытие ≈ 98 % statements, 92 % branches.
- jsdom закреплён на v27: вспомогательный код Vitest 5 для multipart читает внутреннее поле jsdom,
  которого в v30 нет. Обновлять вместе с Vitest.

## 7. Линтеры и форматирование

| Команда | Что делает |
|---|---|
| `pnpm lint` / `lint:fix` | ESLint (`--max-warnings=0`) + Stylelint |
| `pnpm format` / `format:check` | Prettier |
| `pnpm typecheck` | `tsc -b` |
| `pnpm test` / `test:coverage` | Vitest |
| `pnpm check` | всё сразу, как в CI |
| `make front-check` / `front-pretty` / `front-test` | то же из корня репозитория |

## 8. Что не сделано и следующие шаги

- Камеры и рабочие зоны, видео и стримы, решения по гипотезам — ждут эндпоинтов в backend.
- Список строек делает по два запроса на стройку (итог и наблюдения): при росте числа строек
  нужен агрегирующий эндпоинт.
- Печатная версия обзора (P2) — сейчас `window.print()` без отдельной печатной вёрстки.
- Адаптив под узкие экраны — базовый (макет десктопный, 1440 px).
