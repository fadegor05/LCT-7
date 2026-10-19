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

## Языковая модель

Ассистент по отчёту и разбор нестандартных графиков используют языковую модель. Подойдёт любой провайдер с API, совместимым с форматом chat completions (OpenAI), облачный или локальный. Настраивается тремя переменными в `.env`:

```dotenv
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=<ключ>
LLM_MODEL=<имя модели>
```

Пока любая из трёх пуста, ассистент и разбор графика моделью отключены, остальные функции работают.

## Вход и переменные окружения

Доступ к API по логину и паролю (JWT). Переменные задаются в `.env`; в `.env.dist` их нет, значения по умолчанию рабочие для разработки:

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `AUTH__SECRET_KEY` | `dev-insecure-change-me` | Ключ подписи токенов. При `SECURE=true` с этим значением бэкенд не стартует: в проде задайте свой |
| `AUTH__TOKEN_TTL_MINUTES` | `720` | Срок жизни токена, минуты |
| `AUTH__LOGIN_RATE_LIMIT_PER_MIN` | `10` | Попыток входа в минуту на логин |
| `AUTH__REGISTER_RATE_LIMIT_PER_MIN` | `5` | Регистраций в минуту с одного адреса |
| `AUTH__SEED_LOGIN`, `AUTH__SEED_PASSWORD` | не заданы | Логин и пароль стендового пользователя, создаются при старте |

Новые возможности выключены по умолчанию:

| Переменная | Назначение |
|---|---|
| `STREAM__ENABLED=false` | Выключить снимки со стрима по расписанию (включены по умолчанию). Камеры в локальной сети требуют `STREAM__ALLOWED_NETWORKS`; остальные `STREAM__*` в [documentation/configuration.md](documentation/configuration.md) |
| `STAMP_CAMERA_READER=0` | Выключить чтение штампа камеры по эталонам (сервис `ml`, включено по умолчанию) |

Полный список переменных: [documentation/configuration.md](documentation/configuration.md).

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

[AGPL-3.0](LICENSE): модели Ultralytics распространяются под AGPL-3.0, включая обученные веса.
