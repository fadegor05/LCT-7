# Модель данных и C4: сервис контроля стройплощадки по кадрам

Источники: `product.md`, `architecture.md`, `mvp.md`, макеты «ЛЦТ — MVP: экраны» (Стройки, Новая стройка, Методика, Камеры, Обзор, Наблюдения, Отклонение).

Документ идёт по уровням C4: контекст → контейнеры → компоненты → динамика загрузки кадра. Своей нотации для данных у C4 нет, поэтому уровень кода (модель БД) дан ER-диаграммами Mermaid, разбитыми на три домена, и словарём таблиц.

## 1. C4 · Уровень 1: контекст

```mermaid
C4Context
  title Контекст: сервис контроля стройплощадки по кадрам (MVP)

  Person(eng, "Инженер / руководитель стройки", "Единственная роль, без авторизации. Заводит стройки, грузит график и кадры, правит методику, читает выводы, решает по гипотезам")

  System(lct, "LCT-7", "Сравнивает технику на кадрах с календарным графиком, выдаёт статусы этапов, отклонения и итог по объекту")

  System_Ext(files, "Файлы инженера", "График CSV/Excel, фото, видеофайлы")
  System_Ext(stream, "Источник стрима", "RTSP/HTTP-поток камеры. В демо тестовый источник или зацикленный файл (P1)")
  System_Ext(ref, "Справочник видов работ", "Иерархия видов работ. Загружается как начальные данные")
  System_Ext(gesn, "ГЭСН", "Нормы. В системе только номера расценок в правилах, без интеграции")

  Rel(eng, lct, "Работает через браузер", "HTTPS")
  Rel(eng, files, "Выбирает файлы")
  Rel(files, lct, "Загрузка графика и кадров", "HTTPS multipart")
  Rel(lct, stream, "Берёт кадры с периодичностью и опорный кадр для зоны", "RTSP/HTTP")
  Rel(ref, lct, "Начальные данные", "seed")
  Rel(gesn, lct, "Ссылки в правилах методики")
```

## 2. C4 · Уровень 2: контейнеры

