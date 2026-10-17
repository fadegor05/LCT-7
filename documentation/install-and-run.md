# Сборка, установка и запуск

Три способа запуска.

| Способ | Что получите | Что нужно |
|---|---|---|
| A. Интерфейс на моках | Все экраны с демонстрационной стройкой «Березники», без бэкенда | Node.js и pnpm |
| B. Весь стек в Docker | Настоящие бэкенд, база, хранилище, интерфейс. Распознавание техники только при наличии весов | Docker |
| C. Без Docker | То же вручную | Python, Node.js, PostgreSQL |

## Требования

| Что | Версия | Где нужно |
|---|---|---|
| Git | любая | все способы |
| Docker и Docker Compose v2 | Docker 24 и новее | способ B |
| GNU Make | любая | способ B, команды `make` |
| Node.js | 22 | способы A и C |
| pnpm | 10.18 (`corepack enable`, версия закреплена в `frontend/Dockerfile`) | способы A и C |
| Python | 3.12 | способ C |
| uv | последняя | способ C |
| PostgreSQL | 16 | способ C |
| Токен Hugging Face с правом чтения приватного репозитория весов | нет | распознавание техники, см. ниже |
| Доступ к языковой модели по формату chat completions | нет | ассистент и разбор графика моделью, необязательно |
| Свободные порты 80, 443, 8080 и 5432 | нет | способ B: Traefik занимает 80, 443 и 8080, PostgreSQL в dev-режиме публикуется на 5432 |

## Способ A. Только интерфейс на моках

```bash
git clone <адрес репозитория> LCT-7
cd LCT-7/frontend
pnpm install
pnpm dev
```

Откройте `http://localhost:5173`. В шапке будет бейдж «Моки». Бэкенд, база и Docker не нужны. Все данные ненастоящие: это демонстрационная стройка из `frontend/src/mocks/fixtures.ts`. Загруженные вами графики и снимки живут в памяти вкладки, статусов и отклонений у новых строек нет.

## Способ B. Весь стек в Docker

### 1. Подготовьте окружение

```bash
git clone <адрес репозитория> LCT-7
cd LCT-7
cp .env.dist .env
```

Откройте `.env` и поправьте.

| Переменная | Значение | Зачем |
|---|---|---|
| `VITE_USE_MOCKS` | `false` | Иначе интерфейс покажет моки и не обратится к бэкенду. В `.env.dist` по умолчанию `true` |
| `DETECTOR__URL` | пусто, если ML не запускается | При пустом значении снимки остаются в статусе `pending`. При значении `http://ml:8000` и остановленном `ml` они получат `failed` |
| `ASSESSMENT__AS_OF_MODE` | `last_observation` для демо на старых снимках | Иначе расчёт считает «сегодня» и покажет отставание на сотни дней. Строка в `.env.dist` закомментирована |
| `POSTGRES__PASSWORD` | своё значение для любого общедоступного стенда | Значение по умолчанию `supersecretpassword` |

Остальные переменные описаны в [configuration.md](configuration.md).

### 2. Запустите

Без распознавания (быстрее, без весов):

```bash
make dev
```

С распознаванием техники, после загрузки весов (шаг 3):

```bash
make dev-ml
```

Первая сборка занимает несколько минут: собираются образы `backend` и `frontend`, а во фронтенде при старте выполняется `pnpm install`. Бэкенд при старте сам применяет миграции (`alembic upgrade head`).

### 3. Загрузите веса детектора (только для `make dev-ml`)

Веса не хранятся в репозитории, они лежат в приватном репозитории Hugging Face. Нужен токен с правом чтения, который выдаёт команда проекта.

```bash
export HF_TOKEN=<ваш токен>
make ml-weights
```

Команда запускает одноразовый контейнер и кладёт `mocs_m_best.pt` (42 МБ) в том `lct7_ml_weights`. Репозиторий по умолчанию `lct-7/lct7-construction-detector`, другой задаётся переменной `HF_REPO`.

Без весов контейнер `ml` не стартует (`FileNotFoundError`) и перезапускается по кругу из-за `restart: always`. Если весов нет, запускайте `make dev` и оставляйте `DETECTOR__URL` пустым.

### 4. Проверьте

| Адрес | Что должно быть |
|---|---|
| `http://localhost` | Интерфейс |
| `http://localhost/api/health` | `{"status":"ok"}` |
| `http://localhost/api/ready` | `{"database":true,...}`, в поле `detector` при запущенном ML `"ready":true` и версия модели |
| `http://localhost/api/docs` | Swagger UI |
| `http://localhost/api/version` | Тег сборки и версия модели |
| `http://localhost:8080` | Панель Traefik |

Журналы: `make logs`. Остановка: `make down`. Данные (база, снимки) при остановке сохраняются в томах Docker.

Полный сброс, с удалением томов базы, снимков и весов:

```bash
docker compose --project-directory . --env-file ./.env --env-file ./deploy/versions.env \
  -f deploy/docker/common/core.yaml -f deploy/docker/common/infra.yaml down -v --remove-orphans
```

### 5. Заведите пользователя

Все эндпоинты, кроме входа, регистрации и служебных (`/health`, `/ready`, `/version`), требуют токена. На моках (способ A) вход `demo` / `demo`.

На реальном бэкенде аккаунт заводится одним из трёх способов:

- в интерфейсе на странице `/register`;
- запросом `POST /api/auth/register` (пример в следующем шаге);
- командой CLI из контейнера бэкенда:

```bash
docker compose exec backend python -m app.cli create-user --login mylogin [--full-name "My Name"] [--password mypassword]
```

