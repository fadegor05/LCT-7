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
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
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


NO_PROGRESS_SIM = 0.8     # похожесть составов техники, выше которой считаем «то же самое»
NO_PROGRESS_DAYS = 14     # минимальный разрыв между наблюдениями, иначе сравнивать нечего


def load_unusable(path: Path) -> dict[str, dict]:
    """Кадры, не дошедшие до цепочки: нет даты или нет привязки к площадке."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("meta", {}).get("unusable_frames", {})


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
        # Это не то же самое, что not_checkable. «Не проверяется по технике» —
        # свойство этапа (гидроизоляцию по машинам не увидишь). «Нет правила» —
        # дыра в нашей настройке: заказчик прислал код, которого нет в методике.
        # Свалить их в один статус опасно: план с чужой нумерацией целиком стал
        # бы «не проверяется», и система молча выглядела бы работающей.
        return {**base, "status": "no_rule",
                "basis": f"кода «{code}» нет в методике configs/rules.json"}, []
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

        # Отставание — главный вывод системы по ТЗ («отставание либо соответствие
        # графику», Q&A 18:33), поэтому оно должно попадать в список отклонений,
        # а не оставаться строкой в таблице статусов.
        if status == "behind":
            alerts.append({
                "type": "stage_behind",
                "stage_code": code,
                "window": {"from": first.isoformat(), "to": last.isoformat()},
                "expected": f"завершение к {stage['end'].isoformat()}",
                "observed": f"работы этапа наблюдаются {last.isoformat()}",
                "confidence": "medium" if best["specific_present"] else "low",
                "observability": "medium",
                "evidence": sorted({img for st, _ in observed for img in st["images"]})[:4],
                "rules_fired": [f"{code}/{best['variant']}"],
                "explanation": (f"Этап «{name}» отстаёт на {delay} дн.: плановое окончание "
                                f"{stage['end'].isoformat()}, а работы наблюдаются "
                                f"{last.isoformat()}" +
                                (f" (подтверждение: {', '.join(best['specific_present'])})."
                                 if best["specific_present"]
                                 else " по полному набору универсальной техники.")),
                "cannot_claim": ("Отставание измерено по снимкам: работы этапа видны после "
                                 "плановой даты. Объём невыполненных работ и новый срок "
                                 "завершения по фотографиям не определяются."),
            })

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


MIN_SAMPLES = 10          # меньше — доля простоя статистически бессмысленна


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Интервал Уилсона: в отличие от нормального приближения не схлопывается
    в точку при доле 0 или 1 и корректен на малых выборках."""
    if not n:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    hw = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return max(0.0, c - hw), min(1.0, c + hw)


def work_sampling(states: list[dict]) -> list[dict]:
    """Доля наблюдений без признаков вовлечённости, по классам техники.

    Метод work sampling (в строительном производственном анализе с 1930-х): одно
    наблюдение — один мгновенный замер, ответ бинарный, оценка — доля с
    доверительным интервалом. Вердикта «машина простаивает» по одному кадру не
    даём: он не наблюдаем (research/part_N_activity.md).

    Интервал — нормальное приближение, z = 1.96. При малом N он широкий, и это
    честно: на десятке наблюдений доля простоя не измеряется.
    """
    agg: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for st in states:
        for cls, counts in (st.get("engagement") or {}).items():
            for k, v in counts.items():
                agg[cls][k] += v
    out = []
    for cls, c in sorted(agg.items()):
        engaged, not_engaged = c.get("engaged", 0), c.get("not_engaged", 0)
        decided = engaged + not_engaged
        total = decided + c.get("unknown", 0)
        if not total:
            continue
        row = {"class": cls, "observations": total, "decided": decided,
               "engaged": engaged, "not_engaged": not_engaged,
               "unknown": c.get("unknown", 0)}
        # Порог: на единичных наблюдениях доля не оценивается. Без него отчёт
        # напечатал бы «0% ±0 п.п.» по одному кадру — ложная точность.
        if decided >= MIN_SAMPLES:
            p = not_engaged / decided
            lo, hi = wilson(not_engaged, decided)
            row["not_engaged_share"] = round(p, 3)
            row["ci95"] = [round(lo, 3), round(hi, 3)]
            row["basis"] = (f"{decided} наблюдений с определённым ответом из {total}; "
                            f"доля без признаков вовлечённости {p:.0%} "
                            f"(интервал {lo:.0%}–{hi:.0%})")
        else:
            row["basis"] = (f"определённый ответ дан по {decided} наблюдениям из {total} — "
                            f"меньше порога {MIN_SAMPLES}, доля не оценивается")
        out.append(row)
    return out


