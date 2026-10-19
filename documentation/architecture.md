# Архитектура

## Контейнеры

Сервисы поднимаются в Docker Compose, наружу смотрит только Traefik.

```mermaid
flowchart LR
  user([Браузер]) -->|HTTP 80 или HTTPS 443| traefik[Traefik v3.6]
  traefik -->|"путь /"| frontend["frontend<br/>nginx, статика React"]
  traefik -->|"путь /api"| backend["backend<br/>FastAPI на Granian :8000"]
  backend --> pg[("PostgreSQL 16")]
  backend --> store[("Хранилище снимков<br/>том storage_data или MinIO")]
  backend -->|"DETECTOR__URL"| ml["ml<br/>FastAPI :8000<br/>YOLO26-m на CPU"]
  backend -->|"ffmpeg, кадр со стрима"| cams[["Камеры стройки<br/>RTSP, RTSPS, HTTP(S)"]]
  ml --> weights[("Веса mocs_m_best.pt<br/>том lct7_ml_weights")]
  ml -->|"LLM_BASE_URL"| llm[["Внешняя языковая модель<br/>формат chat completions"]]
```

| Сервис | Роль |
|---|---|
| `traefik` | Единая точка входа. `/api` уходит в backend (приоритет 20), всё остальное во frontend (приоритет 1). Порт 8080 открывает дашборд без пароля, но только на `127.0.0.1` хоста |
| `frontend` | Одностраничное приложение. В dev вместо nginx работает Vite dev-server на порту 5173 |
| `backend` | REST API. При старте контейнера выполняет `alembic upgrade head`, затем запускает Granian. При `STREAM__ENABLED=true` в том же процессе работает планировщик снимков со стрима камер |
| `ml` | Распознавание техники, чтение штампа, ассистент, разбор графика моделью |
| `postgres` | Основная база |
| `minio`, `minio-init` | Поднимаются всегда, но бэкенд обращается к ним только при `S3=true`. По умолчанию снимки лежат в томе `storage_data` |

## Потоки данных

### Аутентификация и авторизация

```mermaid
sequenceDiagram
  participant UI as Браузер
  participant API as backend
  participant DB as PostgreSQL
  UI->>API: POST /api/auth/login {login, password}
  API->>DB: SELECT * FROM app_user WHERE login = ?
  alt логин найден
    API->>API: verify_password(plain, hash) с argon2
    alt пароль верен
      API->>API: create_token(user_id) — JWT HS256
      API-->>UI: {access_token, token_type, user}
      UI->>UI: сохранить токен в localStorage['lct7.token']
    else пароль неверен
      API-->>UI: 401 «Неверный логин или пароль»
    end
  else логин не найден
    API->>API: verify_against_dummy(plain) — timing equalization
    API-->>UI: 401 «Неверный логин или пароль»
  end

  UI->>API: GET /api/sites, Authorization: Bearer {token}
  API->>API: decode_token(token) — проверка HS256 подписи и exp
  alt токен валиден
    API->>DB: SELECT * FROM app_user WHERE id = ?
    API->>DB: SELECT * FROM sites WHERE owner_id = ?
    API-->>UI: сайты
  else токен невалиден или истёк
    API-->>UI: 401 «Требуется авторизация»
    UI->>UI: clearToken(), redirect на /login
  end
```

Токен хранится в `localStorage['lct7.token']` и передаётся в заголовке `Authorization` при каждом защищённом запросе. Срок жизни токена — `AUTH__TOKEN_TTL_MINUTES` (по умолчанию 720 минут). После истечения пользователь видит 401 на любом эндпоинте и редиректится на /login.

### Загрузка снимка

```mermaid
sequenceDiagram
  participant UI as Браузер
  participant API as backend
  participant ST as Хранилище
  participant ML as ml
  participant DB as PostgreSQL
  UI->>API: POST /api/sites/{id}/photos, файлы, Authorization: Bearer {token}
  loop каждый файл по порядку
    API->>API: размер, формат, целостность
    API->>ML: POST /stamp (если не отключено DETECTOR__STAMP_ENABLED=false)
    API->>ST: сохранить оригинал
    API->>ML: POST /detect
    ML-->>API: рамки в долях кадра
    API->>DB: photo и detections, commit
  end
  API->>DB: дата по соседям для снимков без даты
  loop каждая затронутая дата
    API->>DB: пересчитать наблюдение
    API->>DB: пересчитать статусы и отклонения
  end
  API-->>UI: отчёт по каждому файлу
```

