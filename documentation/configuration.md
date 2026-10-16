# Конфигурация

Образец: `.env.dist`. Файл `.env` в git не попадает.

## Общие

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `DOMAIN` | `localhost` | Хост для правил Traefik. Сам бэкенд её не использует |
| `SECURE` | `false` | Признак HTTPS. Определена в настройках, кодом сейчас не читается |
| `API_PREFIX` | `/api` | Префикс маршрутов и документации. Traefik префикс не срезает |
| `BACKEND_TAG` | `dev` | Тег сборки, отдаётся в `GET /api/version`. В compose подставляется из `deploy/versions.env` |

## База данных

| Переменная | По умолчанию |
|---|---|
| `POSTGRES__HOST` | `postgres` |
| `POSTGRES__PORT` | `5432` |
| `POSTGRES__USER` | `app_user` |
| `POSTGRES__PASSWORD` | `supersecretpassword` |
| `POSTGRES__DB` | `postgres` |

Строка подключения собирается как `postgresql+asyncpg://...`. Пароль по умолчанию нужно менять на любом стенде, доступном извне. `POSTGRES__PORT` в dev-слое ещё задаёт порт, на котором PostgreSQL публикуется на хосте.

## Хранилище снимков

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `S3` | `false` | `true` включает S3 или MinIO, иначе локальный том |
| `STORAGE__LOCAL_ROOT` | `/data/storage` | Каталог локального хранилища (в compose том `storage_data`) |
| `STORAGE__ENDPOINT_URL` | не задан | Адрес S3, например `http://minio:9000` |
| `STORAGE__BUCKET` | `photos` | Бакет |
| `STORAGE__ACCESS_KEY`, `STORAGE__SECRET_KEY` | `minioadmin` | Ключи доступа. Они же становятся паролем администратора MinIO в compose |
| `STORAGE__REGION` | `us-east-1` | |
| `STORAGE__MAX_UPLOAD_MB` | `20` | Предел одного файла |
| `STORAGE__MAX_BATCH_FILES` | `50` | Предел файлов в пачке. Больше отклоняется целиком |

В `.env.dist` переменные `STORAGE__*` не заданы, а сервисы `minio` и `minio-init` берут из них учётные данные и имя бакета. При `S3=false` это ни на что не влияет.

## ML-детектор

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `DETECTOR__URL` | не задан | Адрес ML-сервиса, например `http://ml:8000`. Пусто: детектор выключен, снимки остаются `pending`. Тот же адрес используют штамп, ассистент и разбор графика |
| `DETECTOR__TIMEOUT_S` | `30` | Таймаут запроса |
| `DETECTOR__CONNECT_TIMEOUT_S` | `2` | Таймаут соединения |
| `DETECTOR__MAX_CONCURRENCY` | `2` | Одновременных запросов |
| `DETECTOR__RETRY_503` | `3` | Повторов при 503 |
| `DETECTOR__RETRY_OTHER` | `1` | Повторов при другой 5xx, таймауте, сетевой ошибке |
| `DETECTOR__RETRY_BACKOFF_S` | `2, 5, 10` | Паузы перед повторами |
| `DETECTOR__RETRY_BUDGET_S` | `20` | Общий бюджет пауз на один снимок |
| `DETECTOR__STAMP_ENABLED` | `true` | Читать дату со штампа кадра (левый и правый нижний угол) через ML. Без `DETECTOR__URL` не действует |

## Наблюдения

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `OBSERVATION__MIN_PHOTOS_HIGH` | `3` | Снимков `done` за день для высокой наблюдаемости |
| `OBSERVATION__MIN_PHOTOS_MEDIUM` | `2` | Для средней |
| `OBSERVATION__MIN_SCORE_HIGH` | `0.7` | Порог высокой уверенности детекции |
| `OBSERVATION__MIN_SCORE_MEDIUM` | `0.4` | Порог средней уверенности |
| `OBSERVATION__MOVEMENT_THRESHOLD` | `0.05` | Сдвиг центра рамки в долях кадра, с которого активность считается `works` |

