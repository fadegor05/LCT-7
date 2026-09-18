# 0. Статус исходных предпосылок

| Метка | Содержание |
|---|---|
| **ФАКТ** | Данные и полное ТЗ планируются к публикации 15.09.2026; на 09.09.2026 они недоступны. |
| **ФАКТ** | Вход предполагает изображения или видеопоток со стационарных камер строительной площадки. |
| **ФАКТ** | Требуется обнаруживать технику, оценивать её количество, присутствие и поведение, сопоставлять наблюдения с календарным графиком и выявлять отклонения. |
| **НЕИЗВЕСТНО** | Частота кадров, разрешение, число камер, синхронизация, геометрия, ночная съёмка, погода, длительность архива, наличие timestamp/GPS/метаданных. |
| **НЕИЗВЕСТНО** | Классы техники, наличие людей/материалов/зон работ в разметке, формат и детализация календарного графика. |
| **НЕИЗВЕСТНО** | Есть ли размеченные треки, состояния `работает/припаркована`, виды работ, прогресс и реальные отклонения. |
| **ГИПОТЕЗА H1** | Основная полезная информация — не единичная детекция, а устойчивые пространственно-временные паттерны техники относительно рабочих зон. |
| **ГИПОТЕЗА H2** | На хакатоне надёжнее выводить ограниченный набор наблюдаемых активностей и признаков прогресса, чем пытаться распознавать весь строительный процесс end-to-end. |
| **ГИПОТЕЗА H3** | Календарный план должен участвовать в сравнении и, возможно, в отдельном plan-aware пути, но не должен определять основной независимый вывод о факте. |

Все дальнейшие параметры окон, порогов и классов являются **конфигурацией**, а не утверждениями о будущем датасете.

---

# 1. Целевая декомпозиция

```text
Camera/Image
    ↓
Perception
    ↓ DetectionObservation + FrameQuality
Temporal aggregation
    ↓ Tracklet / TemporalEvidence
Site state
    ↓ SiteStateDistribution
Activity/work-stage inference
    ↓ ObservedSignature + ActivityPosterior
Schedule matching
    ↓ ConformityAssessment
Deviation detection
    ↓ DeviationCandidate
Alerting
    ↓ Alert / Dashboard state / Explanation
```

Принцип: каждый уровень принимает версионированный контракт, выдаёт не только оценку, но и:

- неопределённость;
- показатель достаточности данных;
- причины деградации;
- ссылку на исходные наблюдения;
- версию модели и конфигурации;
- явное значение `unknown`, не подменяемое нулём.

## 1.1 Общие типы

```text
UUID             := string
TimestampUTC     := string, ISO-8601 UTC
Probability      := float32 ∈ [0,1]
Score            := float32 ∈ [0,1]
BBoxXYXY         := float32[4], нормированные координаты
Polygon          := float32[N,2], нормированные координаты либо координаты площадки
Distribution[K]  := float32[K], сумма = 1
CountDistribution:= map<int, Probability>
Interval         := {start: TimestampUTC?, end: TimestampUTC?}
EvidenceRef      := {camera_id, frame_id, timestamp?, bbox?, artifact_uri?}
```

Правило семантики:

- `0` означает наблюдаемое отсутствие;
- `null`/`unknown` означает отсутствие достаточного наблюдения;
- `not_applicable` означает неприменимость признака;
- все вероятности должны сопровождаться версией калибратора.

---

# 2. Контракты и архитектура по уровням

## 2.1 Входной контракт `FrameEnvelope`

| Поле | Тип | Обязательность | Смысл |
|---|---:|---:|---|
| `frame_id` | `UUID` | да | Уникальный кадр |
| `camera_id` | `string` | да | Источник |
| `image_uri` или `image_bytes` | `string/bytes` | да | Изображение |
| `capture_ts` | `TimestampUTC?` | нет | Время съёмки |
| `ingest_ts` | `TimestampUTC` | да | Время получения |
| `sequence_no` | `int64?` | нет | Порядок кадров |
| `width`, `height` | `int32` | да | Размер |
| `fps_nominal` | `float32?` | нет | Заявленная частота |
| `camera_pose_id` | `string?` | нет | Версия геометрии |
| `metadata` | `map<string, scalar>` | нет | EXIF/источник |

Частота:

- сценарий **A**: 10–25 сообщений/с на камеру до семплирования;
- сценарий **B**: одно сообщение раз в 5–30 минут;
- сценарий **C**: нерегулярно; `capture_ts` может отсутствовать.

До ML необходимы проверки дубликатов, битых кадров, timestamp, поворота изображения и смены ракурса.

---

## 2.2 Perception

### Назначение

Извлечь из каждого кадра объекты, визуальные признаки сцены, качество наблюдения и признаки применимости модели.

### Выход `PerceptionFrame`

| Поле | Тип | Частота |
|---|---:|---|
| `frame_id`, `camera_id`, `capture_ts?` | идентификаторы | на обработанный кадр |
| `detections` | `Detection[]` | на кадр |
| `scene_features` | `float32[D]?` | на кадр/каждый N-й кадр |
| `frame_quality` | `FrameQuality` | на кадр |
| `camera_shift` | `{dx,dy,scale,rotation,confidence}` | на кадр относительно эталона |
| `ood_score` | `Score` | на кадр |
| `model_version` | `string` | на кадр |

`Detection`:

| Поле | Тип |
|---|---:|
| `detection_id` | `UUID` |
| `class_probs` | `Distribution[K]` |
| `objectness` | `Probability` |
| `bbox` | `BBoxXYXY` |
| `mask_rle` | `string?` |
| `embedding` | `float16[D]?` |
| `orientation` | `float32?` |
| `occlusion_prob` | `Probability?` |
| `truncation_prob` | `Probability?` |
| `working_visual_cues` | `map<string, Probability>?` |
| `uncertainty` | `{aleatoric: float32, epistemic: float32?}` |
| `calibration_version` | `string` |

`FrameQuality`:

```text
blur_score, darkness_score, glare_score, precipitation_score?,
occlusion_score, compression_score, usable_fraction: float32 [0,1]
status: enum{usable,degraded,unusable,unknown}
```

### Альтернативы

| Подход | Качество | Стоимость | Данные | Риск хакатона |
|---|---|---|---|---|
| **P1. Предобученный open-vocabulary/универсальный detector + prompt/classes** | Быстрый старт; нестабильная тонкая классификация техники | Низкая | Достаточно изображений для проверки | Низкий |
| **P2. Fine-tuning one-stage detector на локальной разметке** | Обычно лучший баланс precision/recall и скорости | Средняя | Нужны bbox и покрытие условий | Средний |
| **P3. Detector + segmentation + специализированные heads/embeddings** | Лучше при перекрытиях, малых объектах и анализе позы | Высокая | Маски/сильная разметка или псевдоразметка | Высокий |

Выбор:

- **A, плотное видео:** P2; добавить embeddings/segmentation из P3 только при доказанной пользе.
- **B, time-lapse:** P2, поскольку ошибки нельзя исправить плотной временной агрегацией; P1 — baseline.
- **C, отдельные фото:** P2 или P1 при отсутствии разметки; обязательно `ood_score` и frame-quality gate.