Обработка синхронная. Запрос загрузки возвращается, когда все файлы прошли распознавание и пересчёт закончился. Очереди задач и отдельного воркера нет.

### Снимок со стрима камеры

Кадр снимает либо фоновый планировщик, либо кнопка «Снять кадр сейчас». Дальше путь тот же, что у загруженного файла, только дата берётся из момента снимка.

```mermaid
sequenceDiagram
  participant Src as Планировщик или кнопка
  participant G as GuardedGrabber
  participant FF as ffmpeg
  participant Ph as PhotoService
  participant DB as PostgreSQL
  Src->>G: grab(ссылка камеры)
  G->>G: адреса после DNS: служебные, петля, частные сети
  G->>FF: один кадр JPEG в stdout
  FF-->>G: кадр или причина неудачи
  G-->>Src: байты или текст без учётных данных
  Src->>Ph: add_camera_frame, дата по поясу STREAM__TIMEZONE, источник channel
  Ph->>DB: photo, пересчёт наблюдения и выводов за день
  Src->>DB: момент попытки, сбои подряд, последняя ошибка камеры
```

Планировщик раз в `STREAM__TICK_S` секунд выбирает камеры, которым пора, и снимает их не больше `STREAM__CONCURRENCY` сразу. Попытка записывается до снимка, поэтому камеру не берут повторно, пока она отвечает. Выборка идёт с `FOR UPDATE SKIP LOCKED`. Это страховка при нескольких репликах, но рассчитано на один экземпляр бэкенда.

### Цепочка пересчёта

Домены не импортируют друг друга напрямую. Связь идёт через протоколы-хуки, а настоящую реализацию подставляет контейнер зависимостей.

```mermaid
flowchart LR
  photo["photo<br/>upload_batch, set_date, redetect, detect_backlog"] -->|ObservationRecalculator| obs["observation<br/>recompute(site, дата)"]
  obs -->|StatusRecalculator| asm["assessment<br/>recompute_site(site)"]
  meth["methodology<br/>правка правил и комплектов"] -->|StatusRecalculator| asm
  sched["schedule<br/>импорт и правка дат"] -->|StatusRecalculator| asm
```

### Внешние системы через адаптеры

Большинство внешних систем скрыто за `Protocol` с двумя реализациями: настоящей и заглушкой. У снимков со стрима заглушки нет: без `ffmpeg` снимок завершается ошибкой с причиной, а не пустым результатом.

| Протокол | Реальная реализация | Заглушка |
|---|---|---|
| `DetectorClient` | `HttpDetectorClient` (повторы, ограничение параллелизма, кэш `/meta`) | `NullDetector` |
| `StampOcr` | `HttpStampReader` | `NullStampOcr` |
| `AssistantClient` | `HttpAssistantClient` (без повторов, каждый вызов платный) | `NullAssistantClient` |
| `ScheduleLlmClient` | `HttpScheduleLlmClient` | `NullScheduleLlmClient` |
| `FileStorage` | `S3FileStorage`, `LocalFileStorage` | нет |
| `StreamGrabber` | `FfmpegGrabber`, обёрнут в `GuardedGrabber` (проверка адресов) | нет |
| `NotificationChannel` | `TelegramChannel` поверх `TelegramClient` | `LogChannel` |


### Уведомления

Домен `notification` хранит ленту и привязки каналов. Доменам-источникам доступен один метод, `NotificationService.notify(user_id, type, title, body, link)`: про каналы и телеграм они ничего не знают. Источников событий пока нет — отклонения и сбои камер к этому шву не подключены, лента наполняется только служебным `POST /api/notifications/test`.

