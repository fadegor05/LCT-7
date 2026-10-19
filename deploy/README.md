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
NOTIFY__PUBLIC_URL=https://xxprod.ru
```

Доставка уведомлений в телеграм включается двумя переменными:

```dotenv
NOTIFY__TELEGRAM__TOKEN=<токен от @BotFather>
NOTIFY__TELEGRAM__BOT_USERNAME=<имя бота без @>
```

Без них уведомления работают, но остаются только в интерфейсе: сообщения пишутся
в лог приложения, кнопка привязки в личном кабинете отвечает «канал не настроен».
`NOTIFY__PUBLIC_URL` нужен, чтобы ссылки в сообщениях были абсолютными, иначе из
телеграма по ним не перейти.

Там, где `api.telegram.org` заблокирован (Россия), бот не заработает без прокси.
Добавьте ссылки VLESS и поднимайте стек профилем `proxy`:

```dotenv
XRAY__LINKS=vless://...#Узел один
vless://...#Узел два
```

Разделитель — перевод строки или запятая, но не пробел: пробел бывает в названии
узла, и ссылка порвётся. Затем `make up-proxy` вместо `make up` (или `make deploy`
с теми же дополнительными `-f`, см. makefile). Проверить ссылки, не поднимая стек:
`make xray-check`.

Затем:

```bash
make deploy-tunnel   # pull образов по тегам из deploy/versions.env + up
make logs
curl -fsS http://localhost/api/health
```

Туннель поднимается отдельно (агент TUNA на этом же ПК) и смотрит на **:80**.
Порт **8080 (дашборд Traefik) наружу не пробрасывать** — он поднят с
`api.insecure: true` и не требует аутентификации. В compose он привязан к
`127.0.0.1:8080`, снаружи недоступен.

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

## Ассистент по отчёту (LLM)

Языковая модель помогает прочитать готовый отчёт: пользователь спрашивает на
русском, ассистент отвечает пересказом данных с проверкой чисел.

### Подключение модели

Три переменные в корневом `.env`:

```dotenv
LLM_BASE_URL=https://<хост-провайдера>/v1
LLM_API_KEY=<ключ>
LLM_MODEL=<имя-модели>
```

Сервис обращается к `{LLM_BASE_URL}/chat/completions` — формат OpenAI,
заголовок `Authorization: Bearer {LLM_API_KEY}`, `temperature: 0`. Подойдёт
любой сервис или локальная модель, которая держит этот формат.

Переменные передаются **только** в контейнер `ml`; в `backend` они отсутствуют
(ключ живёт только в ML-сервисе).

### Проверка доступности

```bash
docker compose exec ml python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/meta').read().decode())"
```

Поле `"assistant": true` означает, что модель доступна и ассистент готов
отвечать. Запрос `/meta` может ответить 503 пока модель прогревается
(до 90 секунд после старта сервиса).

Без подключения переменных `POST /ask` отвечает 503 — это штатное состояние
стенда без LLM-провайдера. Интерфейс в этом случае ассистента не показывает.

Доступные модели провайдера:

```bash
# в Docker
docker compose exec ml python tools/suggest_stage_mapping.py --list-models

# при локальной разработке (из ml/ с переменными в ml/.env)
python tools/suggest_stage_mapping.py --list-models
```

## Стенд в Yandex Cloud (veha-stand)

С 27.09.2026 стенд живёт на ВМ в Yandex Cloud: 4 vCPU (Intel Ice Lake, 100%),
8 ГБ, SSD 30 ГБ, Ubuntu 24.04, статический IP `81.26.184.6`. До появления домена
работает по HTTP через `make deploy-tunnel`: роутинг только по пути, без `Host(...)`.

Что важно знать про сеть Yandex Cloud:

* **Docker Hub недоступен** (таймаут на `registry-1.docker.io`). В
  `/etc/docker/daemon.json` на ВМ прописано зеркало `https://mirror.gcr.io`, через
  него идут `postgres`, `traefik`, `coollabsio/minio` и базовые образы.
* **`download.pytorch.org`, `registry.npmjs.org` и `api.github.com` недоступны**,
  поэтому образы `ml` и `frontend` на ВМ не собираются. Их собирает GitHub Actions
  и кладёт в Yandex Container Registry, ВМ только тянет готовое.
* **GitHub с ВМ доступен с перебоями**: `ghcr.io` ответил на 7 запросов из 20,
  скачивание образа обрывалось. Поэтому реестр — `cr.yandex` (15 из 15 изнутри
  облака, доступен и из-за рубежа, откуда пушат раннеры GitHub).
* HuggingFace и PyPI с ВМ доступны.

Раскладка на ВМ:

```
/opt/veha/
├── .env                 # только на ВМ: DOMAIN=<IP>, пароли PostgreSQL и MinIO, DETECTOR__URL
├── .deployed-revision   # коммит, который сейчас выкачен
├── bin/autodeploy.sh    # копия deploy/autodeploy/autodeploy.sh
├── makefile             # приезжают в посылке из того же коммита, что и образы
└── deploy/
```

