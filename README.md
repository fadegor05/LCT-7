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
│   └── app/
│       ├── main.py           # сборка приложения (аналог Application.kt)
│       ├── core/             # settings, database (Base), security
│       ├── plugins/          # di (Dishka), exceptions, routing
│       ├── clients/          # внешние клиенты (позже ML)
│       └── modules/<домен>/  # per-domain: models / schemas / repository /
│                             #   service / provider (DI) / router
├── frontend/                # React + Vite (single-page), nginx в prod
│   ├── Dockerfile
│   ├── nginx.conf
│   └── src/
└── deploy/
    ├── versions.env         # REGISTRY + теги образов
    ├── docker/
    │   ├── common/{core,infra}.yaml   # сервисы + Traefik-лейблы + postgres/traefik
    │   ├── dev/core.yaml              # локальный билд, bind-mount, hot-reload
    │   └── prod/core.yaml             # TLS, mem_limit, готовые образы
    └── config/traefik/traefik.yml
```

Бэкенд повторяет раскладку Kotlin-версии: `core` (инфраструктура), `plugins`
(сквозные вещи — DI/ошибки/роутинг), `modules/<домен>` (по модулю на доменную
область), `clients` (внешние интеграции).

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
  примонтированы;
- Traefik разводит трафик по одному хосту: `/api` → backend (priority 20),
  всё остальное → frontend (priority 1).

`make deploy` использует `prod/core.yaml` (TLS + готовые образы по тегам из
`deploy/versions.env`) и не билдит, только `pull` + `up`.

## Бэкенд: Dishka + Granian

- **Granian** — ASGI-сервер: `granian --interface asgi app.main:app`.
- **Dishka** — DI-контейнер (`app/plugins/di.py`). Инфраструктура (`Settings`,
  `AsyncEngine`, `AsyncSession`) в scope APP/REQUEST; доменные провайдеры — в
  своих модулях (`modules/<домен>/provider.py`). В роутах зависимости
  подставляются через `FromDishka[...]` + `@inject`.
- Таблицы создаются на старте (`Base.metadata.create_all`) — для реального
  проекта заменить на Alembic.

Локальный запуск без Docker:

```bash
cd backend
uv sync
granian --interface asgi app.main:app --reload   # нужен доступный PostgreSQL
```
```