def forecast(stages: list[dict], plan: list[dict]) -> dict:
    """Прогноз сроков: насколько сдвинется завершение, если задержка не нагоняется.

    Чего мы **не** делаем: не предсказываем срок по объёму выполненных работ —
    объём по снимкам не измеряется (D-016). Здесь арифметика графика, а не модель.

    Допущение одно и названо явно: этапы идут последовательно, и задержка
    переносится на те, что начинаются после окончания задержавшегося. Если
    подрядчик нагонит темп или пустит работы параллельно, сдвиг будет меньше.
    Поэтому это **верхняя оценка**, и в отчёте она помечена как таковая.
    """
    delayed = [(st["stage_code"], st.get("delay_days") or 0, st["planned"]["end"])
               for st in stages
               if st["status"] in ("behind", "not_started") and st.get("delay_days")]
    if not delayed:
        return {"shift_days": 0, "basis": "задержавшихся этапов нет"}

    by_code = {st["stage_code"]: st for st in stages}
    shifted = []
    for item in plan:
        code = item["stage_code"]
        own = by_code.get(code, {}).get("delay_days") or 0
        # сдвиг от предшественников: берём максимум по тем, что должны были
        # закончиться до начала этого этапа
        inherited = max((d for c, d, end in delayed
                         if parse_date(end) <= item["start"] and c != code), default=0)
        total = max(own, inherited)
        if total:
            shifted.append({
                "stage_code": code,
                "stage_name": item["stage_name"],
                "planned_end": item["end"].isoformat(),
                "projected_end": (item["end"] + timedelta(days=total)).isoformat(),
                "shift_days": total,
            })

    worst = max((s["shift_days"] for s in shifted), default=0)
    last_planned = max(item["end"] for item in plan)
    return {
        "shift_days": worst,
        "planned_completion": last_planned.isoformat(),
        "projected_completion": (last_planned + timedelta(days=worst)).isoformat(),
        "stages": shifted,
        "basis": (f"наибольшая наблюдаемая задержка {worst} дн. переносится на "
                  f"последующие этапы; завершение сдвигается с "
                  f"{last_planned.isoformat()} на "
                  f"{(last_planned + timedelta(days=worst)).isoformat()}"),
        "assumption": ("этапы считаются последовательными, задержка не нагоняется. "
                       "Это верхняя оценка сдвига"),
        "cannot_claim": ("Срок не рассчитан по объёму выполненных работ: объём по "
                         "снимкам не измеряется. Это перенос наблюдаемой задержки по "
                         "графику, а не прогноз производительности подрядчика."),
    }