Группа безопасности `veha-sg`: входящие 80, 443 и 22 (TCP), исходящие все.
8080 (дашборд Traefik без пароля) наружу закрыт.

**Входящие соединения с зарубежных адресов до ВМ не доходят** (проверено с ~35
узлов check-host: SYN-пакеты не появляются на интерфейсе, при группе безопасности
`0.0.0.0/0`). С российских адресов стенд и SSH доступны. Отсюда:

* открывать стенд и заходить по SSH — без VPN, либо с VPN, который пускает
  российские адреса напрямую (`81.26.184.6` в исключениях);
* доставка из GitHub Actions по SSH невозможна — раннеры за рубежом;
* self-hosted runner тоже не вариант: с ВМ недоступен `api.github.com`.

Веса детектора лежат в томе `lct7_ml_weights` (скачаны 27.09). Если том пропадёт:

```bash
read -rs HF_TOKEN && export HF_TOKEN
docker run --rm -e HF_TOKEN -v lct7_ml_weights:/weights -v /opt/veha/tools:/tools:ro   python:3.12-slim sh -c "pip install -q huggingface_hub && python /tools/fetch_weights.py --out /weights"
unset HF_TOKEN
```

## Автоматический деплой

Деплой устроен «от ВМ»: она сама забирает обновления, входящих соединений не нужно.

1. **GitHub Actions** (`.github/workflows/cd.yml`) на каждый push в `main` собирает
   `backend`, `frontend`, `ml` и публикует в Yandex Container Registry с тегами
   `sha-<коммит>` и `latest`. Последним публикуется образ-«посылка» `deploy`
   (`deploy/autodeploy/Dockerfile`): `makefile` и `deploy/` того же коммита, в метке —
   полный sha.
2. **Таймер на ВМ** (`veha-autodeploy.timer`, раз в две минуты) запускает
   `autodeploy.sh`: тянет `deploy:latest`, и если коммит новый — раскладывает файлы,
   ставит теги `sha-<коммит>`, делает `make $DEPLOY_TARGET` и проверяет
   `/api/health`.

Что автодеплой трогает на ВМ, а что нет:

* `.env` и `deploy/config/traefik/certs/` — **не трогает** никогда.
* `deploy/config/traefik/traefik.yml` — кладёт только если файла ещё нет; правки
  на ВМ (например, email для Let's Encrypt) сохраняются.
* `makefile`, `deploy/docker/*`, `deploy/versions.env` — **перезаписывает** из
  посылки при каждой выкладке. Правки этих файлов прямо на ВМ пропадут — их
  вносят через `main`.
* Режим выбирается в `.env` ВМ переменной `DEPLOY_TARGET`: `deploy-tunnel`
  (по умолчанию, HTTP на :80, роутинг только по пути) или `deploy` (домен из
  `DOMAIN`, HTTPS с сертификатом Let's Encrypt, `prod/core.yaml`).

Настройка реестра (один раз, в консоли Yandex Cloud):

1. Container Registry → создать реестр `veha`, его ID (`crp…`) вписать в
   `REGISTRY=cr.yandex/<ID>` в `deploy/versions.env`.
2. Реестр → Права доступа → роль `container-registry.images.puller` для «Все
   пользователи» (`system:allUsers`): образы публичные, ВМ тянет без токена. Весов в
   образах нет.
3. Сервисный аккаунт `veha-ci` с ролью `container-registry.images.pusher` на реестр,
   авторизованный ключ в JSON.
4. GitHub → Settings → Secrets and variables → Actions: секрет `YC_SA_JSON_KEY` —
   JSON ключа целиком, переменная `YC_REGISTRY_ID` — ID реестра. Пока переменной нет,
   CD собирает образы, но никуда не публикует.
5. По желанию — политика очистки реестра: хранить последние 5 тегов, чтобы старые
   образы ML (≈2.5 ГБ каждый) не копили плату за хранение.

Журнал и ручной запуск:

```bash
journalctl -u veha-autodeploy -n 50 --no-pager   # что делал деплой
sudo systemctl start veha-autodeploy              # проверить обновления прямо сейчас
cat /opt/veha/.deployed-revision                  # какой коммит выкачен
```

Откат — revert в `main`: новый коммит соберётся и выкатится так же.

Установка таймера (один раз, уже сделано 27.09):

```bash
# скрипт не обновляется посылкой сам: после его изменений в main повторить эту строку
sudo install -m 755 -o veha -g veha deploy/autodeploy/autodeploy.sh /opt/veha/bin/autodeploy.sh
sudo cp deploy/autodeploy/veha-autodeploy.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now veha-autodeploy.timer
```

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

* Бэкапов postgres (том `postgres_data` живёт только на ВМ).
* Ротации секретов и хранилища для них — `.env` правится руками на хосте.
* Блокировки деплоя при красном CI: `cd.yml` запускается на push в `main` и
  на статус CI не смотрит.