```mermaid
C4Container
  title Контейнеры LCT-7 (Docker Compose, CPU ноутбука)

  Person(eng, "Инженер", "Браузер")
  System_Ext(stream, "Источник стрима", "Тестовый поток (P1)")

  System_Boundary(lct, "LCT-7") {
    Container(spa, "Веб-интерфейс", "React + Vite, дизайн-система LCT-7", "Стройки, создание стройки, Обзор, Наблюдения, Камеры, Методика, карточка отклонения")
    Container(api, "API", "Python, FastAPI", "REST. Стройки, импорт графика, методика, камеры и зоны, приём кадров, чтение выводов, решения по гипотезам")
    Container(ml, "ML-воркер", "Python, детектор 8 классов, OCR", "Время кадра: EXIF, затем штамп. Детекция техники. Признак годности кадра")
    Container(slicer, "Нарезчик", "Python, ffmpeg", "Видеофайл и поток в кадры с шагом. Клипы-доказательства (P1)")
    Container(gw, "Шлюз стрима", "Python", "Сессии стрима по камерам, периодичность, статус, опорный кадр (P1)")
    Container(engine, "Движок пересчёта", "Python, детерминированная функция", "Наблюдение за дату, активность техники, статусы этапов, отклонения, важность, итог")
    ContainerDb(pg, "БД", "PostgreSQL", "Стройки, график, методика, камеры, кадры, детекции, производные выводы, решения")
    ContainerDb(s3, "Объектное хранилище", "MinIO, S3", "Оригиналы кадров (неизменяемы), файлы графиков, клипы-доказательства")
    ContainerQueue(q, "Очередь задач", "Redis", "frame.process, video.slice, site.recalc")
  }

  Rel(eng, spa, "Использует", "HTTPS")
  Rel(spa, api, "JSON", "HTTPS/REST")
  Rel(api, pg, "Читает и пишет", "SQL")
  Rel(api, s3, "Кладёт оригиналы", "S3 API")
  Rel(api, q, "Ставит задачи")
  Rel(q, ml, "frame.process")
  Rel(q, slicer, "video.slice")
  Rel(q, engine, "site.recalc")
  Rel(ml, s3, "Читает кадр")
  Rel(ml, pg, "Пишет время кадра, детекции")
  Rel(slicer, s3, "Пишет кадры и клипы")
  Rel(slicer, pg, "Создаёт кадры")
  Rel(gw, stream, "Читает поток", "RTSP/HTTP")
  Rel(gw, slicer, "Передаёт поток на нарезку")
  Rel(engine, pg, "Читает план, правила, детекции. Пишет выводы")

  UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

## 3. C4 · Уровень 3: компоненты API и движка

```mermaid
C4Component
  title Компоненты API и движка пересчёта

  Container(spa, "Веб-интерфейс", "React")
  ContainerDb(pg, "БД", "PostgreSQL")
  ContainerDb(s3, "Хранилище", "MinIO")
  ContainerQueue(q, "Очередь", "Redis")

  Container_Boundary(api, "API (FastAPI)") {
    Component(sites, "Стройки", "router", "Черновик стройки, активация, список строек со сводкой")
    Component(imp, "Импорт графика", "service", "Разбор CSV/Excel по названиям, ошибки строк, ручные даты")
    Component(match, "Сопоставление и группировка", "service, pg_trgm", "Работа к справочнику: точно, затем нечётко. Группировка в крупные этапы по родителю. Проверка пересечений окон")
    Component(meth, "Методика", "service", "Комплект этапа из стартового набора, правка, вычисление маркеров по соседним этапам")
    Component(cams, "Камеры и зоны", "service", "Камеры, ссылка на стрим, полигон зоны в долях кадра")
    Component(ingest, "Приём кадров", "service", "Фото, видео, стрим в единую ленту. Кадры без времени, подтверждение времени, время начала клипа")
    Component(read, "Чтение выводов", "router", "Обзор, наблюдения, карточка отклонения, сквозной список отклонений")
    Component(dec, "Решения по гипотезам", "service", "Подтвердить / не подтверждается, история решений (P1)")
  }

  Container_Boundary(eng, "Движок пересчёта") {
    Component(agg, "Сведение", "module", "Наблюдение за дату: максимум по кадрам, наблюдаемость")
    Component(act, "Активность", "module", "Треки машин по камере, движение, положение к зоне: работает / простаивает / неизвестно")
    Component(stat, "Статусы", "module", "Ожидаемый этап, доказательство маркером, факт начала и конца, статус, интервал отставания")
    Component(devb, "Отклонения", "module", "Типы, гипотезы, шаблонные тексты, границы вывода, ключ отклонения")
    Component(sev, "Важность и уверенность", "module", "Уровни и потолки, причина уровня")
    Component(sum, "Итог", "module", "Итог по объекту, прогноз окончания (P1)")
  }

  Rel(spa, sites, "REST")
  Rel(spa, imp, "REST")
  Rel(spa, meth, "REST")
  Rel(spa, cams, "REST")
  Rel(spa, ingest, "REST")
  Rel(spa, read, "REST")
  Rel(spa, dec, "REST")
  Rel(imp, match, "Строки графика")
  Rel(match, meth, "Этапы для стартовых комплектов")
  Rel(ingest, s3, "Оригиналы")
  Rel(ingest, q, "frame.process")
  Rel(meth, q, "site.recalc")
  Rel(cams, q, "site.recalc")
  Rel(agg, act, "Детекции дня")
  Rel(act, stat, "Наблюдение с активностью")
  Rel(stat, devb, "Статусы")
  Rel(devb, sev, "Кандидаты отклонений")
  Rel(sev, sum, "Отклонения с важностью")
  Rel(sum, pg, "Пишет результат пересчёта")
  Rel(read, pg, "SQL")

  UpdateLayoutConfig($c4ShapeInRow="4", $c4BoundaryInRow="1")