**НЕИЗВЕСТНО:** пригодны ли классы публичных датасетов; локальная техника может визуально отличаться.

---

## 2.3 Temporal aggregation

### Назначение

Устранить кадровый шум, связать наблюдения одного объекта, оценить длительность присутствия, движение и устойчивость признаков.

### Выход `TemporalEvidence`

| Поле | Тип | Частота |
|---|---:|---|
| `window_id` | `UUID` | на окно |
| `camera_id` | `string` | на окно |
| `interval` | `Interval` | на окно |
| `duration_s` | `float32?` | на окно |
| `tracklets` | `Tracklet[]` | на окно |
| `count_distributions` | `map<class, CountDistribution>` | на окно |
| `coverage` | `float32 [0,1]` | на окно |
| `effective_sample_size` | `float32` | на окно |
| `quality_summary` | `FrameQualityAggregate` | на окно |
| `unknown_reasons` | `string[]` | на окно |

`Tracklet`:

```text
track_id: UUID
class_posterior: Distribution[K]
observations: [{ts?, bbox, class_probs, detection_confidence, evidence_ref}]
first_seen_ts?, last_seen_ts?: TimestampUTC
presence_probability: Probability
motion: {
  displacement_px?, displacement_world_m?,
  velocity_distribution?, direction_distribution?,
  stationary_probability: Probability
}
zone_occupancy: map<zone_id, Probability>
activity_cues: map<cue_name, Probability>
association_confidence: Probability
```

Рекомендуемые частоты агрегации:

- **A:** inference 2–10 FPS после адаптивного семплирования; короткое окно 10–60 с, отчёт состояния каждые 10–30 с; длинное окно 5–15 мин.
- **B:** обновление на каждый новый кадр; окно 2–12 последовательных кадров, фактический горизонт 10 мин–6 ч.
- **C:** temporal output вырождается в `SingleFrameEvidence`; длительности и скорости равны `unknown`.

### Альтернативы

| Подход | Качество | Стоимость | Требования | Риск |
|---|---|---|---|---|
| **T1. EMA/robust counting без tracking** | Хорош для устойчивых количеств, слаб для поведения | Низкая | Только timestamp желательно | Низкий |
| **T2. Tracking-by-detection: Kalman + IoU + appearance** | Хорош для движения, присутствия и дедупликации | Средняя | Плотное видео и стабильная камера | Средний |
| **T3. Вероятностная агрегация/particle filter по объектам и count distributions** | Лучше отражает пропуски и неоднозначность | Высокая | Калиброванные вероятности, модель переходов | Высокий |

Выбор:

- **A:** T2 + вероятностное сглаживание счётчиков из T3.
- **B:** T1 с сопоставлением по зонам и appearance; не использовать обычный Kalman как доказательство непрерывного трека.
- **C:** T1 только внутри одного кадра; между фотографиями агрегировать лишь при доказанной последовательности и метаданных.

---

## 2.4 Site state

### Назначение

Перевести camera-centric наблюдения в семантическое состояние площадки: зоны, типы техники, активность, качество обзора, вероятностные количества.

### Выход `SiteStateDistribution`

| Поле | Тип | Частота |
|---|---:|---|
| `site_state_id` | `UUID` | каждое окно |
| `site_id` | `string` | каждое окно |
| `interval` | `Interval` | каждое окно |
| `zone_states` | `ZoneState[]` | каждое окно |
| `global_counts` | `map<class, CountDistribution>` | каждое окно |
| `camera_coverage` | `map<camera_id,float32>` | каждое окно |
| `state_quality` | `Score` | каждое окно |
| `fusion_assumptions` | `string[]` | каждое окно |
| `evidence_refs` | `EvidenceRef[]` | каждое окно |
| `model_version` | `string` | каждое окно |

`ZoneState`:

```text
zone_id: string
zone_type: enum{work,storage,parking,access,unknown}
visibility_probability: Probability
equipment_count: map<class, CountDistribution>
active_count: map<class, CountDistribution>
presence_probability: map<class, Probability>
flow_in, flow_out: map<class, distribution>?
motion_energy: distribution?
spatial_occupancy: distribution?
scene_change_features: map<string, distribution>
unknown_fields: string[]
```

Геометрия может быть:

1. ручные полигоны на изображении;
2. гомография на условную карту;
3. полноценная multi-camera world calibration.

### Альтернативы

| Подход | Качество | Стоимость | Требования | Риск |
|---|---|---|---|---|
| **S1. Состояние по камере без world fusion** | Надёжно при одной камере; возможны дубли между камерами | Низкая | ROI/зоны на изображении | Низкий |
| **S2. Rule-based zone graph + вероятностная дедупликация камер** | Хороший баланс интерпретируемости | Средняя | Перекрытия, карта зон, ручная настройка | Средний |
| **S3. Learned scene graph / spatiotemporal GNN** | Потенциально лучше сложных связей | Высокая | Много размеченных эпизодов и стабильная схема | Высокий |

Выбор:

- **A:** S2, если несколько камер; S1, если одна.
- **B:** S2 с большими временными допусками, но без утверждения непрерывного пути между кадрами.
- **C:** S1; вывод только о видимой части кадра. Fusion фотографий допустим лишь при известной камере/ракурсе.

---

## 2.5 Activity/work-stage inference

### Назначение

Оценить наблюдаемую активность и признаки стадии работ независимо от календарного плана.

### Выход `ObservedSignature`

```text
signature_id: UUID
site_id: string
interval: Interval
equipment_presence: map<class, Distribution{count bins}>
equipment_active: map<class, Distribution{count bins}>?
zone_activity: map<zone_id, Distribution[activity_class]>
motion_profile: map<zone_id, Distribution[motion_class]>?
material_change: map<zone_id, Distribution[change_class]>?
visual_progress_features: map<feature_name, distribution>?
activity_posterior: Distribution[A]
stage_evidence_posterior: Distribution[W]
data_sufficiency: Score
observability_mask: map<feature_name, bool>
feature_uncertainty: map<feature_name, distribution parameters>
evidence_refs: EvidenceRef[]
model_version: string
```

Здесь:

- `A` — наблюдаемые активности, например `excavation_like`, `lifting_like`, `hauling_like`, `idle`, `unknown`;
- `W` — визуально различимые стадии, определяемые только после знакомства с ТЗ;
- `stage_evidence_posterior` не использует плановый срок задачи.

Частота:

- **A:** активности каждые 30–60 с; стадия/прогресс каждые 5–30 мин.
- **B:** обновление на кадр; стадия — после накопления нескольких кадров или ежедневно.
- **C:** на фотографию; временное поведение и прогресс — `unknown`.

### Альтернативы

| Подход | Качество | Стоимость | Требования | Риск |
|---|---|---|---|---|
| **A1. Экспертные правила по технике, зонам, движению и change features** | Интерпретируемо, устойчиво на малых данных | Низкая–средняя | Семантика зон и Expected Signatures | Низкий |
| **A2. Supervised classifier: gradient boosting/MLP/TCN по агрегированным признакам** | Выше при качественной разметке активностей | Средняя | Размеченные временные окна | Средний |
| **A3. Video encoder/transformer или multimodal model по клипам** | Может распознать сложные действия | Высокая | Много клипов, GPU, контроль domain shift | Высокий |

Выбор:

