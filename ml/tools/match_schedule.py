# -*- coding: utf-8 -*-
"""Сопоставление наблюдений с календарным планом: статус этапа и алерты.

Третье звено пайплайна. На входе состояние площадок по датам (site_state.py),
методика «этап → техника» (configs/rules.json) и план (schedule). На выходе —
то, что просили постановщики (Q&A 18:11, 36:10): по каждому этапу графика
отставание, соответствие или опережение, плюс объясняющие алерты.

Два принципа, заложенные в логику:

1. Техника с обязательностью `logical` — самосвал, автобетоносмеситель — в
   разделах «Машины и механизмы» ГЭСН отсутствует: перевозка и бетон нормируются
   отдельно. Поэтому её отсутствие НЕ опровергает этап, а её наличие не
   доказывает. Этап считается наблюдаемым по `normative`-технике.

2. «Работы не ведутся» и «мы этого не видели» — разные утверждения. Первое
   говорит о стройке, второе о наших данных. Статусы `not_started` и
   `not_observed` не смешиваются.

Тексты объяснений собираются по шаблонам из тех же полей, что попадают в отчёт:
ни одного числа, которого нет в структуре. Это и делает вывод проверяемым.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path


def parse_date(value: str) -> date:
    return datetime.strptime(value.strip(), "%Y-%m-%d").date()


def load_schedule(path: Path) -> dict[str, list[dict]]:
    plans: dict[str, list[dict]] = defaultdict(list)
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh, delimiter=";"):
            plans[row["site_id"]].append({
                "stage_code": row["stage_code"],
                "stage_name": row["stage_name"],
                "start": parse_date(row["planned_start"]),
                "end": parse_date(row["planned_end"]),
                "note": row.get("note", ""),
            })
    return plans


def load_rules(path: Path) -> tuple[dict[str, dict], set[str]]:
    """Правила по коду этапа; укрупнённое правило доступно по каждому исходному коду.

    D-011 сводит неразличимые по технике работы в один наблюдаемый этап (например,
    фундаментную плиту и монолит ниже нуля). В графике заказчика коды остаются
    исходными, поэтому объединённое правило регистрируется под всеми ними.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    specific = set(data["meta"].get("class_specificity", {}).get("specific", []))
    rules = {}
    for r in data["rules"]:
        rules[r["stage_code"]] = r
        for code in r.get("merged_from", []):
            rules[code] = r
    return rules, specific


