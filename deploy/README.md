# Деплой

Что здесь лежит:

```
deploy/
├── versions.env              # реестр образов + теги, которые тянет `make deploy*`
├── config/traefik/
│   ├── traefik.yml           # конфиг Traefik (entrypoints, ACME)
│   └── certs/                # acme.json, в git не попадает
└── docker/
    ├── common/{core,infra}.yaml  # сервисы + postgres + traefik (база для всех сред)
    ├── dev/core.yaml             # локальный билд, bind-mount, hot-reload
    ├── prod/core.yaml            # прод с собственным TLS (Let's Encrypt на хосте)
    └── prod/tunnel.yaml          # прод за туннелем: TLS терминирует туннель
```

`prod/core.yaml` и `prod/tunnel.yaml` — **альтернативы**, а не слои друг поверх
друга. Выбор делается целью makefile: `make deploy` или `make deploy-tunnel`.

## Целевая схема MVP

Хостинга нет — MVP живёт на домашнем ПК, наружу торчит через туннель TUNA на
домен `xxprod.ru` (жюри заходит без VPN). Отсюда два следствия:

1. **TLS терминируется туннелем.** Let's Encrypt через `httpChallenge` до
   Traefik за NAT не дойдёт, и сертификат не нужен — его даёт край туннеля.
   Поэтому в `prod/tunnel.yaml` нет ни `websecure`, ни `certresolver`,
   роутеры сидят на `web` (:80).
2. **Роутинг без `Host(...)`.** Туннель может подменить `Host`-заголовок, а на
   этом хосте всё равно одно приложение. Разводим только по пути:
   `/api` → backend (priority 20), всё остальное → frontend (priority 1).

```
жюри ──https──> TUNA (xxprod.ru) ──http──> :80 домашнего ПК ──> Traefik ──┬─> /api  backend:8000
                                                                          └─> /*    frontend:80
```

## Разворачивание на хосте (вручную, первый раз)

```bash
git clone git@github.com:refaxD/LCT-7.git /opt/lct-7 && cd /opt/lct-7
cp .env.dist .env
```

В `.env` для прода:

```dotenv
DOMAIN=xxprod.ru
SECURE=true
API_PREFIX=/api
POSTGRES__PASSWORD=<не supersecretpassword>
```

Затем:

```bash
make deploy-tunnel   # pull образов по тегам из deploy/versions.env + up
make logs
curl -fsS http://localhost/api/health
```

Туннель поднимается отдельно (агент TUNA на этом же ПК) и смотрит на **:80**.
Порт **8080 (дашборд Traefik) наружу не пробрасывать** — он поднят с
`api.insecure: true` и не требует аутентификации.

## ML-детектор

Сервис обнаружения объектов на строительных площадках. Весят 42 МБ, в git не
хранятся — их загружают перед первым запуском.

### Загрузка весов

```bash
export HF_TOKEN=<токен_huggingface>  # HuggingFace токен с доступом к Gatarez/lct7-construction-detector
make ml-weights
```

Токен хранится в `~/.cache/huggingface/` на хосте, не в проекте. Можно также
положить в `.env` как `HF_TOKEN=...` или переименовать для локальной разработки в
`ml/.env`.

### Локальная разработка с ML

```bash
make dev-ml        # dev + --profile ml
```

Без профиля `make dev` ML не запускает (экономит ресурсы, если фронт и миграции
тестируете без детектора). Бэкенд всегда готов ответить: если ML недоступен,
фото остаются в статусе `pending`, но приложение работает нормально.

### Память и ресурсы

- **Prod**: `mem_limit: 1536m` (для инференса YOLOE v11m на RTX 2060 SUPER).
- **Dev**: без лимита (обычно требует 2–3 ГБ).
- GPU опционален; сейчас используется CPU.

### Поведение без ML

Если сервис недоступен или не настроен (`DETECTOR__URL` пусто):

- Новые фото загружаются, остаются в статусе `pending` (не удаляются).
- Эндпоинт GET `/api/health` (на `backend`) возвращает `200 OK`, но `"detector":
  {"configured": false, "ready": false}`.
- Фронт показывает кнопку «Распознать необработанные» только если фото с статусом
  `pending` или `failed`.

### Добрать обработку фото

```bash
curl -X POST http://localhost/api/sites/{id}/photos/detect?status=pending,failed
```

