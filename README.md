# LCT-7

Монорепо: один фронтенд (React + Vite) и бэкенд на **FastAPI + Dishka + Granian**.
Оркестрация — Docker Compose со слоями `common` / `dev` / `prod`, маршрутизация — Traefik.

## Структура

```
LCT-7/
├── makefile                 # точка входа: make dev / up / deploy / down / logs
├── .env / .env.dist         # переменные окружения (.dist — образец)
├── backend/                 # FastAPI + Dishka + Granian
│   ├── Dockerfile
│   ├── pyproject.toml        # зависимости (uv), package = false
│   ├── alembic.ini           # конфиг Alembic
│   ├── migrations/           # миграции Alembic
│   └── app/
│       ├── main.py           # сборка приложения (аналог Application.kt)
│       ├── core/             # settings, database (Base), repository, security
│       ├── plugins/          # di (Dishka), exceptions, routing
│       ├── adapters/         # внешние системы (позже ML)
│       ├── models.py         # единая точка импорта ORM-моделей для Alembic
│       └── domains/<домен>/  # per-domain: models / schemas / repository /
│                             #   service / provider (DI) / router
├── frontend/                # React + Vite (single-page), nginx в prod
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
├── deploy/
│   ├── README.md            # схема деплоя, туннель, включение CD
│   ├── versions.env         # REGISTRY + теги образов
│   ├── docker/
│   │   ├── common/{core,infra}.yaml   # сервисы + Traefik-лейблы + postgres/traefik
│   │   ├── dev/core.yaml              # локальный билд, bind-mount, hot-reload
│   │   ├── prod/core.yaml             # TLS на хосте, mem_limit, готовые образы
│   │   └── prod/tunnel.yaml           # прод за туннелем: TLS терминирует туннель
│   └── config/traefik/traefik.yml
└── .github/workflows/       # ci.yml (проверки) + cd.yml (шаблон деплоя)
```

Бэкенд повторяет раскладку Kotlin-версии: `core` (инфраструктура), `plugins`
(сквозные вещи — DI/ошибки/роутинг), `domains/<домен>` (по каталогу на доменную
область), `adapters` (внешние интеграции). `core`, `plugins` и `adapters`
доменами не являются — подробнее в [docs/architecture.md](docs/architecture.md) §6.

## Быстрый старт

```bash
cp .env.dist .env    # при необходимости поправить
make dev
```

- http://localhost — фронтенд
- http://localhost/api/health — healthcheck бэкенда
- http://localhost/api/docs — Swagger UI
- http://localhost:8080 — дашборд Traefik

## Как работает `make dev`

Compose-файлы наслаиваются. Базовый набор (`COMPOSE` в makefile):

```
common/core.yaml   # сервисы backend + frontend, их образы и Traefik-лейблы
common/infra.yaml  # postgres + traefik
```

`make dev` добавляет `dev/core.yaml`, который переопределяет сервисы под разработку:
- `backend`: билдится локально (`target: build`), исходники монтируются в `/app`,
  Granian запускается с `--reload`;
- `frontend`: вместо nginx крутится Vite dev-server на порту 5173, исходники
  примонтированы; по умолчанию экраны работают на MSW-моках
  (`VITE_USE_MOCKS=true` в `.env`), для реального API — `VITE_USE_MOCKS=false`.
  Подробно — [docs/architecture-frontend.md](docs/architecture-frontend.md);
- Traefik разводит трафик по одному хосту: `/api` → backend (priority 20),
  всё остальное → frontend (priority 1).

`make deploy` использует `prod/core.yaml` (TLS + готовые образы по тегам из
`deploy/versions.env`) и не билдит, только `pull` + `up`. `make deploy-tunnel` —
то же самое для хоста за туннелем, где TLS терминируется снаружи.

## CI/CD

**CI** (`.github/workflows/ci.yml`) — на каждый PR и push в `main`:

| Job | Что делает |
|---|---|
| `backend · ruff` | `make check` — линт + проверка формата |
| `backend · mypy` | типы; пока информативно, CI не красит |
| `backend · миграции + /api/health` | postgres в сервис-контейнере, `alembic upgrade head`, поднимает Granian и дёргает healthcheck |
| `frontend · lint + test + build` | ESLint + Stylelint, Prettier, Vitest с порогами покрытия, `pnpm build` |
| `ml · синтаксис скриптов` | `compileall` по `ml/tools` — без установки torch |
| `deploy · валидация compose-слоёв` | `docker compose config` по dev / prod / tunnel |
| `docker · backend/frontend` | сборка образов (без публикации) |

**CD** (`.github/workflows/cd.yml`) — пока шаблон: автотриггеров нет, деплой
отключён переменной `DEPLOY_ENABLED`. Работающая часть — сборка и публикация
образов в GHCR по ручному запуску. Как включить деплой на `xxprod.ru` —
в [deploy/README.md](deploy/README.md).

## Бэкенд: Dishka + Granian

- **Granian** — ASGI-сервер: `granian --interface asgi app.main:app`.
- **Dishka** — DI-контейнер (`app/plugins/di.py`). Инфраструктура (`Settings`,
  `AsyncEngine`, `AsyncSession`) в scope APP/REQUEST; доменные провайдеры — в
  своих доменах (`domains/<домен>/provider.py`). В роутах зависимости
  подставляются через `FromDishka[...]` + `@inject`.
- Схема применяется миграциями: `alembic upgrade head` выполняется перед
  стартом сервера (см. `backend/app/main.py`, `deploy/docker/dev/core.yaml`).

Локальный запуск без Docker:

```bash
cd backend
uv sync
granian --interface asgi app.main:app --reload   # нужен доступный PostgreSQL
```
```

## Лицензия

[AGPL-3.0](LICENSE). Выбрана из-за ML-части: модели Ultralytics (YOLOE, YOLO26)
распространяются под AGPL-3.0, включая обученные веса. Закрытое внедрение с этими
моделями потребует коммерческой лицензии Ultralytics. Обоснование — `ml/DECISIONS.md`, D-001.