```

## 4. C4 · Динамика: загрузка фото (UC-3, P0)

```mermaid
C4Dynamic
  title UC-3: загрузка фото и пересчёт

  Person(eng, "Инженер")
  Container(spa, "Веб-интерфейс", "React")
  Container(api, "API", "FastAPI")
  ContainerDb(s3, "Хранилище", "MinIO")
  ContainerDb(pg, "БД", "PostgreSQL")
  ContainerQueue(q, "Очередь", "Redis")
  Container(ml, "ML-воркер", "Python")
  Container(engine, "Движок пересчёта", "Python")

  Rel(eng, spa, "1. Добавить кадры: Фото, камера К-2")
  Rel(spa, api, "2. POST ingests + файлы")
  Rel(api, s3, "3. Оригиналы кадров")
  Rel(api, pg, "4. ingest, frame (processing_status = queued)")
  Rel(api, q, "5. frame.process на каждый кадр")
  Rel(q, ml, "6. Задача")
  Rel(ml, pg, "7. captured_at, date_source, детекции или time_status = needs_review")
  Rel(ml, q, "8. site.recalc (схлопывается на стройку)")
  Rel(q, engine, "9. Задача")
  Rel(engine, pg, "10. calc_run: наблюдения, статусы, отклонения, итог")
  Rel(spa, api, "11. Обзор и Наблюдения читают текущий calc_run")
