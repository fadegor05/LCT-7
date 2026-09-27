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

DEFAULT_RULES = ML / "configs" / "rules.json"
DEFAULT_THRESHOLDS = ML / "configs" / "thresholds.json"


def _as_date(value) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


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

    plans: dict[str, list[dict]] = defaultdict(list)
    for row in schedule:
        plans[row["site_id"]].append({
            "stage_code": row["stage_code"],
            "stage_name": row.get("stage_name", ""),
            "start": _as_date(row["planned_start"]),
            "end": _as_date(row["planned_end"]),
            "note": row.get("note", ""),
        })

    rules, specific = ms.load_rules(Path(rules_path))
    reports = [ms.site_report(site, plan, rules, by_site.get(site, []), specific,
                              unusable.get(site))
               for site, plan in sorted(plans.items())]

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