def site_report(site_id: str, plan: list[dict], rules: dict[str, dict],
                states: list[dict], specific: set[str],
                unusable: dict[str, int] | None = None,
                plan_issues: list[dict] | None = None) -> dict:
    stages, alerts = [], []

    # Дыра в данных — не то же самое, что отсутствие работ. Заказчик просил
    # предупреждать, что часть площадки или периода вне контроля (Q&A 13:01).
    sampling = work_sampling(states)

    if unusable:
        total = sum(unusable.values())
        reasons = ", ".join(f"{k}: {v}" for k, v in sorted(unusable.items()))
        alerts.append({
            "type": "unusable_data",
            "site_id": site_id,
            "confidence": "high",
            "observability": "low",
            "explanation": f"{total} кадр(ов) площадки не участвуют в анализе ({reasons}). "
                           f"Выводы по этой площадке построены только на кадрах с датой.",
            "cannot_claim": "Отсутствие наблюдений на этих кадрах не означает отсутствия работ: "
                            "кадры исключены из-за неполных данных, а не из-за пустой площадки.",
        })
    # Строки плана, которые не удалось разобрать, — такая же дыра в данных, как
    # кадр без даты, и прятать её нельзя: по выброшенной строке выводов не будет,
    # а заказчик считает, что этап под контролем.
    if plan_issues:
        reasons = "; ".join(f"{i['stage_code'] or 'без кода'}: {i['reason']}"
                            for i in plan_issues[:5])
        more = f" и ещё {len(plan_issues) - 5}" if len(plan_issues) > 5 else ""
        alerts.append({
            "type": "plan_invalid",
            "site_id": site_id,
            "confidence": "high",
            "observability": "low",
            "explanation": (f"{len(plan_issues)} строк(и) календарного плана не разобраны "
                            f"и не участвуют в выводах ({reasons}{more})."),
            "cannot_claim": ("По этим этапам система не говорит ничего: строка отброшена "
                             "из-за ошибки в плане, а не потому, что работы не идут. "
                             "Исправьте строку и загрузите план заново."),
        })

    # Часть техники могла прийти не из распознавания, а из реестра неподвижных
    # машин (tools/registered_equipment.py). Это утверждение оператора, и отчёт
    # обязан сказать об этом сам: иначе ручной ввод неотличим от зрения.
    from_registry: Counter = Counter()
    for state in states:
        for cls, n in (state.get("registered_equipment") or {}).items():
            from_registry[cls] = max(from_registry[cls], n)
    if from_registry:
        listed = ", ".join(f"{cls} x{n}" for cls, n in sorted(from_registry.items()))
        alerts.append({
            "type": "registered_equipment",
            "site_id": site_id,
            "confidence": "high",
            "observability": "low",
            "explanation": (f"В выводах по этой площадке учтена техника из реестра "
                            f"неподвижных машин: {listed}. Она не распознана на снимках, "
                            f"а внесена оператором при настройке камеры."),
            "cannot_claim": ("Присутствие этой техники система не проверяла по кадрам: "
                             "это запись в настройке, а не наблюдение. Если машину "
                             "увезли раньше срока, отчёт об этом не узнает — период "
                             "действия записи задаёт оператор."),
        })

    for stage in sorted(plan, key=lambda s: s["start"]):
        status, stage_alerts = stage_status(stage, rules.get(stage["stage_code"]), states, specific)
        stages.append(status)
        alerts.extend({**a, "site_id": site_id} for a in stage_alerts)

    # Коды без правила собираем в один алерт по площадке. Поштучно это был бы
    # шум, а одной строкой видно масштаб: «из 14 этапов методика знает 2».
    no_rule = [st["stage_code"] for st in stages if st["status"] == "no_rule"]
    if no_rule:
        alerts.append({
            "type": "unknown_stages",
            "site_id": site_id,
            "confidence": "high",
            "observability": "low",
            "explanation": (f"{len(no_rule)} из {len(stages)} этапов плана не описаны в "
                            f"методике: {', '.join(no_rule[:8])}"
                            + (" и др." if len(no_rule) > 8 else "") +
                            ". По ним система выводов не делает."),
            "cannot_claim": ("Отсутствие правила — пробел в настройке, а не заключение о "
                             "стройке. Добавьте этап в configs/rules.json, и он начнёт "
                             "проверяться без изменения кода."),
        })

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
    #
    # Раньше условием было полное совпадение состава техники — на реальных сериях
    # такого не бывает, и алерт не срабатывал ни разу. Считаем похожесть составов
    # (Жаккар по классам): при 0.8 и выше состав «практически тот же».
    for prev, cur in zip(states, states[1:]):
        a, b = set(prev["equipment"]), set(cur["equipment"])
        if not a or not b:
            continue
        sim = len(a & b) / len(a | b)
        days = (cur["_date"] - prev["_date"]).days
        if sim >= NO_PROGRESS_SIM and days >= NO_PROGRESS_DAYS:
            alerts.append({
                "type": "no_progress",
                "site_id": site_id,
                "stage_code": "",
                "window": {"from": prev["date"], "to": cur["date"]},
                "expected": "смена состава техники за период",
                "observed": ", ".join(f"{k} x{v}" for k, v in cur["equipment"].items()),
                "confidence": "low",
                "observability": "medium",
                "evidence": cur["images"][:4],
                "rules_fired": [],
                "explanation": (f"За {days} дней (с {prev['date']} по {cur['date']}) состав техники "
                                f"совпадает на {sim:.0%}: те же классы, что и в прошлое наблюдение."),
                "cannot_claim": ("Одинаковый состав техники не означает отсутствия работ: между "
                                 "съёмками могли смениться объёмы, а не машины."),
            })

    # Застой этапа: работы одного этапа наблюдаются после планового окончания
    # на протяжении нескольких наблюдений подряд. Это и есть «прогноз задержки»
    # в наблюдаемой форме (Q&A 12:52): не модель, а измеренный сдвиг.
    for stage in plan:
        rule = rules.get(stage["stage_code"])
        if not rule or not rule.get("checkable_by_equipment", True):
            continue
        seen = [st for st in states
                if match_stage(st["equipment"], rule, specific)["observed"]]
        if len(seen) < 3:
            continue
        last, first = seen[-1], seen[0]
        overdue = (last["_date"] - stage["end"]).days
        if overdue <= 0:
            continue
        span = (last["_date"] - first["_date"]).days
        alerts.append({
            "type": "stage_stalled",
            "site_id": site_id,
            "stage_code": stage["stage_code"],
            "window": {"from": first["date"], "to": last["date"]},
            "expected": f"завершение к {stage['end'].isoformat()}",
            "observed": f"работы этапа наблюдаются на {len(seen)} датах за {span} дн.",
            "confidence": "medium",
            "observability": "medium",
            "evidence": last["images"][:4],
            "rules_fired": [f"{stage['stage_code']}/stalled"],
            "explanation": (f"Этап «{stage['stage_name']}» наблюдается на {len(seen)} наблюдениях "
                            f"подряд и продолжается через {overdue} дн. после планового окончания "
                            f"{stage['end'].isoformat()}. Признаков перехода к следующему этапу нет."),
            "cannot_claim": ("Срок завершения по этим данным не предсказывается: объём выполненных "
                             "работ по снимкам не измеряется, видно только продолжение этапа."),
        })

    return {
        "site_id": site_id,
        "as_of": states[-1]["date"] if states else None,
        "observations": len(states),
        "stages": stages,
        "equipment_engagement": sampling,
        "forecast": forecast(stages, plan),
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

    unusable = load_unusable(args.state)
    reports = [site_report(site, plan, rules, states_by_site.get(site, []), specific,
                           unusable.get(site))
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