- **A:** A1 как основной объяснимый baseline; A2 при наличии labels; A3 только как дополнительный evidence source.
- **B:** A1 + change detection; A2 по последовательности редких кадров, если достаточно истории.
- **C:** A1 по композиции объектов и контексту; выводить `compatible_with`, а не факт выполнения работ.

---

## 2.6 Schedule matching

### Вход `ScheduleSnapshot`

```text
schedule_version: string
valid_at: TimestampUTC
tasks: [{
  task_id: string
  parent_task_id: string?
  name: string
  planned_start: TimestampUTC?
  planned_finish: TimestampUTC?
  planned_progress_curve: [{ts, progress: float32}]?
  zones: string[]
  dependencies: [{task_id, relation, lag_s?}]
  expected_signature_id: string?
  tolerance: {
    start_early_s?, start_late_s?,
    finish_late_s?, score_threshold?
  }
  criticality: enum{critical,high,normal,unknown}
}]
```

Если график не содержит зон, техники и сигнатур, они задаются отдельной версионированной таблицей соответствий. Это экспертная гипотеза, а не факт из календаря.

### Выход `ConformityAssessment`

```text
assessment_id: UUID
task_id: string
interval: Interval
schedule_version: string
observed_signature_id: UUID
conformity_score: Score
conformity_distribution: distribution
evidence_only_stage_posterior: Distribution[W]
plan_aware_stage_posterior: Distribution[W]?
expected_signature_version: string
feature_contributions: map<feature_name,float32>
missing_expected_features: string[]
contradictory_features: string[]
unobservable_features: string[]
data_sufficiency: Score
decision_eligibility: enum{eligible,insufficient_data,not_observable}
```

Частота:

- **A:** пересчёт каждые 5–30 мин;
- **B:** на новый кадр/пакет, обычно не чаще раза в 5–30 мин;
- **C:** разовая совместимость без утверждения о сроках, если timestamp отсутствует.

### Альтернативы

| Подход | Качество | Стоимость | Требования | Риск |
|---|---|---|---|---|
| **M1. Взвешенное сходство сигнатур** | Прозрачно, быстро, легко объяснить | Низкая | Экспертные веса и маски наблюдаемости | Низкий |
| **M2. Вероятностный likelihood с моделью ошибок** | Корректнее учитывает detector noise | Средняя | Калибровка ошибок и expected distributions | Средний |
| **M3. Байесовская динамическая модель задач** | Учитывает зависимости и накопление факта | Высокая | Переходы, priors, временная история | Высокий |

Выбор:

- **A:** M2; M1 как объяснимый baseline; M3 при длинной истории.
- **B:** M2 или M3 с переходами, соответствующими большим интервалам.
- **C:** M1/M2 только для совместимости изображения с видом работ; M3 неприменим без времени и последовательности.

---

## 2.7 Deviation detection

### Выход `DeviationCandidate`

```text
candidate_id: UUID
site_id: string
task_id: string?
deviation_type: enum
interval: Interval
severity_distribution: Distribution[severity]
deviation_probability: Probability
conformity_score: Score?
persistence_probability: Probability?
affected_zones: string[]
evidence_refs: EvidenceRef[]
counter_evidence_refs: EvidenceRef[]
data_sufficiency: Score
alternative_explanations: [{
  code: string
  probability?: Probability
}]
assertion_limit: string
model_version: string
```

### Альтернативы

| Подход | Качество | Стоимость | Требования | Риск |
|---|---|---|---|---|
| **D1. Пороги + persistence + правила качества** | Предсказуемо и объяснимо | Низкая | Настройка порогов | Низкий |
| **D2. Statistical process control/change-point detection** | Хорошо ловит устойчивые сдвиги без labels | Средняя | История стабильной работы | Низкий–средний |
| **D3. Supervised anomaly/deviation classifier** | Потенциально лучший ranking | Высокая | Репрезентативная разметка отклонений | Высокий |

Выбор:

- **A:** D1 + D2.
- **B:** D1 с количеством подтверждающих кадров вместо секунд; D2 по дневным рядам.
- **C:** только ограниченные визуальные несоответствия; временные отклонения не определять.

---

## 2.8 Alerting

### Выход `Alert`

```text
alert_id: UUID
candidate_id: UUID
status: enum{pending,open,acknowledged,resolved,suppressed}
alert_type: enum
severity: enum{info,warning,critical}
confidence: Probability
created_at: TimestampUTC
first_evidence_at: TimestampUTC?
last_evidence_at: TimestampUTC?
task_id: string?
zone_ids: string[]
headline: string
observed_statement: string
plan_statement: string?
uncertainty_statement: string
assertion_limit: string
evidence_refs: EvidenceRef[]
explanation: [{
  feature: string
  observed: scalar|string
  expected: scalar|string
  contribution: float32
}]
suppression_reason: string?
deduplication_key: string
policy_version: string
```

Каналы: dashboard всегда; push/email только при достаточной уверенности, persistence и доступном бюджете ложных тревог.

### Альтернативы

| Подход | Качество | Стоимость | Требования | Риск |
|---|---|---|---|---|
| **L1. Фиксированные пороги и cooldown** | Просто, но плохо адаптируется | Низкая | Минимум данных | Низкий |
| **L2. Гистерезис + severity + false-alert budget** | Лучший хакатонный баланс | Средняя | История candidates и feedback | Низкий |
| **L3. Decision-theoretic policy по стоимости FN/FP** | Оптимально при известных бизнес-стоимостях | Высокая | Надёжные cost estimates | Средний–высокий |

Выбор:

- **A:** L2.
- **B:** L2 с evidence-count hysteresis.
- **C:** L1/L2, но только для проблем, наблюдаемых в одном изображении; без срочных утверждений о задержке графика.

---

# 3. Expected Signature

## 3.1 Представление

Для вида работ \(w\), зоны \(z\), фазы выполнения \(\phi\in[0,1]\) и контекста \(c\):

\[
E_{w,z,\phi,c} =
\left\{
E_i,\ q_i,\ \omega_i,\ \tau_i,\ \rho_{ij},\ a_i
\right\}_{i=1}^{d},
\]

где:

- \(E_i\) — ожидаемое распределение признака;
- \(q_i\in\{\text{required},\text{supporting},\text{forbidden},\text{irrelevant}\}\);
- \(\omega_i\ge 0\) — важность;
- \(\tau_i\) — допустимое отклонение;
- \(\rho_{ij}\) — зависимости признаков;
- \(a_i\in[0,1]\) — ожидаемая наблюдаемость.

Примеры признаков, не утверждаемые как доступные:

```text
count(excavator), active_count(crane), presence(dump_truck),
zone_occupancy(work_zone_3), vehicle_flow(access_gate),
motion_pattern(cyclic), scene_change(excavation_volume_proxy),
material_presence(rebar), structural_visual_stage,
time_of_day, minimum_observation_duration
```

`ExpectedSignature`:

```text
expected_signature_id: string
version: string
work_type: string
applicable_zones: string[]
phase_range: {min: float32, max: float32}?
features: [{
  feature_name: string
  semantic: required|supporting|forbidden|irrelevant
  expected_distribution: distribution specification
  weight: float32
  tolerance: float32?
  minimum_observability: float32
}]
minimum_evidence: {
  frames?: int
  duration_s?: float32
  distinct_days?: int
}
valid_contexts: map<string, allowed values>
expert_confidence: Probability
```