Доставка идёт через реестр каналов (`ChannelRegistry`, `Scope.APP`). Реализован один канал, телеграм; без `NOTIFY__TELEGRAM__TOKEN` на его месте `LogChannel`, который только пишет в лог приложения. Почта и СМС не реализованы: интерфейс `NotificationChannel` на них рассчитан, файлов нет.

Отправкой занимается `BackgroundDispatcher`. Сервис создаёт уведомление, коммитит транзакцию и только после этого планирует доставку через `asyncio.create_task`; задача берёт собственную сессию из `async_sessionmaker`, потому что сессия запроса к этому моменту уже закрыта. Ошибка канала пишется в лог и не влияет на HTTP-ответ. Таблицы доставок и повторов нет — следствия описаны в `limitations.md`.

Привязка телеграма устроена так же, как фоновые снимки со стрима: `TelegramLinkPoller` поднимается в `lifespan` и живёт, только если бот настроен. Он опрашивает Bot API методом `getUpdates` (long polling) и на `/start <токен>` гасит одноразовый токен из `channel_link_tokens`, сохраняя `chat_id`. Webhook не используется: ему нужен публичный HTTPS, которого нет при локальной разработке. Курсор апдейтов живёт в памяти задачи — телеграм хранит их сутки, а повторный `/start` по погашенному токену безвреден.

### Прокси для телеграма

`api.telegram.org` заблокирован в России, поэтому телеграм-клиент бэкенда ходит через Xray:

```
TelegramClient --http://xray:8080--> Xray --VLESS--> api.telegram.org
```

Маршрутизации по домену внутри Xray нет намеренно: в прокси попадает только то, что послал
телеграм-клиент, остальной трафик приложения (Postgres, MinIO, LLM, ML) идёт напрямую и Xray
не видит. Вход у Xray — HTTP, а не SOCKS, потому что `httpx` умеет HTTP-прокси без
дополнительных зависимостей.

Живую ссылку среди нескольких выбирает сам Xray, своей логики для этого нет:
`observatory` пингует каждый outbound по `XRAY__PROBE_URL`, а балансировщик со стратегией
`leastPing` шлёт трафик через самый быстрый из отвечающих и переключается, когда тот падает.
Стратегия `leastPing` без `observatory` не запускается — Xray отказывается стартовать с
«not all dependencies are resolved», так что эти две части конфига связаны жёстко.

Конфиг собирает отдельный контейнер `xray-init` из `backend/tools/xray_config.py`: официальный
образ `xray-core` — distroless, в нём нет ни shell, ни Python, поэтому генерировать конфиг
внутри него нечем. Результат кладётся в том `xray_config`, Xray читает его штатным `-confdir`.
Образ бэкенда для этого подходит потому, что скрипт лежит в нём (`COPY . .`), и тот же код
покрыт обычным `pytest`. Healthcheck'а у `xray` нет: в distroless-образе проверять соединение
изнутри нечем, готовность конфига гарантирует `depends_on` на успешно завершившийся `xray-init`.

Если все ссылки мертвы, Xray слушает, но соединения не проходят: `httpx` получает ошибку,
доставка пишет её в лог, привязка остаётся, уведомление остаётся в интерфейсе. Отдельной
обработки для этого не потребовалось — это тот же путь, что и при недоступном Bot API.

## Развёртывание

| Слой compose | Файл | Что добавляет |
|---|---|---|
| Общий | `deploy/docker/common/core.yaml`, `infra.yaml` | Сервисы, метки Traefik, PostgreSQL, MinIO, Traefik |
| Разработка | `deploy/docker/dev/core.yaml` | Локальная сборка, bind-mount исходников, Granian с `--reload`, Vite вместо nginx, порт PostgreSQL наружу |
| Прод | `deploy/docker/prod/core.yaml` | TLS Let's Encrypt, лимиты памяти (backend 512 МБ, frontend 64 МБ, ml 1536 МБ), готовые образы |

В образе backend стоят два системных пакета: `ffmpeg` (снимки со стрима камер) и `fonts-dejavu-core` (кириллица в подписях рамок на аннотированных снимках).
