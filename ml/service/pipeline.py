"""цепочка «детекции -> статусы этапов» без файлов на диске.

Скрипты `tools/site_state.py` и `tools/match_schedule.py` читают CSV и JSON с
диска: так удобно в исследовании, но не в сервисе. У бэкенда те же данные лежат
в базе, и гонять их через временные файлы незачем.

Этот модуль вызывает те же функции, что и скрипты, — логика одна, расхождения
между «как считали в отчёте» и «как считает сервис» быть не может.

    from service.pipeline import build_report
    report = build_report(observations, schedule)
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML / "tools"))

import match_schedule as ms                      # noqa: E402
import site_state as ss                          # noqa: E402
from parse_schedule import parse_date            # noqa: E402

DEFAULT_RULES = ML / "configs" / "rules.json"
DEFAULT_THRESHOLDS = ML / "configs" / "thresholds.json"


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


def normalise_plan(schedule: list[dict]) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """План из запроса → план по площадкам плюс список отбракованных строк.

    Реальные планы заказчика приходят грязными: в присланном файле 13 строк с
    датой «30.02.2027», а один и тот же этап повторяется несколькими работами.
    Раньше такая строка роняла весь запрос: департамент загружал настоящий план
    и получал 422, то есть сервис выглядел сломанным. Теперь битая строка
    выбрасывается поимённо и попадает в алерт — так же, как кадр без даты.

    Что делаем со строкой:

    - дата не разбирается — строка не участвует в выводах, причина названа;
    - окончание раньше начала — то же самое. Молчаливо принять такую строку
      нельзя: цепочка честно посчитает по ней отставание в сто дней, и это
      будет уверенное число из ничего;
    - этап повторяется — строки сводятся в одну, от самого раннего начала до
      самого позднего окончания. Так же поступает `tools/parse_schedule.py`,
      и расхождение между загрузкой файлом и загрузкой через API недопустимо.
    """
    plans: dict[str, list[dict]] = defaultdict(list)
    issues: dict[str, list[dict]] = defaultdict(list)

    for row in schedule:
        site = row.get("site_id") or ""
        code = row.get("stage_code") or ""
        start, why_start = parse_date(row.get("planned_start"))
        end, why_end = parse_date(row.get("planned_end"))
        if start is None or end is None:
            issues[site].append({"stage_code": code, "reason":
                                 f"дата не распознана ({why_start or why_end})"})
            continue
        if end < start:
            issues[site].append({"stage_code": code,
                                 "reason": f"окончание {end} раньше начала {start}"})
            continue
        plans[site].append({"stage_code": code, "stage_name": row.get("stage_name", ""),
                            "start": start, "end": end, "note": row.get("note", "")})

    merged: dict[str, list[dict]] = {}
    for site, rows in plans.items():
        by_code: dict[str, dict] = {}
        for row in rows:
            seen = by_code.get(row["stage_code"])
            if seen is None:
                by_code[row["stage_code"]] = dict(row, merged_rows=1)
                continue
            seen["start"] = min(seen["start"], row["start"])
            seen["end"] = max(seen["end"], row["end"])
            seen["merged_rows"] += 1
            seen["stage_name"] = seen["stage_name"] or row["stage_name"]
        merged[site] = list(by_code.values())
    return merged, issues


def build_report(observations: list[dict], schedule: list[dict],
                 rules_path: Path = DEFAULT_RULES,
                 thresholds_path: Path | None = DEFAULT_THRESHOLDS,
                 conf: float = ss.DEFAULT_CONF) -> dict:
    """Отчёт по площадкам из детекций и календарного плана.

    observations: [{"image", "site_id", "date", "width", "height", "detections": [...]}]
        — по одной записи на кадр, детекции в формате контракта §1.
        Кадры без `site_id` или `date` в анализ не попадают и учитываются
        отдельно: это дыра в данных, а не отсутствие работ (Q&A 13:01).
    schedule: [{"site_id", "stage_code", "stage_name", "planned_start", "planned_end"}]
    """
    records, sites = [], {}
    for obs in observations:
        name = obs.get("image") or ""
        records.append({"image": name, "width": obs.get("width", 0),
                        "height": obs.get("height", 0),
                        "detections": obs.get("detections", [])})
        sites[name] = (obs.get("site_id") or "", str(obs.get("date") or "")[:10])

    thresholds = ss.load_thresholds(thresholds_path if thresholds_path
                                    and Path(thresholds_path).exists() else None)
    states, _skipped, unusable = ss.build_states(records, sites, thresholds, conf)

    by_site: dict[str, list[dict]] = defaultdict(list)
    for state in states:
        state["_date"] = _as_date(state["date"])
        by_site[state["site_id"]].append(state)
    for group in by_site.values():
        group.sort(key=lambda s: s["_date"])

    plans, plan_issues = normalise_plan(schedule)

    rules, specific = ms.load_rules(Path(rules_path))
    # Площадка, у которой не разобралась ни одна строка плана, в `plans` не
    # попадает. Брать ключи только оттуда значит потерять её вместе с
    # предупреждением — то есть ровно тот молчаливый пропуск, против которого
    # разбор и делался. Поэтому идём по объединению.
    reports = [ms.site_report(site, plans.get(site, []), rules, by_site.get(site, []),
                              specific, unusable.get(site), plan_issues.get(site))
               for site in sorted(set(plans) | set(plan_issues))]

    covered = sum(s["n_images"] for s in states)
    return {
        "meta": {
            "frames_in": len(records),
            "frames_used": covered,
            "frames_unusable": sum(sum(v.values()) for v in unusable.values()),
            "observations": len(states),
            "sites": len(reports),
            "conf": conf,
            "rules": Path(rules_path).name,
            "plan_rows_in": len(schedule),
            "plan_rows_used": sum(len(p) for p in plans.values()),
            "plan_rows_rejected": sum(len(v) for v in plan_issues.values()),
        },
        "sites": reports,
    }


def summary(report: dict) -> dict:
    """Короткая сводка для интерфейса: сколько чего, без разбора по площадкам."""
    statuses: Counter = Counter()
    alerts: Counter = Counter()
    for site in report["sites"]:
        for stage in site["stages"]:
            statuses[stage["status"]] += 1
        for alert in site.get("alerts", []):
            alerts[alert["type"]] += 1
    return {"statuses": dict(statuses), "alerts": dict(alerts), **report["meta"]}
