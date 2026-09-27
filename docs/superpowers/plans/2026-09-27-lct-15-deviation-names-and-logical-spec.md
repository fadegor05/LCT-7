# LCT-15 — Движок отклонений: имена техники + предупреждение по logical-технике

**Linear:** LCT-15 — https://linear.app/kaiangel/issue/LCT-15/dvizhok-otklonenij-odnoj-zadachej
**Связано:** LCT-11 (домен assessment, движок и координатор уже существуют), LCT-12 (PR #20, база этой ветки)

**Базовая ветка:** `claude/laughing-hypatia-20ipgi` (PR #20) — **отдельный PR поверх #20**, по итогам ревью PR #20 в сам #20 больше не докидываем задачи. Не зависит от LCT-14 (та ветка трогает `Clock`/`AsOfConfig`, эта — независимую от них часть `engine.py`/`coordinator.py`) — обе ветки можно мержить в любом порядке.

## Обзор и ruling по скоупу

Тикет LCT-15 я сам написал по скриншоту плана, без реального кода движка перед глазами. После чтения актуального `engine.py` (700+ строк, уже сложная, протестированная логика из LCT-11) выяснилось: часть пунктов тикета уже реализована («отклонения только по активным этапам» — есть, через `window_started` в `_compute_stage_status`), а часть — реальные, подтверждённые чтением кода дефекты. Беру в эту задачу только **два подтверждённых, чётко очерченных** пункта:

1. **Названия техники вместо UUID.** `_check_stage_deviations` подставляет `eq.equipment_type_id` напрямую в `observed`/`expected` (например: `f"Техника ID: {', '.join(str(eq.equipment_type_id) for eq in ...)}"`) — в STAGE_MISMATCH, IDLE, EXTRA_EQUIPMENT, OUT_OF_ZONE. Каталог типов техники (`EquipmentCatalog`, кэшированный APP-scope сервис с `by_id()`/`all()`) уже существует в `methodology/catalog.py` и уже используется в других доменах (`photo`, `observation`) — просто не был протянут в `engine`/`coordinator`.

2. **Предупреждение по отсутствию `logical`-техники.** `EquipmentRequirementInput.obligation` уже несёт значения `"normative"|"logical"|"auxiliary"`, и `RecomputeCoordinator` уже строит их из методики (`coordinator.py`, сбор `rule_requirements`) — но движок использует только `obligation == "normative"` (маркеры для `missing_equipment`). `"logical"`/`"auxiliary"` участвуют только в множестве `all_required` (для STAGE_MISMATCH/EXTRA_EQUIPMENT), но отсутствие `logical`-техники никогда не даёт собственного предупреждения.

**Осознанно НЕ беру в эту задачу** (более рискованные правки над уже протестированной бизнес-логикой статусов, без возможности свериться с тобой сейчас):
- Дедup простоя/no_progress «один раз на площадку» вместо одного раза на этап — нужно решение по семантике модели данных (отдельная запись на площадку целиком, `stage_id=None`, как у `stale_data`? Или что-то другое?).
- `markers_active_now` в `_compute_stage_status`/`_check_stage_deviations` не привязан к окну конкретного этапа (использует последнее наблюдение по ВСЕЙ площадке, не по этапу) — тонкая правка в статус-логике, покрытой отдельным большим набором тестов (`test_assessment_engine_status.py`, `test_assessment_coordinator.py`), где легко незаметно сломать корректный кейс.

Если после демо эти два пункта всё ещё нужны — заводить отдельными тикетами с реальными репродукциями (как получилось с LCT-16), а не спекулятивно.

## Архитектура и компоненты

- `backend/app/domains/assessment/models.py` — новый `DeviationType.MISSING_LOGICAL_EQUIPMENT`.
- `backend/app/domains/assessment/engine.py`:
  - `RuleEngine.compute_site(..., equipment_names: Mapping[uuid.UUID, str] | None = None)` — новый опциональный параметр (дефолт `None` → пустой dict), чтобы не трогать ~36 существующих вызовов в тестах движка.
  - Новый приватный хелпер `_format_equipment_names(ids, equipment_names) -> str` — резолвит UUID → имя, сортирует, join через `", "`; отсутствующее в словаре имя — fallback на сам UUID (не падает, не теряет данные).
  - `_check_stage_deviations` получает `equipment_names` и прокидывает в 4 существующих места (STAGE_MISMATCH/IDLE/EXTRA_EQUIPMENT/OUT_OF_ZONE) вместо прямой UUID-строки.
  - Новый метод `_check_missing_logical_equipment` + вызов из `_check_stage_deviations` (шаг «2b», сразу после `missing_equipment`).
- `backend/app/domains/assessment/coordinator.py` — `RecomputeCoordinator` получает новую обязательную зависимость `equipment_catalog: EquipmentCatalog` (как и остальные репозитории в конструкторе — не опционально, это такая же core-зависимость), строит `equipment_names = {item.id: item.title for item in await equipment_catalog.all()}` перед вызовом `engine.compute_site(...)` и передаёт его.
- Фронтенд: `frontend/src/api/schemas.ts` (новый литерал в `deviationTypeSchema`), `frontend/src/lib/labels.ts` (новая запись в `deviationTypeLabels` — TS заставит добавить, `Record<DeviationType, string>` иначе не скомпилируется).

`AssessmentProvider` (DI) **не меняется** — `EquipmentCatalog` уже зарегистрирован в контейнере (`methodology/provider.py`, `Scope.APP`), и Dishka автоматически подключит его в конструктор `RecomputeCoordinator` по типу, как и остальные репозитории.

## Интерфейсы / контракты

`RuleEngine.compute_site(stages, rules_by_stage, observations, today, equipment_names=None) -> SiteComputation` — новый параметр keyword-совместим, старые позиционные вызовы (4 аргумента) не ломаются.

`_format_equipment_names(equipment_type_ids: Iterable[uuid.UUID], equipment_names: Mapping[uuid.UUID, str]) -> str` — чистая функция, детерминированный порядок (сортировка по итоговому имени).

Новый `DeviationResult` с `type=MISSING_LOGICAL_EQUIPMENT`: `severity=ATTENTION`, `is_hypothesis=True` (мягкое предупреждение, как IDLE/EXTRA_EQUIPMENT/OUT_OF_ZONE — не блокирует подтверждение этапа, в отличие от `missing_equipment`, который CRITICAL).

## Обработка ошибок

Нет новых веток исключений. `equipment_names.get(eid, str(eid))` — безопасный fallback, если каталог не содержит нужный тип (рассинхрон БД) — деградация до UUID в тексте, не падение.

## Тестирование

- `backend/tests/test_assessment_engine_deviations.py`: новые тесты — имена вместо UUID в `stage_mismatch`/`idle` (проверка, что `observed` содержит переданное имя, а не UUID-строку); отсутствие `equipment_names` (`None`, дефолт) — фоллбэк на UUID в тексте, регресс не допускается; `missing_logical_equipment` срабатывает при отсутствии logical-техники на верифицируемом этапе с высокой наблюдаемостью; НЕ срабатывает, если logical-техника присутствует; НЕ срабатывает, если у правила вообще нет logical-требований.
- `backend/tests/test_assessment_coordinator.py`: обновить `create_coordinator` и прямую конструкцию в `test_ml_parity.py`, чтобы передавать `equipment_catalog` (через `request_container.get(EquipmentCatalog)` — уже зарегистрирован в контейнере). Один новый end-to-end тест: реальные названия типов техники (из `EquipmentType.title`) попадают в `Deviation.observed`/`expected`, а не UUID.
- Весь существующий набор `test_assessment_engine_status.py`/`test_assessment_engine_deviations.py`/`test_assessment_coordinator.py`/`test_ml_parity.py` обязан пройти без изменений (кроме упомянутых точечных правок) — регрессионная гарантия.

## Критерии готовности

- [ ] Ни один `Deviation.observed`/`expected` не содержит сырой UUID техники, если тип есть в каталоге.
- [ ] Отсутствие `logical`-техники на верифицируемом этапе с высокой наблюдаемостью даёт `MISSING_LOGICAL_EQUIPMENT` (ATTENTION, hypothesis).
- [ ] `uv run pytest -q` — весь backend-набор зелёный.
- [ ] `pnpm check` (frontend) — зелёный (в т.ч. `Record<DeviationType, string>` компилируется).
- [ ] На ML-демонаборе (после ручного прогона, опционально) есть хотя бы одно предупреждение вида «экскаватор есть, самосвалов нет» — DoD-пример из тикета.