Без Docker та же команда запускается из `backend/`: `python -m app.cli create-user ...`. Если флага `--password` нет, программа дважды спросит пароль. Логин приводится к нижнему регистру, ФИО по умолчанию равно логину.

### 6. Пробный проход через API

Команды регистрируют пользователя, создают стройку, загружают маленький график, подставляют базовые комплекты и читают результат. Снимков в репозитории нет (материалы организаторов публиковать нельзя), поэтому проход без ML заканчивается статусом «не наблюдалось».

```bash
cat > /tmp/schedule.csv <<'EOF'
Работа;Начало;Окончание
Разработка котлована;01.03.2026;30.04.2026
Устройство свай;15.04.2026;30.06.2026
Монолитные работы ниже нуля;01.07.2026;30.09.2026
EOF

TOKEN=$(curl -s -X POST http://localhost/api/auth/register -H 'Content-Type: application/json'   -d '{"login":"proba","password":"proba-pass-1"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
AUTH="Authorization: Bearer $TOKEN"

SITE=$(curl -s -X POST http://localhost/api/sites -H "$AUTH" -H 'Content-Type: application/json'   -d '{"name":"Проба","address":"Москва"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["id"])')

curl -s -X POST "http://localhost/api/sites/$SITE/schedule/import" -H "$AUTH" -F file=@/tmp/schedule.csv -F mode=builtin
curl -s -X POST "http://localhost/api/sites/$SITE/methodology/apply-defaults" -H "$AUTH"
curl -s "http://localhost/api/sites/$SITE/assessment/stages" -H "$AUTH"
curl -s "http://localhost/api/sites/$SITE/assessment/summary" -H "$AUTH"
```

Если логин `proba` уже занят, регистрация вернёт `409`: возьмите другой логин или получите токен через `POST /api/auth/login` с теми же полями.

Ожидаемый результат. Три этапа разобраны. После импорта у всех этапов пустые правила и статус `not_checked`: комплекты сами не подставляются. Вызов `apply-defaults` отвечает `{"applied":3,"eligible":3,"unmatched":0}`: все три названия совпали с базовыми правилами (котлован, сваи, монолит). Снимков нет, поэтому начавшиеся этапы получают статус `not_observed`, итог `insufficient_data`, отклонений нет. Комплект можно задать и вручную во вкладке «Методика» или через `POST /api/sites/$SITE/methodology/rules/{ruleId}/sets`.

Чтобы получить осмысленные статусы, нужны снимки и работающий детектор. Загрузка:

```bash
curl -s -X POST "http://localhost/api/sites/$SITE/photos" -H "$AUTH" -F files=@frame1.jpg -F files=@frame2.jpg
```

Дата берётся из EXIF, штампа (по умолчанию включено, нужен `DETECTOR__URL`; отключается `DETECTOR__STAMP_ENABLED=false`), имени файла или от соседних снимков пачки, иначе её задают вручную (`PATCH .../photos/{id}/date`).

## Способ C. Без Docker

### PostgreSQL

```bash
docker run -d --name lct7-pg -e POSTGRES_USER=app_user -e POSTGRES_PASSWORD=supersecretpassword \
  -e POSTGRES_DB=postgres -p 5432:5432 postgres:16.6
```

Годится и установленный локально PostgreSQL 16 с теми же именем пользователя, паролем и базой.

### Бэкенд

```bash
cd backend
uv sync
export PYTHONPATH=.
export POSTGRES__HOST=localhost
export STORAGE__LOCAL_ROOT=/tmp/lct7-storage      # каталог для снимков
export ASSESSMENT__AS_OF_MODE=last_observation    # для демо на старых снимках
uv run alembic upgrade head
uv run granian --interface asgi app.main:app --host 127.0.0.1 --port 8000 --reload
```

Проверка: `curl http://127.0.0.1:8000/api/health`. Настройки читаются из переменных окружения и из файла `backend/.env`, если он есть. Вложенные секции задаются через двойное подчёркивание.

### Фронтенд против этого бэкенда

```bash
cd frontend
pnpm install
VITE_API_PROXY_TARGET=http://localhost:8000 pnpm dev:api
```

Интерфейс на `http://localhost:5173`.

### ML-сервис

С весами:

```bash
cd ml
python3.12 -m venv .venv && source .venv/bin/activate
pip install torch==2.14.0 torchvision==0.29.0 --index-url https://download.pytorch.org/whl/cpu
pip install ultralytics==8.4.153 pillow==12.3.0 huggingface_hub "fastapi>=0.115" "uvicorn[standard]>=0.30" \
  python-multipart opencv-python-headless==5.0.0.93 numpy==2.5.2 rapidocr-onnxruntime==1.2.3
HF_TOKEN=<токен> python tools/fetch_weights.py
uvicorn service.app:app --port 8001
```

Затем для бэкенда `export DETECTOR__URL=http://localhost:8001`.

Без весов сервис можно запустить в демо-режиме: он отвечает заранее посчитанными детекциями из `ml/data/processed/detections_mocs_m.json` (сопоставление по имени файла, каждый ответ помечен `"mode": "demo"`).

```bash
cd ml && DEMO_DETECTIONS=data/processed/detections_mocs_m.json uvicorn service.app:app --port 8001
```

В контейнере демо-режим не подключён: каталог `ml/data` в образ не копируется. Снимков, имена которых есть в выгрузке, в репозитории нет.

## Запуск проверок

```bash
make test           # тесты бэкенда (pytest, SQLite в памяти)
make check          # ruff: линт и формат бэкенда
make front-check    # типы, ESLint, Stylelint, Prettier, тесты фронтенда с покрытием
```
