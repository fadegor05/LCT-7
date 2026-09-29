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
  ml --> weights[("Веса mocs_m_best.pt<br/>том lct7_ml_weights")]
  ml -->|"LLM_BASE_URL"| llm[["Внешняя языковая модель<br/>формат chat completions"]]
```

| Сервис | Роль |
|---|---|
| `traefik` | Единая точка входа. `/api` уходит в backend (приоритет 20), всё остальное во frontend (приоритет 1). Порт 8080 открывает дашборд без пароля |
| `frontend` | Одностраничное приложение. В dev вместо nginx работает Vite dev-server на порту 5173 |
| `backend` | REST API. При старте контейнера выполняет `alembic upgrade head`, затем запускает Granian |
| `ml` | Распознавание техники, чтение штампа, ассистент, разбор графика моделью |
| `postgres` | Основная база |
| `minio`, `minio-init` | Поднимаются всегда, но бэкенд обращается к ним только при `S3=true`. По умолчанию снимки лежат в томе `storage_data` |

## Потоки данных

### Загрузка снимка

```mermaid
sequenceDiagram
  participant UI as Браузер
  participant API as backend
  participant ST as Хранилище
  participant ML as ml
  participant DB as PostgreSQL
  UI->>API: POST /api/sites/{id}/photos, файлы
  loop каждый файл по порядку
    API->>API: размер, формат, целостность
    API->>ML: POST /stamp (только при DETECTOR__STAMP_ENABLED)
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

Каждая внешняя система скрыта за `Protocol` с двумя реализациями: настоящей и заглушкой.

| Протокол | Реальная реализация | Заглушка |
|---|---|---|
| `DetectorClient` | `HttpDetectorClient` (повторы, ограничение параллелизма, кэш `/meta`) | `NullDetector` |
| `StampOcr` | `HttpStampReader` | `NullStampOcr` |
| `AssistantClient` | `HttpAssistantClient` (без повторов, каждый вызов платный) | `NullAssistantClient` |
| `ScheduleLlmClient` | `HttpScheduleLlmClient` | `NullScheduleLlmClient` |
| `FileStorage` | `S3FileStorage`, `LocalFileStorage` | нет |


## Развёртывание

| Слой compose | Файл | Что добавляет |
|---|---|---|
| Общий | `deploy/docker/common/core.yaml`, `infra.yaml` | Сервисы, метки Traefik, PostgreSQL, MinIO, Traefik |
| Разработка | `deploy/docker/dev/core.yaml` | Локальная сборка, bind-mount исходников, Granian с `--reload`, Vite вместо nginx, порт PostgreSQL наружу |
| Прод | `deploy/docker/prod/core.yaml` | TLS Let's Encrypt, лимиты памяти (backend 512 МБ, frontend 64 МБ, ml 1536 МБ), готовые образы |
