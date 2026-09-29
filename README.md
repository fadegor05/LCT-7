# LCT-7

| Часть | Каталог | Стек |
|---|---|---|
| Интерфейс | [frontend/](frontend/) | React 19, Vite, TypeScript, TanStack Query, Zod |
| Бэкенд | [backend/](backend/) | FastAPI, Dishka, Granian, SQLAlchemy, Alembic, PostgreSQL 16 |
| Распознавание и ассистент | [ml/](ml/) | FastAPI, YOLO26-m, внешняя языковая модель |
| Развёртывание | [deploy/](deploy/) | Docker Compose, Traefik |

## Запуск

Только интерфейс на демонстрационных данных (нужен Node.js):

```bash
cd frontend && pnpm install && pnpm dev    # http://localhost:5173
```

Весь стек (нужны Docker и Make):

```bash
cp .env.dist .env    # в .env: VITE_USE_MOCKS=false
make dev             # интерфейс http://localhost, API http://localhost/api/docs
```

Для распознавания техники нужны веса из закрытого репозитория Hugging Face:

```bash
export HF_TOKEN=<токен>
make ml-weights && make dev-ml
```

Без весов оставьте `DETECTOR__URL` в `.env` пустым. Для демонстрации на старых снимках задайте `ASSESSMENT__AS_OF_MODE=last_observation`. Подробности в [documentation/install-and-run.md](documentation/install-and-run.md).

## Команды

| Команда | Что делает |
|---|---|
| `make dev`, `make dev-ml` | Локальный запуск без ML и с ML |
| `make ml-weights` | Загрузить веса детектора |
| `make deploy`, `make deploy-tunnel` | Прод: образы из реестра, с TLS на хосте и за туннелем |
| `make down`, `make logs` | Остановка и журналы |
| `make check`, `make pretty`, `make test` | Бэкенд: ruff, форматирование, pytest |
| `make front-check`, `make front-pretty`, `make front-test` | Фронтенд: проверки, форматирование, тесты |

## Документация

| Файл | О чём |
|---|---|
| [architecture.md](documentation/architecture.md) | Контейнеры, потоки данных, слои бэкенда |
| [data-model.md](documentation/data-model.md) | Схема БД, ограничения, миграции |
| [api.md](documentation/api.md) | Эндпоинты бэкенда |
| [business-logic.md](documentation/business-logic.md) | Как считаются даты, наблюдения, статусы и отклонения |
| [install-and-run.md](documentation/install-and-run.md) | Сборка, установка и запуск |
| [configuration.md](documentation/configuration.md) | Переменные окружения |
| [limitations.md](documentation/limitations.md) | Условия и ограничения |

## Лицензия

[AGPL-3.0](LICENSE): модели Ultralytics распространяются под AGPL-3.0, включая обученные веса (см. [ml/DECISIONS.md](ml/DECISIONS.md), D-001).