```

## 5. Модель данных

### 5.1. Принципы

1. **Вход и производное разделены.** Вход меняет только инженер или конвейер распознавания: стройка, график, методика, камеры и зоны, кадры, детекции, решения по гипотезам. Производное целиком пересобирается движком: наблюдения, треки, статусы, отклонения, итог. Правка методики или зоны пересобирает производное без повторной обработки изображений.
2. **Производное привязано к пересчёту.** Каждая производная строка несёт `calc_run_id`. Экраны читают `site.current_calc_run_id`. Старые пересчёты удаляются фоном. Интерфейс не видит половину пересчёта, а два пересчёта одной стройки не смешиваются.
3. **Решения по гипотезам переживают пересчёт.** Отклонение пересоздаётся на каждом пересчёте, поэтому решение ссылается не на `deviation.id`, а на стабильный `deviation_key` (см. 5.6).
4. **Оригиналы неизменяемы.** Кадры и файлы лежат в S3, в БД только ключи. Детекции — вывод модели с `model_version`, вывод пользователем не правится.
5. **Пороги не в схеме.** Допуски, окна, пороги уверенности и наблюдаемости живут в конфигурации (раздел 9 `architecture.md`). В `calc_run.config_hash` записывается, с какой конфигурацией посчитано.
6. **Время.** Всё время — `timestamptz`. Дата наблюдения считается в часовом поясе стройки (`site.timezone`): Березники — `Asia/Yekaterinburg`.

### 5.2. Домен «Стройка, график, методика»

```mermaid
erDiagram
  app_user ||--o{ site : "создал"
  site ||--o{ schedule_import : "загрузки графика"
  schedule_import ||--o{ schedule_work : "строки файла"
  schedule_import ||--o{ import_issue : "проблемы разбора"
  site ||--o{ stage : "крупные этапы"
  stage ||--o{ schedule_work : "вошедшие работы"
  work_type ||--o{ work_type : "родитель"
  work_type ||--o{ stage : "сопоставлен"
  work_type ||--o{ schedule_work : "сопоставлена"
  work_type ||--o{ work_type_kit_item : "стартовый комплект"
  stage ||--o{ equipment_kit : "комплект (в MVP один)"
  equipment_kit ||--|{ kit_rule : "машины"
  equipment_group ||--o{ equipment_class : "классы группы"
  equipment_class ||--o{ kit_rule : "правило на класс"
  equipment_group ||--o{ kit_rule : "правило на группу"
  equipment_class ||--o{ work_type_kit_item : ""
  equipment_group ||--o{ work_type_kit_item : ""

  app_user {
    uuid id PK
    text full_name "подпись решений, авторизации нет"
  }
  site {
    uuid id PK
    text name "Жилой дом · Березники"
    text address "адрес или обозначение"
    site_object_type object_type "housing | education | health | other"
    work_days work_days "mon_fri | mon_sat | all"
    text timezone "Asia/Yekaterinburg"
    site_state state "draft | active"
    uuid current_calc_run_id FK "текущий пересчёт"
    uuid created_by FK
    timestamptz created_at
    timestamptz activated_at "нажата Создать стройку"
  }
  schedule_import {
    uuid id PK
    uuid site_id FK
    text file_name "grafik_berezniki.xlsx"
    text s3_key
    int file_size
    int works_total "38 работ в файле"
    int rows_failed
    bool is_current "одна текущая на стройку"
    timestamptz uploaded_at
  }
  schedule_work {
    uuid id PK
    uuid import_id FK
    uuid stage_id FK "null, если не разобрана"
    int row_number "строка файла"
    text name
    date planned_start "null, если дат нет"
    date planned_end
    uuid work_type_id FK "лист справочника"
    int sort_no
  }
  import_issue {
    uuid id PK
    uuid import_id FK
    issue_kind kind "row_unparsed | no_dates | fuzzy_match | window_overlap | no_marker"
    int row_number
    uuid stage_id FK
    text message
    bool blocking "блокирует активацию"
    timestamptz resolved_at
  }
  stage {
    uuid id PK
    uuid site_id FK
    int seq_no UK "порядок, план последовательный"
    text name "Разработка котлована"
    uuid work_type_id FK "родитель уровня 1-2"
    match_kind match_kind "exact | fuzzy | manual | none"
    numeric match_score "0.74"
    timestamptz match_confirmed_at
    date planned_start "min по работам или вручную"
    date planned_end
    dates_source dates_source "works | manual"
    bool equipment_check "Проверяется / Не проверяется"
    text not_checked_reason
    bool has_marker "вычисляется"
  }
  work_type {
    uuid id PK
    uuid parent_id FK
    smallint level "1-3"
    text code
    text name
    site_object_type_arr object_types "применимые типы объекта"
    bool equipment_verifiable
    text not_verifiable_reason
  }
  work_type_kit_item {
    uuid id PK
    uuid work_type_id FK
    text equipment_class FK "класс или группа"
    text equipment_group FK
    rule_kind rule_kind
    text source_ref "ГЭСН номер или по смыслу работы"
    smallint typical_qty
  }
  equipment_kit {
    uuid id PK
    uuid stage_id FK "UNIQUE в MVP, снять в P2"
    smallint kit_no
  }
  kit_rule {
    uuid id PK
    uuid kit_id FK
    text equipment_class FK "ровно одно из двух"
    text equipment_group FK
    rule_kind rule_kind "normative | logical | auxiliary"
    text source_ref "ГЭСН [номер]"
    smallint typical_qty "необязательно"
    bool is_marker "вычисляется"
    timestamptz updated_at
  }
  equipment_class {
    text code PK "excavator, dump_truck..."
    text name_ru
    text group_code FK
  }
  equipment_group {
    text code PK "earthmoving | transport | lifting | concrete"
    text name_ru
  }
```

### 5.3. Домен «Камеры и кадры»

```mermaid
erDiagram
  site ||--o{ camera : "камеры объекта"
  camera ||--o{ ingest : "загрузки и сессии"
  site ||--o{ ingest : ""
  ingest ||--o{ frame : "кадры"
  camera ||--o{ frame : "кадры камеры"
  ingest ||--o{ evidence_clip : "клипы-доказательства"
  frame ||--o{ detection : "детекции"
  equipment_class ||--o{ detection : ""
  evidence_clip |o--o{ frame : "кадры из клипа"

  camera {
    uuid id PK
    uuid site_id FK
    text name UK "К-1, уникально в стройке"
    text stream_url "необязательно"
    jsonb zone_polygon "[[x,y],...] в долях 0-1, от 3 точек, null = зоны нет"
    timestamptz zone_updated_at
    timestamptz created_at
  }
  ingest {
    uuid id PK
    uuid site_id FK
    uuid camera_id FK
    source_type source_type "photo | video | stream"
    ingest_state state "queued | running | done | stopped | failed"
    int slice_step_sec "видео 60-1800, стрим 300-1800"
    text original_name "имя файла, оригинал видео не хранится"
    timestamptz clip_started_at "время начала клипа, null = нужно ввести"
    date_source clip_start_source "video_meta | manual"
    int frames_count
    timestamptz last_frame_at "для стрима"
    timestamptz started_at
    timestamptz stopped_at
  }
  frame {
    uuid id PK
    uuid site_id FK
    uuid camera_id FK "выбирается при загрузке"
    uuid ingest_id FK
    uuid clip_id FK "для видео и стрима"
    source_type source_type "photo | video | stream"
    text s3_key
    text sha256 UK "дубль в стройке не принимается"
    int width
    int height
    int video_offset_ms "смещение от начала клипа"
    timestamptz captured_at "null, пока время не известно"
    date_source date_source "exif | stamp | manual | video | stream"
    time_state time_state "ok | needs_review"
    time_issue time_issue "stamp_unrecognized | no_metadata | stamp_cropped | stamp_low_conf | clip_no_start"
    text stamp_text "распознанный штамп"
    numeric stamp_confidence
    jsonb exif
    processing_state processing_state "queued | processing | done | failed"
    bool is_daylight
    bool is_usable "годный кадр для наблюдаемости"
    int detections_count "0 = нет техники, кадр остаётся"
    text model_version
    timestamptz uploaded_at
  }
  evidence_clip {
    uuid id PK
    uuid ingest_id FK
    text s3_key
    timestamptz started_at
    int duration_ms
  }
  detection {
    uuid id PK
    uuid frame_id FK
    text equipment_class FK
    numeric confidence "0-1, наружу уровнем"
    real bbox_x "доли кадра 0-1"
    real bbox_y
    real bbox_w
    real bbox_h
    text model_version
  }
```

### 5.4. Домен «Выводы» (производное, пересобирается движком)

```mermaid
erDiagram
  site ||--o{ calc_run : "пересчёты"
  calc_run ||--o| site_summary : "итог"
  calc_run ||--o{ observation : "наблюдения"
  observation ||--o{ observation_equipment : "техника на площадке"
  observation ||--o{ equipment_track : "треки машин"
  equipment_track ||--|{ track_detection : ""
  detection ||--o{ track_detection : ""
  camera ||--o{ equipment_track : ""
  calc_run ||--o{ stage_status : "статусы этапов"
  stage ||--o{ stage_status : ""
  calc_run ||--o{ stage_forecast : "прогноз (P1)"
  calc_run ||--o{ deviation : "отклонения"
  stage ||--o{ deviation : ""
  kit_rule |o--o{ deviation : "сработавшее правило"
  deviation ||--o{ deviation_evidence : "кадры-доказательства"
  frame ||--o{ deviation_evidence : ""
  equipment_track |o--o{ deviation : "машина-доказательство"
  site ||--o{ hypothesis_decision : "решения"
  app_user ||--o{ hypothesis_decision : "решил"

  calc_run {
    uuid id PK
    uuid site_id FK
    recalc_trigger trigger "frames | methodology | zone | time_confirmed | schedule | stale_check"
    calc_state state "running | done | failed"
    text config_hash "с какими порогами"
    text engine_version
    timestamptz started_at
    timestamptz finished_at
  }
  site_summary {
    uuid calc_run_id PK
    uuid site_id FK
    verdict verdict "behind | no_deviations | insufficient_data"
    smallint delay_days_min "4"
    smallint delay_days_max "null = от 4 дней"
    uuid measured_stage_id FK
    text explanation "шаблон: по какому этапу, даты, техника"
    level observability "low | medium | high"
    smallint cameras_total
    smallint cameras_reporting "4 из 4"
    timestamptz last_frame_at
    int frames_total
    int frames_without_time
    smallint data_age_days "для Данные устарели"
    smallint critical_count
    smallint attention_count
  }
  observation {
    uuid id PK
    uuid calc_run_id FK
    uuid site_id FK
    date obs_date UK "UNIQUE с calc_run_id"
    uuid expected_stage_id FK "Этап: ..."
    int frames_total
    int frames_usable
    smallint cameras_with_usable
    level observability
    bool is_workday
  }
  observation_equipment {
    uuid observation_id PK
    text equipment_class PK
    smallint min_count "не менее N, максимум по кадрам"
    activity activity "working | idle | unknown"
    bool activity_hypothesis
    text basis_text "основание вывода"
  }
  equipment_track {
    uuid id PK
    uuid observation_id FK
    uuid camera_id FK
    text equipment_class FK
    motion motion "yes | no | no_pair | view_changed"
    zone_position zone_position "inside | outside | not_set"
    activity activity
    level confidence
    timestamptz first_seen_at
    timestamptz last_seen_at
    smallint frames_in_series
  }
  track_detection {
    uuid track_id PK
    uuid detection_id PK
  }
  stage_status {
    uuid id PK
    uuid calc_run_id FK
    uuid stage_id FK
    stage_status_value status "ahead | on_track | behind | not_started | not_observed | not_checked | not_due"
    evidence_state evidence "marker_confirmed | compatible | none | unknown"
    date fact_start_lo "последняя дата без маркера"
    date fact_start_hi "первая дата с маркером"
    date fact_end "по смене маркеров"
    bool end_confirmed
    text fact_label "с 06.09, идёт / не найден"
    smallint delay_days_min
    smallint delay_days_max
    level confidence
    text confidence_reason
    text basis_text "Экскаватор виден после планового конца"
  }
  stage_forecast {
    uuid id PK
    uuid calc_run_id FK
    uuid stage_id FK
    date forecast_end_lo
    date forecast_end_hi
    level confidence "не выше medium"
  }
  deviation {
    uuid id PK
    uuid calc_run_id FK
    uuid site_id FK
    text deviation_key "стабильный ключ, см. 5.6"
    deviation_type type "missing_equipment | stage_mismatch | stale_data | idle | extra_equipment | out_of_zone | no_progress"
    bool is_hypothesis
    severity severity "critical | attention"
    level confidence
    text confidence_reason
    uuid stage_id FK "null для Данные устарели"
    date period_start
    date period_end
    smallint delay_days_min
    smallint delay_days_max
    text title "Каток не найден"
    text expected_text
    text observed_text
    text limits_text "Чего это не доказывает"
    text severity_reason
    text cause_key "ключ отклонения-причины"
    text cause_text "Возможная причина"
    uuid rule_id FK "правило методики"
    text service_rule_code "правило сервиса, например idle_motion_zone"
    uuid track_id FK
    text equipment_class FK
    uuid camera_id FK
    timestamptz detected_at "для сортировки по свежести"
  }
  deviation_evidence {
    uuid deviation_id PK
    uuid frame_id PK
    evidence_role role "evidence | zone"
    smallint sort_no
    text caption "К-1: катка нет"
  }
  hypothesis_decision {
    uuid id PK
    uuid site_id FK
    text deviation_key "не FK: переживает пересчёт"
    decision decision "confirmed | rejected"
    text comment "ждёт погрузки"
    uuid decided_by FK
    timestamptz decided_at
    timestamptz superseded_at "null = действующее"
  }
```

### 5.5. Словарь таблиц

**Стройка, график, методика**

| Таблица | Назначение | Ключевые ограничения и индексы |
|---|---|---|
| `app_user` | Один пользователь без авторизации, нужен для подписи решений («Решил: инженер [ФИО]») | seed одной строкой |
| `site` | Стройка. `draft` существует, пока инженер на шагах 1–2 создания, в списке строек не показывается. `active` — после «Создать стройку» | переход `draft → active` только без блокирующих `import_issue` |
| `schedule_import` | Загруженный файл графика и статистика разбора. «Заменить файл» создаёт новую загрузку, прежняя становится не текущей | partial unique `(site_id) WHERE is_current` |
| `schedule_work` | Мелкая работа из файла. Нужна только для группировки и сопоставления, техника на неё не задаётся | index `(stage_id)` |
| `import_issue` | Проблемы блока «Что нужно поправить до создания»: нераспознанные строки, этап без дат, нечёткое сопоставление, пересечение окон, этап без маркера | index `(import_id) WHERE resolved_at IS NULL` |
| `stage` | Крупный этап — единица контроля. Окно считается по работам или задаётся вручную | unique `(site_id, seq_no)`; для `active` исключающее ограничение `EXCLUDE USING gist (site_id WITH =, daterange(planned_start, planned_end, '[]') WITH &&)` через `btree_gist` |
| `work_type` | Справочник видов работ, иерархия уровней 1–3, применимость к типам объекта | trigram-индекс `gin (name gin_trgm_ops)` для нечёткого сопоставления |
| `work_type_kit_item` | Стартовые комплекты на 8–10 крупных этапов, составляем сами | check: ровно одно из `equipment_class`, `equipment_group` |
| `equipment_kit` | Комплект этапа. В MVP один на этап; таблица оставлена ради альтернативных комплектов P2 | unique `(stage_id)` в MVP |
| `kit_rule` | Машина или группа в комплекте: вид правила, источник, типовое количество. Минимум для подтверждения всегда 1 и не хранится | check: ровно одно из класса и группы; check: `rule_kind = 'logical' → NOT is_marker` |
| `equipment_class` / `equipment_group` | Восемь классов из ТЗ и четыре группы: землеройная, транспортная, подъёмная, бетонная | seed |

**Камеры и кадры**

| Таблица | Назначение | Ключевые ограничения и индексы |
|---|---|---|
| `camera` | Камера объекта. Зона — один полигон на камеру, в долях кадра. Опорный кадр для рисования не сохраняется | unique `(site_id, name)`; check `jsonb_array_length(zone_polygon) >= 3` |
| `ingest` | Одна загрузка фото, один видеофайл или одна сессия стрима. Общая сущность для трёх читателей одного нарезчика | index `(camera_id, source_type, state)` |
| `frame` | Кадр — единица входа для любого источника. Кадр без времени (`time_state = needs_review`) хранится, показывается в блоке «Без даты или времени» и не участвует в расчётах | index `(site_id, captured_at)`, `(camera_id, captured_at)`; partial `(site_id) WHERE time_state = 'needs_review'`; unique `(site_id, sha256)` |
| `evidence_clip` | Короткий клип-доказательство из видео или стрима. Оригинал видео не хранится | — |
| `detection` | Рамка техники на кадре. Кадр с `detections_count = 0` — тоже наблюдение | index `(frame_id)` |

**Выводы**

| Таблица | Назначение | Ключевые ограничения и индексы |
|---|---|---|
| `calc_run` | Один пересчёт стройки. Пересчёты одной стройки идут последовательно; `site.current_calc_run_id` переключается только на завершённый | advisory-lock на `site_id` в движке |
| `site_summary` | Итог и «Состояние данных» для Обзора и строки в списке строек | PK = `calc_run_id` |
| `observation` | Наблюдение за дату: кадры, камеры с годными кадрами, наблюдаемость, ожидаемый этап | unique `(calc_run_id, obs_date)` |
| `observation_equipment` | «Техника на площадке»: класс, «не менее N», активность и основание | PK `(observation_id, equipment_class)` |
| `equipment_track` | Машина, сопоставленная между соседними кадрами одной камеры: движение, положение к зоне, активность | index `(observation_id, camera_id)` |
| `track_detection` | Какие детекции составили трек. Детекции при этом не меняются | PK `(track_id, detection_id)` |
| `stage_status` | Строка таблицы этапов: статус, доказательство, факт по маркеру, интервал отставания, уверенность | unique `(calc_run_id, stage_id)` |
| `stage_forecast` | Прогноз окончания, подписан как оценка (P1) | unique `(calc_run_id, stage_id)` |
| `deviation` | Отклонение со всеми полями карточки. Тексты собраны шаблонами при пересчёте | index `(calc_run_id, severity, detected_at DESC)`; check `is_hypothesis → severity = 'attention' AND confidence <> 'high'` |
| `deviation_evidence` | Кадры-доказательства; у гипотезы про положение машины — кадр с зоной камеры (`role = zone`) | PK `(deviation_id, frame_id)` |
| `hypothesis_decision` | Решение инженера по гипотезе. «Изменить решение» закрывает текущее (`superseded_at`) и пишет новое, история сохраняется | partial unique `(site_id, deviation_key) WHERE superseded_at IS NULL` |

### 5.6. Ключ отклонения

`deviation_key` — детерминированная строка, по которой одно и то же отклонение узнаётся в разных пересчётах:

```
{type}:{stage_id | -}:{equipment_class | equipment_group | -}:{camera_id | -}:{episode_start}
```

`episode_start` — первая дата эпизода отклонения. Конец периода в ключ не входит: эпизод растёт с новыми кадрами, а решение инженера должно остаться при нём. Если эпизод прервался и начался снова, это новое отклонение с новым ключом, и решение по нему нужно заново. Пример: `idle:9f1c…:dump_truck:К-2:2026-09-17`.

Чтение карточки гипотезы: `deviation LEFT JOIN hypothesis_decision ON site_id и deviation_key AND superseded_at IS NULL`. Нет решения — «Ждёт решения». `rejected` — отклонение уходит в архив: из списков и отчёта исключается, но в БД остаётся. На `site_summary` решение не влияет.

### 5.7. Перечисления

| Тип | Значения | Подпись в интерфейсе |
|---|---|---|
| `site_object_type` | housing, education, health, other | Жильё, Образование, Здравоохранение, Другое |
| `work_days` | mon_fri, mon_sat, all | Пн–Пт, Пн–Сб, Ежедневно |
| `source_type` | photo, video, stream | Фото, Видео, Стрим |
| `date_source` | exif, stamp, manual, video, stream | Метаданные, Штамп, Вручную, Видео, Поток |
| `time_issue` | stamp_unrecognized, no_metadata, stamp_cropped, stamp_low_conf, clip_no_start | Штамп не распознан, Метаданных нет, Штамп обрезан, Штамп читается неуверенно, Клип без времени начала |
| `rule_kind` | normative, logical, auxiliary | Нормативная, Логическая, Вспомогательная |
| `match_kind` | exact, fuzzy, manual, none | Справочник · точное, Справочник · нечёткое · N%, Вручную, Не сопоставлен |
| `stage_status_value` | ahead, on_track, behind, not_started, not_observed, not_checked, not_due | Опережение, В графике, Отставание, Не начата, Не наблюдалось, Не проверяется по технике, Не начата (not_due и not_started одним бейджем) |
| `evidence_state` | marker_confirmed, compatible, none, unknown | Подтверждено маркером, Совместимо, Нет, Неизвестно |
| `activity` | working, idle, unknown | Работает, Простаивает, Неизвестно |
| `motion` | yes, no, no_pair, view_changed | — (основание вывода) |
| `zone_position` | inside, outside, not_set | Внутри зоны, Вне зоны, Зона не задана |
| `deviation_type` | missing_equipment, stage_mismatch, stale_data, idle, extra_equipment, out_of_zone, no_progress | Нет нужной техники, Несоответствие этапу, Данные устарели, Простой техники, Лишняя техника, Вне рабочей зоны, Нет прогресса |
| `severity` | critical, attention | Критично, Внимание |
| `level` | high, medium, low | Высокая, Средняя, Низкая (уверенность и наблюдаемость) |
| `verdict` | behind, no_deviations, insufficient_data | Отставание X–Y дней, Отклонений не выявлено, Недостаточно данных |
| `decision` | confirmed, rejected | Подтвердить (простой), Не подтверждается (простоя не было) |

### 5.8. Что покрывает какой сценарий

| UC | Пишет | Читает |
|---|---|---|
| UC-1 Завести стройку | `site`, `schedule_import`, `schedule_work`, `stage`, `import_issue` | `work_type` |
| UC-2 Методика | `equipment_kit`, `kit_rule`, `stage.equipment_check` → `calc_run` | `work_type_kit_item`, `schedule_work` (состав этапа) |
| UC-3 Загрузить кадры | `ingest`, `frame`, `evidence_clip`, `detection` → `calc_run` | `camera` |
| UC-4 Обзор | — | `site_summary`, `deviation`, `stage_status`, `observation`, `hypothesis_decision` |
| UC-5 Карточка отклонения | — | `deviation`, `deviation_evidence`, `kit_rule`, `camera.zone_polygon`, `hypothesis_decision` |
| UC-6 Камеры и зоны | `camera` → `calc_run` | `frame` (число кадров) |
| UC-7 Наблюдения | — | `observation`, `observation_equipment`, `equipment_track`, `frame`, `detection` |
| UC-8 Кадры без времени | `frame.captured_at`, `ingest.clip_started_at` → `calc_run` | `frame WHERE time_state = needs_review` |
| UC-9 Стройки | — | `site`, `site_summary`, `deviation` по текущим пересчётам всех строек |
| UC-10 Решение по гипотезе | `hypothesis_decision` | `deviation` |