**ФАКТ:** календарное название задачи само по себе не определяет визуальную сигнатуру.  
**ГИПОТЕЗА:** первоначальные сигнатуры можно задать экспертно и уточнить по данным.  
**НЕИЗВЕСТНО:** насколько детально график связывает задачи с зонами и ресурсами.

---

## 3.2 Формулировка 1: взвешенное маскированное сходство

Пусть \(o_i\) — наблюдаемый признак, \(e_i\) — ожидаемое значение, \(u_i\) — его неопределённость, \(m_i\in\{0,1\}\) — наблюдаемость.

Для числового признака:

\[
s_i =
\exp\left(
-\frac{|o_i-e_i|}
{\tau_i+\lambda u_i+\epsilon}
\right).
\]

Для категориального распределения:

\[
s_i = 1-\operatorname{JSD}(P_i^{obs}\|P_i^{exp}).
\]

Для required/supporting:

\[
S^+ =
\frac{\sum_i m_i a_i\omega_i s_i}
{\sum_i m_i a_i\omega_i+\epsilon}.
\]

Для forbidden-признаков с вероятностью \(p_j^{obs}\):

\[
P^- = 1-\prod_{j\in F}
\left(1-\omega_j m_j p_j^{obs}\right).
\]

Итог:

\[
C_{\text{sim}}=
\operatorname{clip}
\left(S^+-\gamma P^-,0,1\right).
\]

Отдельно:

\[
R_{\text{coverage}} =
\frac{\sum_i m_i a_i\omega_i}
{\sum_i a_i\omega_i+\epsilon}.
\]

Решение запрещено, если \(R_{\text{coverage}}<r_{\min}\).

Плюсы: объяснимость, быстрое внедрение, не требует labels отклонений.  
Минусы: независимость признаков фактически предполагается; веса субъективны; score не является вероятностью без калибровки.  
Лучше всего: хакатонный baseline, малый датасет, сценарий C.

---

## 3.3 Формулировка 2: likelihood с моделью шума детектора

Пусть истинное скрытое количество техники класса \(k\) равно \(N_k\), а наблюдаемое — \(Y_k\). Для детектора известны recall \(r_k(c)\) и интенсивность ложных срабатываний \(\lambda_k(c)\), зависящие от контекста качества \(c\):

\[
T_k\mid N_k,c \sim \operatorname{Binomial}(N_k,r_k(c)),
\]

\[
F_k\mid c \sim \operatorname{Poisson}(\lambda_k(c)),
\]

\[
Y_k=T_k+F_k.
\]

Expected Signature задаёт:

\[
N_k\mid w,\phi,z \sim P_k^{exp}(N_k).
\]

Тогда:

\[
P(Y_k\mid w,\phi,z,c)=
\sum_{n=0}^{N_{\max}}
P(Y_k\mid N_k=n,c)P_k^{exp}(n\mid w,\phi,z).
\]

Для активности, зон и scene-change добавляются соответствующие likelihood-компоненты:

\[
\log L(w)=
\sum_i m_i\alpha_i
\log P(O_i\mid w,c)
-\beta\cdot \text{ComplexityPenalty}(w).
\]

Нормированный conformity:

\[
C_{\text{like}}(w)=
\frac{L(w)}
{L(w)+L(\text{background})+L(\text{unknown})}.
\]

Плюсы: различает «не увидели объект» и «объекта нет»; естественно учитывает качество кадра, occlusion и ошибки классов.  
Минусы: требуется калибровать recall/FP по размеру объекта, погоде, зоне и камере; корреляции кадров могут дать чрезмерную уверенность.  
Лучше всего: A и B после минимальной валидационной разметки.

---

## 3.4 Формулировка 3: байесовское обновление задач как скрытых переменных

Для задачи \(j\):

\[
X_{j,t}\in
\{\text{not-started},\text{active},\text{paused},
\text{completed},\text{unknown}\}.
\]

Переход:

\[
P(X_{j,t}\mid X_{j,t-1},D_j,U_t),
\]

где \(D_j\) — зависимости графика, \(U_t\) — наблюдаемый контекст. Наблюдение:

\[
O_t\sim P(O_t\mid X_{j,t},E_j,Q_t),
\]

где \(E_j\) — Expected Signature, \(Q_t\) — качество/наблюдаемость.

Evidence-only posterior:

\[
P_e(X_{j,t}\mid O_{1:t})
\propto
P(O_t\mid X_{j,t})
\sum_x
P_0(X_{j,t}\mid x)
P_e(x\mid O_{1:t-1}),
\]

где \(P_0\) — план-независимая физически допустимая динамика.

Plan-aware posterior:

\[
P_p(X_{j,t}\mid O_{1:t},S)
\propto
P(O_t\mid X_{j,t})
\sum_x
P_S(X_{j,t}\mid x,t,D_j)
P_p(x\mid O_{1:t-1},S).
\]

Мера конфликта с планом:

\[
\Delta_{j,t}
=
\operatorname{JSD}
\left(
P_e(X_{j,t}\mid O_{1:t})
\parallel
P_S(X_{j,t}\mid t)
\right).
\]

Можно оценивать вероятность задержки:

\[
P(\text{delay}_j>\delta\mid O_{1:t}),
\]

но только если состояние задачи визуально наблюдаемо и timestamp надёжен.

Плюсы: накопление доказательств, зависимости задач, пропуски наблюдений, явная неопределённость.  
Минусы: сложность переходов; опасность доминирования prior; трудная отладка.  
Лучше всего: длинная временная история A/B; непригодно для C без временной привязки.

---

# 4. Защита от циклической логики

Проблемная схема:

```text
План говорит «сейчас земляные работы»
→ модель предпочитает земляные работы
→ результат сравнивается с планом
→ система сообщает полное соответствие.
```

## 4.1 Два физически разделённых пути

### Путь E: evidence-only, обязательный для отклонений

```text
изображения
→ детекции
→ движение/change
→ site state
→ P_e(activity, stage | visual evidence)
```

Запрещённые входы:

- плановые даты;
- название текущей плановой задачи;
- ожидаемая техника на текущую дату;
- ожидаемый прогресс;
- downstream conformity score.

Разрешены только статические справочники:

- классы техники;
- геометрия зон;
- визуальные определения активностей;
- физически допустимые переходы, не привязанные к плановой дате.

### Путь P: plan-aware, диагностический

```text
визуальные evidence + план
→ P_p(stage | evidence, plan)
```

Используется для:

- ранжирования гипотез;
- интерфейса руководителя;
- анализа неоднозначности;
- но не как единственный источник deviation alert.

### Comparator

```text
ExpectedSignature(plan) ↔ ObservedSignature(evidence-only)
```

Alert должен сохранять обе величины:

\[
C_e=C(E[P_e],E_{plan}),
\qquad
C_p=C(E[P_p],E_{plan}).
\]

Если \(C_p\gg C_e\), это признак поглощения отклонения плановым prior.

## 4.2 Метрики утечки prior

1. **Prior Influence Index**

\[
PII =
\mathbb{E}
\left[
\operatorname{JSD}(P_e(W_t)\|P_p(W_t))
\right].
\]