Возвращает: `{processed, done, failed, skipped}`. Логика:
- Проходит по фото с указанными статусами (по умолчанию оба).
- После первой транзиентной ошибки (503, таймаут) прекращает вызовы и считает
  остаток `skipped` (ML упал, не тратить бюджет повторов).

### Здоровье ML в статус-эндпоинтах

- `/api/health`: блок `"detector"` с `configured` (определён ли `DETECTOR__URL`),
  `ready` (ответил ли `/meta` без ошибок, модель загружена), `model` (версия
  образ@sha, если достижима).
- `/api/version`: добавлено поле `"model"` (версия, или `null` если ML недоступен).

## Стенд в Yandex Cloud (veha-stand)

С 27.09.2026 стенд живёт на ВМ в Yandex Cloud: 4 vCPU (Intel Ice Lake, 100%),
8 ГБ, SSD 30 ГБ, Ubuntu 24.04, статический IP `81.26.184.6`. До появления домена
работает по HTTP через `make deploy-tunnel`: роутинг только по пути, без `Host(...)`.

Что важно знать про сеть Yandex Cloud:

* **Docker Hub недоступен** (таймаут на `registry-1.docker.io`). В
  `/etc/docker/daemon.json` на ВМ прописано зеркало `https://mirror.gcr.io`, через
  него идут `postgres`, `traefik`, `coollabsio/minio` и базовые образы.
* **`download.pytorch.org` и `registry.npmjs.org` недоступны**, поэтому образы
  `ml` и `frontend` на ВМ не собираются. Их собирает GitHub Actions и кладёт в GHCR,
  ВМ только тянет готовое.
* GHCR, GitHub и HuggingFace с ВМ доступны.

Раскладка на ВМ:

```
/opt/veha/
├── .env            # только на ВМ: DOMAIN=<IP>, пароли PostgreSQL и MinIO, DETECTOR__URL
├── makefile        # выкладывает CD из того же коммита, что и образы
└── deploy/         # compose-файлы и versions.env (теги sha-<коммит> ставит CD)
```

Группа безопасности `veha-sg`: входящие 80, 443 и 22 (TCP), исходящие все.
8080 (дашборд Traefik без пароля) наружу закрыт.

Веса детектора кладутся в том `lct7_ml_weights` один раз, после первого деплоя
(нужен образ `ml`):

```bash
cd /opt/veha && HF_TOKEN=<токен> make ml-weights && docker compose restart ml
```

## Автоматический деплой

`.github/workflows/cd.yml` на каждый push в `main` (и по ручному запуску):

1. собирает `backend`, `frontend`, `ml` и публикует в GHCR с тегами `sha-<коммит>`
   и `latest`;
2. выкладывает на ВМ `makefile` и `deploy/` из того же коммита;
3. логинится в GHCR на ВМ временным `GITHUB_TOKEN` (живёт, пока идёт job —
   отдельный PAT не нужен), ставит теги `sha-<коммит>` в `deploy/versions.env`
   и делает `make deploy-tunnel`;
4. проверяет `http://<IP>/api/health`.

Job `deploy` запускается, только если выставлено всё ниже (Settings → Secrets and
variables → Actions; нужны права администратора репозитория):

| Что | Имя | Значение |
|---|---|---|
| секрет | `DEPLOY_HOST` | `81.26.184.6` |
| секрет | `DEPLOY_USER` | `veha` |
| секрет | `DEPLOY_SSH_KEY` | приватный ключ `~/.ssh/ci_deploy` с ВМ (ключ только под деплой) |
| переменная | `DEPLOY_ENABLED` | `true` |
| переменная | `DEPLOY_URL` | `http://81.26.184.6` |

Откат — ручной запуск workflow на нужном коммите (Actions → CD → Run workflow,
ветка или тег).

## GPU (RTX 2060 SUPER)

Сейчас ни один сервис GPU не просит: `ml/` — отдельные CLI-скрипты, в бэкенд не
подключены. Когда появится ML-сервис, ему в compose нужен доступ к карте
(на хосте — драйвер NVIDIA + `nvidia-container-toolkit`):

```yaml
services:
  ml:
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

8 ГБ памяти 2060 SUPER хватает на инференс YOLOE в разрешении 1280; обучение
на ней не планируется. Пока карта не задействована — это задел, а не факт.

## Чего в шаблоне намеренно нет

* Бэкапов postgres (том `postgres_data` живёт только на этом ПК).
* Ротации секретов и хранилища для них — `.env` правится руками на хосте.
* Блокировки деплоя при красном CI: `cd.yml` запускается вручную и на статус
  CI не смотрит.
