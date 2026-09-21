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

## Включить автоматический деплой

`.github/workflows/cd.yml` — каркас. Job `build-push` рабочий (собирает образы и
кладёт в GHCR по ручному запуску), job `deploy` пропускается, пока не выставлена
переменная `DEPLOY_ENABLED`.

Порядок включения:

1. Один раз собрать и опубликовать образы: **Actions → CD (шаблон) → Run
   workflow**. Появятся пакеты `ghcr.io/refaxd/lct-7/backend` и `.../frontend`.
   Если пакеты приватные — на хосте нужен `docker login ghcr.io` с PAT
   (`read:packages`).
2. Выбрать способ доставки — **вариант A или B** ниже, раскомментировать
   соответствующий блок в `cd.yml`.
3. Завести секреты окружения `prod` (Settings → Environments → prod).
4. Выставить переменную `DEPLOY_ENABLED=true` (Settings → Secrets and variables
   → Actions → Variables) и убрать шаг-заглушку `Что нужно заполнить`.
5. Когда деплой поедет — включить автотриггер: в `cd.yml` раскомментировать
   `push: tags: ['v*']`.

### Вариант A — self-hosted runner на домашнем ПК (рекомендуется)

За NAT и туннелем входящего SSH нет, а runner сам ходит на GitHub — ничего
пробрасывать не надо. Ставится один раз: Settings → Actions → Runners → New
self-hosted runner, метки `self-hosted`, `xxprod`. В job'е `deploy` тогда
`runs-on: [self-hosted, xxprod]`, а шаги — обычные локальные команды
(`make deploy-tunnel`).

Минус: runner выполняет код из репозитория на домашней машине — форки к PR
допускать нельзя (для self-hosted это и так требует подтверждения).

### Вариант B — деплой по SSH

Нужен доступный извне SSH. Секреты окружения `prod`:

| Секрет | Что это |
|---|---|
| `DEPLOY_HOST` | хост или IP |
| `DEPLOY_PORT` | порт SSH |
| `DEPLOY_USER` | пользователь с правом на docker |
| `DEPLOY_SSH_KEY` | приватный ключ ed25519 без пароля, только под деплой |
| `GHCR_PULL_TOKEN` | PAT с `read:packages`, если пакеты приватные |

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
