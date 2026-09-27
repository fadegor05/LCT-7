# LCT-14 — Дата расчёта из настроек (per-площадке, режим last_observation)

**Linear:** LCT-14 — https://linear.app/kaiangel/issue/LCT-14/data-raschyota-iz-nastroek-vmesto-datetoday
**Связано:** LCT-12 (добавила `Clock` в `RecomputeCoordinator`), LCT-11 (домен assessment)

**Базовая ветка:** `claude/laughing-hypatia-20ipgi` (PR #20) — `Clock`/`RecomputeCoordinator` в нужном виде есть только там. Этот PR — **отдельный поверх #20**, не коммит в сам #20 (по итогам ревью PR #20 скоуп зафиксирован на LCT-12+LCT-16, новые задачи в него больше не докидываем).

## Обзор

Предыдущая версия этой спеки (см. git-историю ветки `claude/determined-cannon-lcw9jf`, ныне закрыта) предлагала одну фиксированную дату `ASSESSMENT__AS_OF_OVERRIDE` на всё окружение. Ревью (Антон) указало на реальный изъян: демо-набор содержит площадки из разных лет (2023–2026), и любая ОДНА фиксированная дата оставит часть площадок либо в будущем (сплошной `not_started`), либо настолько далеко в прошлом, что сработает `stale_data`. Единая на всё окружение дата не закрывает Definition of Done тикета.

ML-пайплайн уже решает эту проблему на уровне площадки: `ml/tools/match_schedule.py` берёт `as_of = states[-1]["date"]` — дату **последнего наблюдения на этой конкретной площадке**. Тест паритета в PR #20 (`test_ml_parity.py`) сверяется именно с этим значением per-site. Значит правильный режим для демо — не глобальная дата, а «расчёт как будто сегодня — это дата последнего снимка на площадке».

## Архитектура и компоненты

Новый режим определяется в `AsOfMode` (создаётся в `app/core/settings.py`, не в домене — `AssessmentSettings` держит поле этого типа, а домены зависят от `core`, не наоборот):

- `today` (по умолчанию) — не меняет текущее поведение, `date.today()`.
- `last_observation` — опорная дата = `max(observed_on)` по наблюдениям **этой площадки**. Площадка без наблюдений — fallback на `today`.
- `fixed` — одна дата на всё окружение из `as_of_override` (третий режим, как и предлагалось, на случай если понадобится не по-площадочная, а глобальная дата).

Изменения:
- `backend/app/core/settings.py` — новый `AsOfMode(StrEnum)`, новые поля `AssessmentSettings.as_of_mode`/`as_of_override`.
- `backend/app/domains/assessment/coordinator.py` — новый `AsOfConfig` (dataclass, живёт рядом с `Clock`), новый метод `RecomputeCoordinator._resolve_as_of(observations)`, вызывается в `recompute_site` вместо прямого `self._today()`.
- `backend/app/domains/assessment/provider.py` — провайдер `AsOfConfig` из `Settings`.

`RuleEngine`/`engine.py` **не меняются** — как и раньше, получают уже готовую конкретную `date` в параметре `today`, не знают, как она была вычислена.

## Интерфейсы / контракты

```python
class AsOfConfig:
    mode: AsOfMode
    fixed_date: date | None
```

`RecomputeCoordinator._resolve_as_of(observations: Sequence[ObservationInput]) -> date` — приватный метод:
- `mode == LAST_OBSERVATION` и `observations` непусты → `max(o.observed_on for o in observations)`.
- `mode == LAST_OBSERVATION` и наблюдений нет → `self._today()`.
- `mode == FIXED` и `fixed_date is not None` → `fixed_date`.
- `mode == FIXED` и `fixed_date is None` → `self._today()` (без настроенной даты режим "fixed" бессмыслен — не падаем, тихо откатываемся на "today").
- `mode == TODAY` (или что угодно иное) → `self._today()`.

`RecomputeCoordinator.__init__` получает новый параметр `as_of_config: AsOfConfig | None = None` — если не передан, эквивалентен `AsOfConfig(mode=AsOfMode.TODAY, fixed_date=None)`, так что все существующие прямые вызовы конструктора (тесты) продолжают работать без изменений.

## Обработка ошибок

Нет новых веток исключений. Некорректное значение `ASSESSMENT__AS_OF_MODE` в `.env` (не входящее в `AsOfMode`) — штатная ошибка pydantic при старте процесса, как и для любого другого enum-поля настроек.

## Тестирование

- `backend/tests/test_assessment_coordinator.py`: добавить в `create_coordinator` необязательный параметр `as_of_config`, прокинуть в конструктор. Новые тесты: `last_observation` берёт `max(observed_on)` по площадке; площадка без наблюдений в этом режиме откатывается на `today`; режим `today` (дефолт) не меняет существующее поведение — весь текущий класс `TestRecomputeCoordinator` обязан пройти без изменений (регресс).
- `backend/tests/test_ml_parity.py` — не трогать: он и так строит `RecomputeCoordinator` с явно инъектированным `today`, что эквивалентно текущему поведению по умолчанию (`AsOfMode.TODAY`); новый параметр там не нужен.

## Критерии готовности

- [ ] `AsOfMode`/`AssessmentSettings.as_of_mode`/`as_of_override` добавлены в `core/settings.py`.
- [ ] `AsOfConfig`, `_resolve_as_of`, использование в `recompute_site` — в `coordinator.py`.
- [ ] Провайдер `AsOfConfig` — в `assessment/provider.py`.
- [ ] Существующее поведение (`AsOfMode.TODAY` по умолчанию) не меняется — весь текущий backend-набор тестов зелёный без правок, кроме `test_assessment_coordinator.py`, куда добавляются новые кейсы.
- [ ] Демо: при `ASSESSMENT__AS_OF_MODE=last_observation` площадка с последним наблюдением в 2023 и площадка с последним наблюдением в 2026 обе считаются от СВОЕЙ даты, а не от одной общей — обе не показывают ложный `stale_data`/сплошной `behind`, вызванный исключительно возрастом данных.
- [ ] `.env.dist` документирует `ASSESSMENT__AS_OF_MODE` (`today`/`last_observation`/`fixed`, дефолт `today`) и `ASSESSMENT__AS_OF_OVERRIDE` (используется только при `fixed`).