def load_states(path: Path) -> dict[str, list[dict]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    by_site: dict[str, list[dict]] = defaultdict(list)
    for state in data["states"]:
        state["_date"] = parse_date(state["date"])
        by_site[state["site_id"]].append(state)
    for states in by_site.values():
        states.sort(key=lambda s: s["_date"])
    return by_site


def match_variant(equipment: dict[str, int], variant: dict, specific: set[str]) -> dict:
    """Насколько состояние площадки удовлетворяет одному варианту технологии.

    Этап подтверждается специфичной машиной (буровая, копёр, асфальтоукладчик) —
    она привязана к узкому кругу работ. Универсальная техника (экскаватор,
    башенный кран, самосвал) сама по себе не доказывает ничего: экскаватор
    встречается почти на всех этапах подземной части, а башенный кран стоит на
    площадке месяцами. Когда специфичных машин в варианте нет, требуется весь
    набор целиком, включая logical: «экскаватор И самосвал», а не просто
    «экскаватор».
    """
    present, missing_normative, missing_logical = [], [], []
    for item in variant.get("required", []):
        have = equipment.get(item["class"], 0)
        need = item.get("min", 1)
        if have >= need:
            present.append({"class": item["class"], "count": have, "need": need})
        elif item.get("obligation") == "logical":
            missing_logical.append(item)
        else:
            missing_normative.append(item)

    auxiliary = [a["class"] for a in variant.get("auxiliary", [])
                 if equipment.get(a["class"], 0) > 0]

    specific_present = [p["class"] for p in present if p["class"] in specific]
    observed = bool(present) and not missing_normative and (
        bool(specific_present) or not missing_logical)

    return {
        "variant": variant.get("name", ""),
        "present": present,
        "missing_normative": missing_normative,
        "missing_logical": missing_logical,
        "auxiliary_present": auxiliary,
        "specific_present": specific_present,
        "observed": observed,
        "evidence_strength": ("specific" if specific_present
                              else "generic_full" if observed else "insufficient"),
    }


def match_stage(equipment: dict[str, int], rule: dict, specific: set[str]) -> dict:
    """Лучший из вариантов технологии: сначала наблюдаемые, затем более полные."""
    matches = [match_variant(equipment, v, specific) for v in rule.get("variants", [])]
    if not matches:
        return {"observed": False, "variant": "", "present": [], "specific_present": [],
                "missing_normative": [], "missing_logical": [], "auxiliary_present": [],
                "evidence_strength": "insufficient"}
    return max(matches, key=lambda m: (m["observed"], len(m["present"]),
                                       -len(m["missing_normative"])))


def unexpected_present(equipment: dict[str, int], rule: dict) -> list[str]:
    return [u["class"] for u in rule.get("unexpected", []) if equipment.get(u["class"], 0) > 0]


def stage_status(stage: dict, rule: dict | None, states: list[dict],
                 specific: set[str]) -> tuple[dict, list[dict]]:
    """Статус одного этапа плана плюс алерты по нему."""
    code, name = stage["stage_code"], stage["stage_name"]
    base = {"stage_code": code, "stage_name": name,
            "planned": {"start": stage["start"].isoformat(), "end": stage["end"].isoformat()}}

    if rule is None:
        return {**base, "status": "not_checkable",
                "basis": "для этапа нет правила в методике"}, []
    if not rule.get("checkable_by_equipment", True):
        return {**base, "status": "not_checkable",
                "basis": rule.get("note", "этап не определяется по технике")}, []

    matches = [(s, match_stage(s["equipment"], rule, specific)) for s in states]
    observed = [(s, m) for s, m in matches if m["observed"]]
    alerts: list[dict] = []

    if not states:
        return {**base, "status": "not_observed",
                "basis": "по этой площадке нет ни одного наблюдения"}, []

    last_observation = states[-1]["_date"]

    if observed:
        dates = [s["_date"] for s, _ in observed]
        first, last = min(dates), max(dates)
        best = observed[-1][1]

        if last > stage["end"]:
            status, delay = "behind", (last - stage["end"]).days
            basis = "работы наблюдаются после плановой даты окончания"
        elif first < stage["start"]:
            status, delay = "ahead", (stage["start"] - first).days
            basis = "работы наблюдаются раньше планового начала"
        else:
            status, delay = "on_track", 0
            basis = "наблюдения попадают в плановое окно"

        # Логическая техника отсутствует — повод для алерта, но не для вывода
        # об этапе: в нормах её нет, и по снимку её отсутствие не доказуемо.
        if best["missing_logical"]:
            missing = ", ".join(i["class"] for i in best["missing_logical"])
            present = ", ".join(f"{p['class']} x{p['count']}" for p in best["present"])
            alerts.append({
                "type": "missing_equipment",
                "stage_code": code,
                "window": {"from": first.isoformat(), "to": last.isoformat()},
                "expected": missing,
                "observed": present,
                "confidence": "low",
                "evidence": sorted({img for s, _ in observed for img in s["images"]})[:4],
                "rules_fired": [f"{code}/{best['variant']}"],
                "explanation": (f"На этапе «{name}» наблюдается {present}, "
                                f"но не наблюдается {missing}."),
                "cannot_claim": ("Эта техника в нормах ГЭСН для этапа не значится: перевозка "
                                 "и доставка бетона нормируются отдельно. Её отсутствие на "
                                 "снимках не доказывает остановку работ."),
            })
        return {**base, "status": status, "delay_days": delay,
                "evidence_dates": [d.isoformat() for d in sorted(dates)],
                "matched_variant": best["variant"],
                "evidence_strength": best["evidence_strength"],
                "observed_equipment": [f"{p['class']} x{p['count']}" for p in best["present"]],
                "basis": basis, "confidence": "medium"}, alerts

    # Наблюдений этапа нет — различаем «не начато» и «не видели».
    in_window = [s for s in states if stage["start"] <= s["_date"] <= stage["end"]]
    if not in_window and last_observation < stage["start"]:
        return {**base, "status": "not_observed",
                "basis": "снимков в плановом окне нет, последнее наблюдение раньше начала"}, []

    if last_observation >= stage["start"]:
        delay = (last_observation - stage["start"]).days
        sample = [s for s in states if s["_date"] >= stage["start"]] or states
        best_rule_variant = rule["variants"][0]["name"] if rule.get("variants") else ""
        required = ", ".join(i["class"] for v in rule.get("variants", [])
                             for i in v.get("required", []) if i.get("obligation") != "logical")
        observed_now = ", ".join(f"{k} x{v}" for k, v in sample[-1]["equipment"].items()) or "техника не обнаружена"
        alerts.append({
            "type": "stage_not_started",
            "stage_code": code,
            "window": {"from": stage["start"].isoformat(), "to": last_observation.isoformat()},
            "expected": required,
            "observed": observed_now,
            "confidence": "medium",
            "evidence": sample[-1]["images"][:4],
            "rules_fired": [f"{code}/{best_rule_variant}"],
            "explanation": (f"Плановое начало этапа «{name}» — {stage['start'].isoformat()}. "
                            f"На снимках от {last_observation.isoformat()} техника этапа "
                            f"не наблюдается; видно: {observed_now}."),
            "cannot_claim": ("Снимки покрывают не всю площадку и не всё время. Отсутствие "
                             "техники в кадре не доказывает, что работы не ведутся."),
        })
        return {**base, "status": "not_started", "delay_days": delay,
                "evidence_dates": [s["date"] for s in sample],
                "basis": "плановое начало прошло, техника этапа не наблюдается",
                "confidence": "medium"}, alerts

    return {**base, "status": "not_observed",
            "basis": "наблюдений в плановом окне нет"}, []


def site_report(site_id: str, plan: list[dict], rules: dict[str, dict],
                states: list[dict], specific: set[str]) -> dict:
    stages, alerts = [], []
    for stage in sorted(plan, key=lambda s: s["start"]):
        status, stage_alerts = stage_status(stage, rules.get(stage["stage_code"]), states, specific)
        stages.append(status)
        alerts.extend({**a, "site_id": site_id} for a in stage_alerts)

    # Неожиданная техника: проверяется по этапам, активным на дату наблюдения.
    for state in states:
        for stage in plan:
            if not (stage["start"] <= state["_date"] <= stage["end"]):
                continue
            rule = rules.get(stage["stage_code"])
            if not rule:
                continue
            found = unexpected_present(state["equipment"], rule)
            if found:
                alerts.append({
                    "type": "unexpected_equipment",
                    "site_id": site_id,
                    "stage_code": stage["stage_code"],
                    "window": {"from": state["date"], "to": state["date"]},
                    "expected": "техника этапа " + stage["stage_name"],
                    "observed": ", ".join(found),
                    "confidence": "low",
                    "evidence": state["images"][:4],
                    "rules_fired": [f"{stage['stage_code']}/unexpected"],
                    "explanation": (f"На дату {state['date']} по плану идёт этап "
                                    f"«{stage['stage_name']}», но наблюдается {', '.join(found)}."),
                    "cannot_claim": ("Списки несовместимой техники в нормах отсутствуют — это "
                                     "гипотеза методики, а не нарушение норматива."),
                })

    # Отсутствие изменений между соседними наблюдениями.
    for prev, cur in zip(states, states[1:]):
        if prev["equipment"] == cur["equipment"] and prev["equipment"]:
            alerts.append({
                "type": "no_progress",
                "site_id": site_id,
                "stage_code": "",
                "window": {"from": prev["date"], "to": cur["date"]},
                "expected": "изменение состава техники",
                "observed": ", ".join(f"{k} x{v}" for k, v in cur["equipment"].items()),
                "confidence": "low",
                "evidence": cur["images"][:4],
                "rules_fired": [],
                "explanation": (f"Состав техники не изменился с {prev['date']} по {cur['date']}."),
                "cannot_claim": ("Одинаковый состав техники не означает отсутствия работ: "
                                 "между съёмками могли смениться объёмы, а не машины."),
            })

    return {
        "site_id": site_id,
        "as_of": states[-1]["date"] if states else None,
        "observations": len(states),
        "stages": stages,
        "alerts": alerts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--state", type=Path, default=Path("data/processed/site_state.json"))
    parser.add_argument("--rules", type=Path, default=Path("configs/rules.json"))
    parser.add_argument("--schedule", type=Path, default=Path("data/reference/schedule_demo.csv"))
    parser.add_argument("-o", "--out", type=Path, default=Path("data/processed/report.json"))
    args = parser.parse_args()

    plans = load_schedule(args.schedule)
    rules, specific = load_rules(args.rules)
    states_by_site = load_states(args.state)

    reports = [site_report(site, plan, rules, states_by_site.get(site, []), specific)
               for site, plan in sorted(plans.items())]
    if not reports:
        print("в графике нет ни одной площадки", file=sys.stderr)
        return 1

    payload = {
        "meta": {
            "state": str(args.state),
            "rules": str(args.rules),
            "schedule": str(args.schedule),
            "created": datetime.now().isoformat(timespec="seconds"),
        },
        "sites": reports,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    labels = {"ahead": "опережение", "on_track": "в графике", "behind": "отставание",
              "not_started": "не начат", "not_observed": "нет наблюдений",
              "not_checkable": "не проверяется по технике"}
    for report in reports:
        print(f"\n=== {report['site_id']}  (наблюдений: {report['observations']}, "
              f"на дату: {report['as_of']}) ===")
        for stage in report["stages"]:
            delay = stage.get("delay_days")
            tail = f", {delay} дн." if delay else ""
            print(f"  {stage['stage_code']:9s} {stage['stage_name'][:44]:46s} "
                  f"{labels[stage['status']]}{tail}")
        for alert in report["alerts"]:
            print(f"    [{alert['type']}] {alert['explanation']}")

    total = sum(len(r["alerts"]) for r in reports)
    print(f"\nвсего алертов: {total}\nрезультат: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
