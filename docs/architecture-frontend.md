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
  schemas.ts          Zod-схемы и типы (перечисления DataModel §5.7)
  keys.ts             ключи TanStack Query
  sites.ts … deviations.ts   функции API + хуки useX / useXMutation по доменам
components/ui/        дизайн-система LCT-7: Button, Segmented, TextField, SelectField, Pill,
                      StatusBadge, ConfidenceMeter, DateSourceBadge, Callout, Card, Dialog,
                      Breadcrumbs, Stepper, FrameView, FileDrop, QueryState, Icon
components/layout/    AppLayout (шапка), PageHeader/SectionHeader, SiteShell (вкладки объекта)
features/<домен>/     составные компоненты экранов: sites, new-site, methodology, overview,
                      observations, cameras, deviations
pages/                по странице на экран макета, собирают features
lib/                  env, форматирование дат, подписи перечислений, сортировка отклонений
mocks/                fixtures.ts (демо «Березники»), db.ts (in-memory бэкенд), handlers.ts
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
| 4, 4а · Камеры | `/sites/:id/cameras` | `CamerasPage` + `CameraDialog` | UC-6 |
| 5 · Обзор | `/sites/:id` | `SiteOverviewPage` | UC-4 |
| 6 · Наблюдения | `/sites/:id/observations?date=` | `ObservationsPage` + `AddFramesDialog` | UC-7, UC-3, UC-8 |
| 7, 7а · Отклонение | `/sites/:id/deviations/:deviationId` | `DeviationPage` + `DecisionPanel` | UC-5, UC-10 |

Черновик стройки (`state = draft`) создаётся при первой загрузке графика, после чего URL
становится `/sites/:id/setup`: шаг 1 можно открыть заново, «Далее» сохраняет поля объекта.
«Создать стройку» на шаге 2 вызывает `POST /sites/:id/activate`; блокирующие проблемы импорта
сервер возвращает 409, текст показывается на странице.

## 4. Контракт API

Базовый путь — `VITE_API_BASE_URL` (по умолчанию `/api`). Поля в snake_case, как отдаёт Pydantic.
Полные формы — `src/api/schemas.ts`. Эндпоинты, которые использует фронт:

| Метод и путь | Назначение |
|---|---|
| `GET /users/me` | стендовый пользователь (подпись решений) — **есть в backend** |
| `GET/POST /sites`, `GET/PATCH /sites/{id}` | стройки; в ответе `object_type`, `work_days`, `state`, `summary` — **CRUD есть, доп. поля — нет** |
| `POST /sites/{id}/activate` | черновик → активная стройка, 409 при блокирующих проблемах |
| `GET /sites/{id}/schedule-imports/current`, `POST /sites/{id}/schedule-imports` (multipart `file`) | импорт графика со статистикой и `issues` |
| `GET /sites/{id}/stages`, `PATCH /sites/{id}/stages/{stageId}` | крупные этапы: ручные даты, подтверждение сопоставления |
| `GET /sites/{id}/methodology`, `PUT /sites/{id}/methodology/{stageId}` | комплект этапа; маркеры вычисляет сервер |
| `GET /equipment-classes` | справочник классов техники |
| `GET/POST /sites/{id}/cameras`, `PATCH /cameras/{id}` | камеры, `zone_polygon` в долях кадра |
| `POST /reference-frames` `{stream_url}` | один опорный кадр со стрима (не сохраняется) |
| `GET /sites/{id}/observations`, `GET /sites/{id}/observations/{date}` | дни наблюдений; техника за дату |
| `GET /sites/{id}/frames?date=` | кадры с детекциями (без `date` — все) |
| `GET /sites/{id}/frames/needs-review`, `PATCH /frames/{id}`, `PATCH /ingests/{id}` | кадры без времени, подтверждение времени и старта клипа |
| `POST /sites/{id}/ingests` (multipart), `GET /sites/{id}/ingests?source_type=stream`, `POST /ingests/{id}/stop` | загрузка фото/видео, стримы |
| `GET /sites/{id}/stage-statuses` | таблица этапов обзора |
| `GET /deviations`, `GET /sites/{id}/deviations`, `GET /deviations/{id}` | отклонения: сквозной список, по стройке, карточка |
| `POST/DELETE /deviations/{id}/decision` | решение по гипотезе и «Изменить решение» |

Сейчас backend реализует только `/users/me` и CRUD `/sites`. Схемы фронта объявляют новые поля
стройки с `default`, поэтому экран «Стройки» работает и с текущим backend (итог — «Недостаточно
данных»). Остальные эндпоинты — предложение контракта для бэкенда; при расхождении правится
`schemas.ts`, а Zod-ошибка контракта сразу видна на экране.

Инвалидация кэша: ключи строятся как `['site', id, …]`. Любая правка входа (методика, камера,
время кадра, новые кадры) сбрасывает `['site', id]` целиком — это повторяет серверное правило
«правка входа → пересчёт всех выводов стройки».

## 5. Моки и переключение на реальный API

- `VITE_USE_MOCKS=true` — `main.tsx` до первого рендера запускает MSW service worker
  (`public/mockServiceWorker.js`), и все запросы к `/api/*` обслуживает `src/mocks/handlers.ts`.
  В шапке виден бейдж «Моки».
- `VITE_USE_MOCKS=false` — MSW не загружается вовсе (в прод-сборку код моков не попадает
  благодаря dead-code elimination), запросы идут в backend через Traefik или прокси Vite.

Где задаётся флаг: `frontend/.env.development` (по умолчанию `true`), `.env` в корне для `make dev`
(`VITE_USE_MOCKS`), разово — `pnpm dev:mocks` / `pnpm dev:api`. Прод-образ собирается без флага.

Моки — это не статичные JSON, а маленький in-memory бэкенд (`mocks/db.ts`): создание стройки,
разбор графика с проблемами как в макете, пересчёт маркеров методики, подтверждение времени,
решения по гипотезам. Благодаря этому все сценарии UC-1…UC-10 проходятся в браузере без backend.
Чтобы подключить реальный эндпоинт, код экранов не меняется: достаточно выключить флаг.

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

- «Изменить состав» крупного этапа (перенос работы между этапами, объединение соседних) — нужен
  эндпоинт перегруппировки; на экране пока только ручные даты и подтверждение сопоставления.
- Печатная версия обзора (P2) — сейчас `window.print()` без отдельной печатной вёрстки.
- Реальные изображения кадров: `image_url` поддержан, моки отдают заглушку-«снимок».
- Адаптив под узкие экраны — базовый (макет десктопный, 1440 px).