Высокий PII при слабых данных допустим только как признак неопределённости, но не как основание conformity.

2. **Counterfactual Plan Sensitivity**

Для одного и того же observation подставить истинный, сдвинутый и заведомо неверный планы \(S,S',S''\):

\[
CPS =
\mathbb{E}_{S'\ne S}
\operatorname{JSD}
\left(
P_e(W\mid O,S),
P_e(W\mid O,S')
\right).
\]

Для корректного evidence-only пути \(CPS=0\) с учётом численной погрешности.

3. **Deviation Recall under prior conflict**

На синтетических контрфактуалах поменять местами даты/Expected Signatures. Измерить recall несоответствий отдельно для:

- evidence-only comparator;
- plan-aware posterior.

4. **Prior override rate**

\[
POR=P\left(
\arg\max P_p=W_{plan},
\arg\max P_e\ne W_{plan},
H(P_e)<h_{\max}
\right).
\]

Высокий POR при уверенном evidence-only выводе — дефект.

5. **Blind-plan evaluation**

Все метрики activity/stage inference рассчитываются на наборе, где модуль не получает план. Только matching оценивается с планом.

Правило принятия решения: plan-aware результат может повысить приоритет ручной проверки, но не должен отменять уверенное evidence-only противоречие.

---

# 5. Работающая и припаркованная техника

## 5.1 Сценарий A: плотное видео 10–25 FPS

### Признаки

- перемещение центра bbox/mask после компенсации движения камеры;
- скорость и ускорение в координатах изображения или площадки;
- движение частей механизма: ковш, стрела, кузов, крановый крюк;
- оптический поток внутри объекта относительно фона;
- периодичность рабочих циклов;
- въезд/выезд из рабочих зон;
- взаимодействие с материалом или другой техникой;
- длительность полной неподвижности;
- контекст зоны: парковка против рабочей зоны.

### Вычисление

1. Оценить сдвиг камеры по фоновым keypoints.
2. Стабилизировать координаты bbox/mask.
3. Построить tracklet.
4. Рассчитать displacement и velocity на горизонтах 1–5 и 10–60 с.
5. Сравнить optical flow внутри mask с локальным фоном.
6. При наличии keypoints/part detector измерить изменение конфигурации рабочего органа.
7. Агрегировать признаки по окнам, исключая occluded/unusable фрагменты.
8. Получить \(P(active\mid features)\) калиброванной моделью или правилами.
9. Ввести класс `engine_on_but_stationary = unknown`, если визуально неразличим.

Требования: последовательность, стабильная камера или успешная стабилизация, достаточный размер объекта.

Ожидаемая надёжность:

- высокая для перемещающейся техники;
- средняя для циклически работающей на месте;
- низкая для прогрева, работы двигателя без видимого движения и операций за препятствием.

## 5.2 Сценарий B: time-lapse раз в 5–30 минут

### Признаки

- изменение положения между кадрами;
- изменение позы стрелы/ковша/кузова;
- появление в разных рабочих зонах;
- изменения грунта/материалов вокруг объекта;
- повторяющееся присутствие в рабочей зоне;
- размытость движения, если выдержка позволяет;
- изменение состава техники и следов деятельности.

### Вычисление

1. Зарегистрировать кадры по неподвижному фону.
2. Сопоставить объекты по классу, appearance и зоне; не считать match доказанным треком.
3. Измерить распределение возможного displacement с учётом ambiguity.
4. Измерить изменение pose/configuration.
5. Рассчитать локальную scene-change mask за вычетом освещения, теней и погодных изменений.
6. Объединить evidence за 2–12 кадров.
7. Вывести классы `likely_active`, `likely_parked`, `indeterminate`.
8. Не интерпретировать одинаковую позицию в двух кадрах как непрерывную неподвижность: техника могла работать и вернуться.

Требования: timestamp, повторяемый ракурс, минимум несколько кадров.

Ожидаемая надёжность:

- средняя для перемещений и заметных изменений;
- низкая–средняя для стационарных рабочих циклов;
- низкая для единичной пары кадров с большим интервалом.

## 5.3 Сценарий C: отдельные фотографии без времени

Временное понятие «работает» в общем случае неидентифицируемо.

Допустимые признаки:

- поднятый кузов самосвала;
- ковш в материале;
- натянутый трос/подвешенный груз;
- выраженная динамическая поза рабочего органа;
- пыль, выброс материала, motion blur;
- пространственное взаимодействие с рабочей зон.

Вычисление:

1. Детектировать технику и, если возможно, рабочие органы.
2. Определить позу/конфигурацию.
3. Определить контакт и пространственные отношения с материалом/зоной.
4. Оценить визуальные динамические cues.
5. Выдать \(P(\text{active at capture instant})\) либо `activity_unknown`.
6. Никогда не преобразовывать один кадр в длительность работы.

Ожидаемая надёжность:

- средняя лишь для ярко выраженной рабочей позы;
- низкая для техники с нейтральной позой;
- «припаркована» допустимо только как `visually consistent with parked`, а не факт.

---

# 6. Сквозная модель неопределённости

## 6.1 Источники

1. **Aleatoric:** blur, туман, ночь, occlusion, малый объект.
2. **Epistemic:** новый тип техники, новый ракурс, domain shift.
3. **Association:** ошибочная склейка/разрыв трека.
4. **Sampling:** пропуски между редкими кадрами.
5. **Observability:** зона закрыта или вне поля зрения.
6. **Semantic:** одинаковая техника используется в разных работах.
7. **Schedule:** неточная детализация, фактические переносы, неверное связывание с зонами.
8. **Expected Signature:** экспертная сигнатура неполна или неоднозначна.

## 6.2 Perception → count distribution

Не превращать confidence в бинарный объект слишком рано. Для детекций \(d\) класса \(k\):

\[
p_{d,k}=P(\text{реальный объект класса }k\mid x_d).
\]

При независимом приближении count имеет Poisson-binomial distribution:

\[
P(N_k=n)=
\sum_{A:|A|=n}
\prod_{d\in A}p_{d,k}
\prod_{d\notin A}(1-p_{d,k}).
\]

На практике — динамическое программирование, Monte Carlo или аппроксимация. Для перекрывающихся детекций вводится mutual exclusion; для треков нельзя считать соседние кадры независимыми.

## 6.3 Aggregation

Для tracklet комбинировать evidence с поправкой на корреляцию:

\[
\logit p_{\text{track}}
=
b+\sum_t \alpha_t\logit p_t,
\qquad
\sum_t\alpha_t\le N_{\text{eff}},
\]

где \(N_{\text{eff}}\) ограничивает искусственный рост уверенности на почти одинаковых кадрах.

Association uncertainty включается через несколько гипотез соответствия или штраф:

\[
p_{\text{track}}^\ast =
p_{\text{track}}\cdot p_{\text{association}}.
\]

Пропуски детекций моделируются survival probability, но не бесконечным переносом последнего состояния.

## 6.4 Site state

Multi-camera fusion выполняется через mixture по гипотезам дублирования:

\[
P(N=n\mid O_{1:C})
=
\sum_h
P(N=n\mid h,O_{1:C})P(h\mid O_{1:C}).
\]

Если геометрия неизвестна, камеры не суммируются безусловно: выводятся camera-local counts и интервал возможного глобального количества.

## 6.5 Activity/stage inference

Модель должна выдавать posterior и `unknown`:

\[
P(A\mid Z),\quad P(W\mid Z),\quad P(\text{unknown}\mid Z).
\]

Uncertainty можно оценивать:

- calibrated softmax/temperature scaling;
- ансамблем моделей;
- Monte Carlo dropout как приближением;
- conformal prediction sets;
- bootstrap по кадрам/tracklets;
- интервальными правилами для экспертного inference.

## 6.6 Matching

Conformity должен быть распределением:

\[
P(C\mid O,E)=
\int P(C\mid z,E)P(z\mid O)\,dz.
\]

Практически: семплировать 100–1000 вариантов ObservedSignature из её posterior, вычислять \(C\), сохранять mean, quantiles и:

\[
P(C<\tau).
\]

Alert основан не на среднем score, а, например, на:

\[
P(C<\tau\mid O)>\eta
\]

при достаточной наблюдаемости и persistence.

## 6.7 Финальная confidence алерта

\[
Conf_{alert} =
P(D\mid O,E)
\cdot R_{\text{coverage}}
\cdot R_{\text{timestamp}}
\cdot R_{\text{calibration}}
\cdot R_{\text{persistence}}.
\]

Это инженерный composite score; если он показывается как вероятность, нужна отдельная калибровка.

## 6.8 Что калибровать

- objectness и class probabilities;
- probability присутствия трека;
- count intervals;
- `active/parked/unknown`;
- activity/stage posterior;
- conformity score;
- вероятность каждого типа отклонения;
- итоговый alert confidence.

Методы:

- temperature scaling;
- Platt scaling;
- isotonic regression при достаточной выборке;
- classwise calibration;
- calibration по bins размера объекта, камеры и качества;
- conformal prediction для гарантированного покрытия при exchangeability.

Метрики: ECE, Brier score, NLL, reliability diagrams, coverage/width conformal intervals.

## 6.9 Если нет разметки отклонений

Размечать более дешёвые промежуточные сущности:

- bbox и класс;
- видимость зоны;
- истинное количество;
- active/parked/unknown;
- activity cues;
- совместимость пары `наблюдение—сигнатура`;
- качество кадра.

Далее использовать:

1. синтетические отклонения перестановкой дат, задач, зон и сигнатур;
2. counterfactual schedule corruption;
3. weak labels из известных периодов остановки/работы, если они появятся;
4. экспертное pairwise ranking кандидатов;
5. калибровку нижних уровней на локальной выборке;
6. conservative alert policy и feedback операторов.

Синтетические отклонения пригодны для теста чувствительности, но не доказывают реальную alert precision.

---

# 7. Псевдокод

## 7.1 Temporal aggregation → site state

```text
procedure BUILD_SITE_STATE(perception_frames, zone_map, previous_state):
    valid_frames ← remove_unusable_and_duplicate_frames(perception_frames)
    if valid_frames is empty:
        return UNKNOWN_STATE(reason="no usable observations")

    groups ← group_by_camera(valid_frames)
    camera_states ← empty list

    for each camera_id, frames in groups:
        frames ← sort_by_timestamp_or_sequence(frames)
        stabilized ← estimate_and_compensate_camera_shift(frames)

        if sampling_is_dense(stabilized):
            hypotheses ← track_by_detection_with_association_uncertainty(stabilized)
        else if timestamps_are_available(stabilized):
            hypotheses ← match_sparse_observations_by_zone_and_appearance(stabilized)
        else:
            hypotheses ← independent_single_frame_hypotheses(stabilized)

        tracklets ← empty list
        for each hypothesis in hypotheses:
            class_posterior ← fuse_class_evidence(hypothesis, cap_effective_samples=true)
            motion_posterior ← estimate_motion(hypothesis, sampling_regime)
            active_posterior ← infer_activity_cues(
                motion_posterior, part_motion, pose_change, local_scene_change
            )
            zone_posterior ← intersect_with_zone_map(hypothesis, camera_id)
            tracklets.add(pack_with_uncertainty(
                class_posterior, motion_posterior,
                active_posterior, zone_posterior
            ))

        counts ← count_distribution(tracklets, account_for_mutual_exclusion=true)
        coverage ← estimate_visible_zone_fraction(frames, zone_map)
        camera_states.add({tracklets, counts, coverage, quality_summary})

    if cross_camera_geometry_is_valid():
        site_state ← probabilistic_multicamera_fusion(camera_states)
    else:
        site_state ← retain_camera_local_states_and_global_count_bounds(camera_states)

    site_state ← decay_stale_evidence(site_state, previous_state)
    site_state ← mark_unobserved_fields_as_unknown(site_state)
    site_state.effective_sample_size ← estimate_effective_samples(valid_frames)
    site_state.evidence_refs ← select_representative_evidence(valid_frames)
    return site_state
```

## 7.2 Conformity score

```text
procedure COMPUTE_CONFORMITY(observed, expected, detector_noise_model):
    aligned ← align_features_by_semantics_zone_and_time(observed, expected)
    contributions ← empty map
    used_weight ← 0
    total_observable_weight ← 0
    forbidden_penalty ← 0

    for each expected_feature e in expected.features:
        total_observable_weight += e.weight * e.expected_observability

        if not observed.is_observable(e.name, e.minimum_observability):
            contributions[e.name] ← UNKNOWN
            continue

        o ← observed.distribution(e.name)
        used_weight += e.weight * e.expected_observability

        if detector_noise_model supports e.name:
            similarity ← normalized_marginal_likelihood(
                o, e.expected_distribution, detector_noise_model
            )
        else if e.is_categorical:
            similarity ← 1 - JensenShannon(o, e.expected_distribution)
        else:
            similarity ← uncertainty_scaled_numeric_similarity(o, e)

        if e.semantic == "forbidden":
            penalty ← e.weight * probability_feature_present(o)
            forbidden_penalty ← combine_probabilistic_penalties(
                forbidden_penalty, penalty
            )
            contributions[e.name] ← -penalty
        else:
            contribution ← e.weight * similarity
            contributions[e.name] ← contribution

    coverage ← used_weight / max(total_observable_weight, epsilon)
    if coverage < MIN_COVERAGE or not minimum_evidence_met(observed, expected):
        return {status: "insufficient_data", score: UNKNOWN, coverage}

    positive_score ← sum_positive(contributions) / max(used_weight, epsilon)
    score_samples ← propagate_uncertainty_by_sampling(aligned, expected)
    final_samples ← clip(score_samples - GAMMA * forbidden_penalty, 0, 1)

    return {
        status: "eligible",
        score: mean(final_samples),
        interval: quantiles(final_samples, [0.05, 0.95]),
        probability_below_threshold: mean(final_samples < expected.threshold),
        coverage: coverage,
        contributions: contributions
    }
```

## 7.3 Alert с гистерезисом и бюджетом ложных тревог

```text
procedure UPDATE_ALERT(candidate, alert_state, policy, budget_state):
    if candidate.data_sufficiency < policy.min_sufficiency:
        return suppress_or_hold(alert_state, reason="insufficient_data")

    if candidate.camera_health_is_bad:
        return route_to_camera_health_alert(candidate, alert_state)

    risk ← calibrated_deviation_probability(candidate)
    key ← dedup_key(candidate.site_id, candidate.task_id,
                    candidate.type, candidate.affected_zones)
    state ← alert_state.get_or_create(key)

    if risk >= policy.open_threshold:
        state.positive_evidence += candidate.effective_evidence
        state.negative_evidence ← max(0, state.negative_evidence - 1)
    else if risk <= policy.close_threshold:
        state.negative_evidence += candidate.effective_evidence
        state.positive_evidence ← max(0, state.positive_evidence - 1)
    else:
        state ← decay_evidence_slowly(state)

    persistent_open ← (
        state.positive_evidence >= policy.min_open_evidence
        and candidate.persistence_probability >= policy.min_persistence
    )
    persistent_close ← state.negative_evidence >= policy.min_close_evidence

    expected_false_cost ← estimate_false_alert_cost(candidate, policy)
    budget_available ← budget_state.can_spend(
        candidate.site_id, candidate.severity, expected_false_cost
    )

    if state.status in {"closed", "pending"} and persistent_open:
        if budget_available or candidate.severity == "critical":
            state.status ← "open"
            budget_state.spend(expected_false_cost)
            state.cooldown_until ← now() + policy.cooldown
            emit_alert(candidate, state, include_uncertainty=true)
        else:
            state.status ← "suppressed"
            state.reason ← "false-alert budget exhausted"

    else if state.status == "open" and persistent_close:
        state.status ← "resolved"
        emit_resolution(candidate, state)

    else if state.status == "open" and now() >= state.cooldown_until:
        if material_severity_increase(candidate, state):
            emit_alert_update(candidate, state)
            state.cooldown_until ← now() + policy.cooldown

    persist(state, budget_state)
    return state
```

---

# 8. Таксономия отклонений

| Тип | Наблюдаемый признак | Минимальные данные | Риск ложной тревоги | Система не имеет права утверждать |
|---|---|---|---|---|
| 1. Ожидаемая техника не наблюдается | Низкая \(P(N_k>0)\) при высокой видимости | Кадр, зона, Expected Signature, качество | Высокий при occlusion/вне FOV | «Техники на площадке нет» |
| 2. Недостаточное количество техники | Count posterior ниже ожидаемого диапазона | Калиброванные counts, зона | Средний–высокий | «Ресурсов точно недостаточно для срока» |
| 3. Неожиданный тип техники | Устойчивая техника forbidden/нехарактерного класса | Надёжная классификация | Средний из-за путаницы классов | «Техника используется не по назначению» |
| 4. Техника присутствует, но визуально неактивна | Высокое presence, низкое active на длительном окне | Видео или серия кадров | Средний | «Простой вызван подрядчиком» |
| 5. Активность в неверной зоне | Активный объект устойчиво вне ожидаемой зоны | Валидная геометрия зон | Средний | «Работы выполняются с нарушением технологии» |
| 6. Работы визуально не начались в плановое окно | Evidence-only posterior остаётся `not-started` | Timestamp, план, наблюдаемая сигнатура | Высокий при скрытых работах | «Задача фактически не начата» без оговорки видимости |
| 7. Активность продолжается после планового завершения | Signature активности сохраняется после finish | Временной ряд и график | Средний | «Проект задержан на X дней» без progress model |
| 8. Преждевременная активность | Signature появляется до planned start | Время, план, зона | Средний | «Нарушена последовательность работ» без зависимостей |
| 9. Несовместимые параллельные активности | Две forbidden-together сигнатуры в одной зоне | Хорошая семантика зон и правил | Высокий | «Создана опасная ситуация» без safety-ТЗ |
| 10. Аномально низкая интенсивность | Active count/flow существенно ниже baseline | Плотное видео или длинный time-lapse | Средний | «Производительность ниже нормы» без норм выработки |
| 11. Аномально высокая концентрация техники | Count/occupancy выше expected range | Надёжный подсчёт и зона | Средний | «Перегрузка площадки опасна» |
| 12. Длительная остановка активности | Change-point к `idle` с persistence | Временной ряд | Средний | Причину остановки |
| 13. Несогласованность прогресса и активности | Есть activity evidence, но visual progress proxy не меняется | Стабильный ракурс, дни наблюдений | Высокий | «Работы фиктивны/неэффективны» |
| 14. Нарушение ожидаемой последовательности стадий | Evidence-only posterior перескакивает/возвращается | Длинный ряд, различимые стадии | Высокий | «Технологическое нарушение» без экспертной проверки |
| 15. Необъяснимое исчезновение техники | Track/count резко падает без exit evidence | Видео, покрытие въездов | Высокий | «Техника покинула объект» |
| 16. Несогласованность между камерами | Камеры дают конфликтующие state distributions | Синхронизация и overlap | Средний | Какой источник истинный без диагностики |
| 17. Недостаточная наблюдаемость | Ожидаемая зона закрыта/камера смещена/кадр непригоден | Quality и camera-shift monitoring | Низкий | Любое производственное отклонение |
| 18. Неизвестная техника/OOD | Высокий OOD, нестабильный класс | Изображение | Средний | Конкретный класс или назначение объекта |

Каждый производственный alert должен иметь `assertion_limit`, например:

> «Ожидаемый экскаватор не наблюдается в видимой части зоны Z в 8 из 10 пригодных кадров; наличие за пределами обзора не исключено».

---

# 9. Baselines B0–B5

| Baseline | Состав | Цель | Время после получения данных |
|---|---|---|---:|
| **B0** | Проверка входов, frame-quality, ручной просмотр стратифицированной выборки, константный predictor | Установить классы, качество, режим частоты и верхние ограничения наблюдаемости | 3–5 ч |
| **B1** | Предобученный detector на одиночных кадрах, confidence threshold, raw counts | Первый измеримый perception baseline | 4–8 ч |
| **B2** | B1 + ручные ROI/зоны + NMS/WBF + quality gate + калибровка confidence | Проверить пользу геометрии и качества | 6–10 ч |
| **B3** | B2 + tracking/EMA или sparse matching + count distributions | Проверить устойчивость counts и presence | 8–14 ч |
| **B4** | B3 + active/parked rules + expert Expected Signatures + weighted conformity | Полный объяснимый end-to-end baseline | 10–16 ч |
| **B5** | Fine-tuned detector + probabilistic likelihood + evidence-only stage posterior + hysteresis alerts | Конкурентоспособная итоговая система | 20–40 ч, зависит от разметки/GPU |

Порядок не требует обязательно доводить B5: устойчивый B4 лучше недоотлаженного video transformer.

Основные метрики:

- detection: mAP, per-class precision/recall, recall малых объектов;
- counting: MAE, RMSE, exact-count accuracy, interval coverage;
- tracking: HOTA/IDF1, только для A;
- active state: macro-F1, balanced accuracy, coverage при selective prediction;
- stage/activity: macro-F1, NLL, Brier;
- conformity: AUROC/AUPRC на совместимых/несовместимых парах;
- alerts: precision@budget, false alerts/site/day, detection delay;
- calibration: ECE, NLL, interval coverage;
- robustness: метрики по камерам, времени суток, погоде, размеру объекта.

---

# 10. Десять дешёвых ablation-экспериментов

| № | Гипотеза | Сравнение | Стоимость | Информационная ценность |
|---:|---|---|---:|---|
| A1 | Quality gate снижает ложные тревоги сильнее, чем теряет recall | B1 с/без исключения degraded кадров | 1–2 ч | Высокая |
| A2 | Temporal smoothing улучшает count MAE | Raw counts против median/EMA/count posterior | 1–2 ч | Высокая |
| A3 | Tracking нужен именно для поведения, а не для counts | EMA против tracker на count и active-state | 2–4 ч | Высокая для A |
| A4 | Ручные зоны дают больше пользы, чем усложнение detector | Global features против zone-aware features | 2–3 ч | Высокая |
| A5 | Компенсация сдвига камеры критична для active/parked | Motion features до/после stabilization | 2–4 ч | Высокая |
| A6 | Appearance embeddings полезны при occlusion | IoU-only против IoU+appearance association | 2–4 ч | Средняя |
| A7 | Detector confidence нельзя трактовать как вероятность | До/после temperature/isotonic calibration | 1–3 ч | Высокая |
| A8 | Required/forbidden семантика лучше плоского cosine similarity | Flat similarity против typed signature | 2–3 ч | Средняя–высокая |
| A9 | Plan prior поглощает реальные отклонения | Evidence-only против plan-aware на переставленных планах | 3–5 ч | Критическая |
| A10 | Гистерезис существенно сокращает alert churn | Single-threshold против open/close thresholds + persistence | 2–3 ч | Высокая |

Каждый ablation проводится на фиксированном split по камерам/дням, а не по случайным кадрам. Иначе почти одинаковые соседние кадры попадут одновременно в train и validation.

---

# 11. Экспериментальный протокол после публикации данных

## 11.1 Первые 2 часа

1. Зафиксировать schema и лицензии.
2. Определить режим A/B/C отдельно для каждого источника.
3. Проверить timestamps, дубликаты, разрешения и смены ракурса.
4. Построить распределения кадров по камере, времени, размеру.
5. Просмотреть не случайные 100 кадров, а стратифицированную выборку:
   камера × время суток × качество × период.
6. Сопоставить термины графика с визуально наблюдаемыми сущностями.
7. Составить таблицу `observable / partially observable / unobservable`.

## 11.2 Split

Приоритет:

1. holdout по целым камерам, если нужна переносимость;
2. holdout по целым дням/эпизодам;
3. временной split без перемешивания соседних кадров;
4. отдельный stress set: ночь, дождь, occlusion, малые объекты, camera shift.

Запрещён random frame split для оценки temporal models.

## 11.3 Минимальная разметка

Если времени мало:

- 300–800 кадров bbox;
- 100–200 кадров с точными counts;
- 50–100 коротких видеоокон для active/parked;
- 100–300 пар `ObservedSignature—ExpectedSignature` с экспертной оценкой;
- отдельная разметка `unknown/unobservable`.

Active learning:

1. запустить pretrained detector;
2. выбрать high-confidence, low-confidence, OOD и disagreement samples;
3. размечать разнообразие, а не соседние кадры;
4. повторить один цикл fine-tuning.

---

# 12. Пять неочевидных технических ловушек

## 12.1 Camera shift имитирует движение всей техники

Ветер, обслуживание камеры, цифровой zoom или изменение crop создают массовое ложное движение. Optical flow и bbox displacement без регистрации кадра превращают парковку в активность.

Контроль:

- фоновые keypoints;
- robust homography;
- alarm `camera_geometry_changed`;
- инвалидировать motion features до повторной привязки зон.

## 12.2 Отсутствие детекции не равно отсутствию техники

Строительная техника систематически перекрывается, покрывается грязью, выглядит малоразмерной и выходит из видимой зоны. Бинарный threshold создаёт ложные остановки и задержки.

Контроль:

- count distributions;
- visibility probability;
- survival модели tracklet;
- `unknown`, когда зона не наблюдаема;
- calibration по размеру объекта и камере.

## 12.3 Наблюдения во времени сильно коррелированы

Тысяча почти одинаковых кадров — не тысяча независимых подтверждений. Наивное перемножение likelihood быстро даёт ложную уверенность, близкую к 1.

Контроль:

- effective sample size;
- subsampling;
- block bootstrap;
- evidence cap;
- split по эпизодам/дням.

## 12.4 Стадия работ неидентифицируема только по составу техники

Одинаковые экскаватор и самосвал могут соответствовать нескольким видам работ; отсутствие уникальной техники не исключает стадию. Простая таблица `техника → этап` будет выглядеть убедительно, но причинно неверна.

Контроль:

- зоны;
- динамика;
- изменение сцены;
- сочетания required/forbidden cues;
- posterior по нескольким гипотезам;
- explicit `unknown`.

## 12.5 Версия графика может измениться задним числом

Если система пересчитает старые наблюдения по обновлённому графику без хранения версий, исторические алерты «исправятся», а аудит станет невозможным.

Контроль:

- immutable `schedule_version`;
- `valid_at` и время получения версии;
- сохранение Expected Signature version;
- раздельные `as-observed`, `as-planned-at-the-time`, `recomputed-current-plan`;
- алерт всегда ссылается на конкретную версию плана.

---

# 13. Архитектурные ограничения и критерии готовности

## 13.1 Что допустимо утверждать

- «Объект класса \(k\) наблюдается с вероятностью \(p\)».
- «В видимой зоне число объектов с 90% интервалом составляет \([a,b]\)».
- «Наблюдаемый паттерн совместим/несовместим с Expected Signature».
- «Несоответствие сохраняется в \(n\) независимых окнах».
- «Данных недостаточно из-за закрытия зоны/качества/отсутствия времени».

## 13.2 Что нельзя утверждать без дополнительных данных

- точный физический объём выполненных работ;
- причину задержки;
- виновную сторону;
- нарушение техники безопасности;
- фактический процент готовности скрытых конструкций;
- производительность относительно нормы без нормативов;
- присутствие техники вне поля зрения;
- непрерывную работу между редкими кадрами;
- отставание по срокам по фотографии без timestamp;
- причинную связь между составом техники и изменением графика.

## 13.3 Минимально жизнеспособная итоговая конфигурация

```text
Fine-tuned или проверенный detector
+ frame-quality/OOD
+ camera stabilization
+ ROI/zone model
+ tracking для A или sparse aggregation для B
+ probabilistic counts
+ active/parked/unknown
+ evidence-only ObservedSignature
+ экспертные Expected Signatures
+ likelihood/weighted conformity
+ deviation rules с persistence
+ hysteresis и false-alert budget
+ evidence-based dashboard
+ immutable model/schedule/signature versions
```

## 13.4 Критерий успешности end-to-end системы

Система готова к демонстрации, если для каждого результата она показывает:

1. что именно увидела;
2. где и когда это увидела;
3. насколько наблюдение надёжно;
4. какая часть площадки была реально видна;
5. с какой сигнатурой и версией плана сравнила;
6. какие признаки дали наибольший вклад;
7. какие альтернативные объяснения остаются;
8. какое утверждение она сознательно не делает;
9. почему alert открыт, удерживается или подавлен;
10. как изменится вывод при удалении plan prior.