## Расчёт статусов и отклонений

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `ASSESSMENT__TOLERANCE_DAYS` | `3` | Допуск при сравнении с плановыми датами |
| `ASSESSMENT__STALE_DATA_DAYS` | `7` | Через сколько дней без снимков появляется отклонение «Данные устарели» |
| `ASSESSMENT__NO_PROGRESS_WINDOW_DAYS` | `5` | Максимальный интервал между наблюдениями пары для отклонения «Нет прогресса» |
| `ASSESSMENT__MIN_CONFIRMING_OBSERVATIONS` | `2` | Сколько дат с маркером нужно для высокой уверенности статуса |
| `ASSESSMENT__AS_OF_MODE` | `today` | Опорная дата: `today`, `last_observation`, `fixed` |
| `ASSESSMENT__AS_OF_OVERRIDE` | не задан | Дата `YYYY-MM-DD` для режима `fixed` |

Режим применяется при следующем пересчёте стройки. Уже посчитанные статусы сами не меняются. Рабочие дни (понедельник - пятница) в настройки не вынесены.

## Ассистент

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `ASSISTANT__RATE_LIMIT_PER_MIN` | `10` | Вопросов в минуту, общий счётчик |
| `ASSISTANT__TIMEOUT_S` | `130` | Ожидание ответа ML |
| `ASSISTANT__CONNECT_TIMEOUT_S` | `2` | |
| `ASSISTANT__MAX_REPORT_KB` | `512` | Предел размера отчёта |
| `ASSISTANT__STATUS_CACHE_S` | `30` | Кэш признака «ассистент доступен» |
| `ASSISTANT__STATUS_RETRY_S` | `5` | Кэш признака «недоступен» |
| `ASSISTANT__PARSE_TIMEOUT_S` | `600` | Ожидание разбора графика моделью, он идёт кусками по 40 строк |

## Языковая модель (сервис `ml`)

| Переменная | Смысл |
|---|---|
| `LLM_BASE_URL` | Адрес сервиса формата chat completions |
| `LLM_API_KEY` | Ключ |
| `LLM_MODEL` | Имя модели |

Если любая из трёх пуста, ассистент и разбор графика моделью отключены. Бэкенд эти три переменные получает пустыми намеренно.

## ML-сервис и веса

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `WEIGHTS` | `/weights/mocs_m_best.pt` | Путь к весам |
| `MAX_UPLOAD_BYTES` | `20971520` | Предел размера кадра |
| `DEMO_DETECTIONS` | не задана | Путь к выгрузке детекций для запуска без весов |
| `YOLO_OFFLINE` | `1` в образе | Запрет обращений Ultralytics в сеть |
| `YOLO_CONFIG_DIR` | `/tmp` в образе | Каталог настроек Ultralytics |
| `HF_TOKEN` | нет | Токен Hugging Face для загрузки весов |
| `HF_REPO` | `lct-7/lct7-construction-detector` | Репозиторий весов |

## Compose

Файл `deploy/versions.env`: `REGISTRY` (реестр образов), `BACKEND_TAG`, `FRONTEND_TAG`, `ML_TAG` (по умолчанию `latest`, для фиксации версии `sha-<короткий sha>` или `v<x.y.z>`). Подключается ключом `--env-file` в `makefile`.

## Фронтенд

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `VITE_USE_MOCKS` | `true` в `.env.development` и `.env.dist`, `false` в `.env.example` | Моки вместо бэкенда |
| `VITE_API_BASE_URL` | `/api` | Базовый путь API |
| `VITE_API_PROXY_TARGET` | `http://backend:8000` | Куда Vite проксирует `/api`, когда работает без Traefik |

Переменные `VITE_*` вшиваются в сборку, изменить их в готовом образе нельзя.
