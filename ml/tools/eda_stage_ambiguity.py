# -*- coding: utf-8 -*-
"""E5: насколько состав техники определяет этап работ.

Открытый пункт гейта G1-03 из `docs/ML_ACTION_PLAN.md` §3.4: хватает ли правил
по технике или нужны признаки сцены. Вопрос решается арифметикой по той же
методике, что работает в пайплайне, — `configs/rules.json` и функция
``match_stage`` из ``tools/match_schedule.py``. Ничего не обучается.

Считаются три вещи:

1. **Неоднозначность наблюдения** — для каждого реального наблюдения
   «площадка + дата» из ручной разметки: сколько этапов методика признаёт
   наблюдаемыми одновременно. Больше одного — значит по технике этап не
   определяется однозначно.
2. **Специфичность класса** — сколько этапов подтверждает каждая машина, взятая
   в одиночку. Это проверка деления specific/generic из `configs/rules.json`
   числом, а не рассуждением.
3. **Различимость этапов** — пары этапов, которые подтверждаются одним и тем же
   набором техники и потому неразличимы в принципе.

Запуск::

    python tools/eda_stage_ambiguity.py
"""

from __future__ import annotations

import itertools
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from match_schedule import load_rules, match_stage  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RULES = ROOT / "configs" / "rules.json"
ORACLE = ROOT / "data" / "processed" / "site_state_oracle.json"


def checkable(rules: dict) -> dict:
    return {c: r for c, r in rules.items() if r.get("checkable_by_equipment", True)}


def observed_stages(equipment: dict[str, int], rules: dict, specific: set) -> list[tuple]:
    out = []
    for code, rule in rules.items():
        m = match_stage(equipment, rule, specific)
        if m["observed"]:
            out.append((code, rule["stage_name"], m["evidence_strength"]))
    return out


def part1(rules: dict, specific: set) -> None:
    print("\n=== 1. Неоднозначность реальных наблюдений (ручная разметка) ===")
    states = json.loads(ORACLE.read_text(encoding="utf-8"))["states"]
    counts = []
    for s in states:
        hits = observed_stages(s["equipment"], rules, specific)
        counts.append(len(hits))
        print(f"\n{s['site_id']} {s['date']}  кадров={s['n_images']}  "
              f"техника: {', '.join(f'{k}x{v}' for k, v in s['equipment'].items())}")
        if not hits:
            print("    ни один этап не подтверждается")
        for code, name, strength in hits:
            print(f"    {code:9} {name[:44]:46} {strength}")
    print(f"\nнаблюдений: {len(counts)}; "
          f"подтверждают 0 этапов: {counts.count(0)}, "
          f"ровно 1: {counts.count(1)}, "
          f"2 и более: {sum(1 for c in counts if c >= 2)}")
    if counts:
        print(f"в среднем этапов на наблюдение: {sum(counts) / len(counts):.1f}")


def part2(rules: dict, specific: set) -> None:
    print("\n=== 2. Специфичность класса: сколько этапов подтверждает одна машина ===")
    classes = sorted({
        item["class"]
        for rule in rules.values()
        for variant in rule.get("variants", [])
        for item in variant.get("required", [])
    })
    print(f"{'класс':20}{'один':>6}{'+самосвал':>11}{'+миксер':>9}  подтверждаемые этапы (в одиночку)")
    for cls in classes:
        alone = observed_stages({cls: 2}, rules, specific)
        with_truck = observed_stages({cls: 2, "dump_truck": 2}, rules, specific)
        with_mixer = observed_stages({cls: 2, "concrete_mixer": 2}, rules, specific)
        tag = "spec" if cls in specific else "gen "
        print(f"{cls:20}{len(alone):>6}{len(with_truck):>11}{len(with_mixer):>9}  "
              f"[{tag}] {', '.join(c for c, _, _ in alone) or '—'}")


def part3(rules: dict, specific: set) -> None:
    print("\n=== 3. Пары этапов, неразличимые по технике ===")
    sets = {}
    for code, rule in rules.items():
        req = set()
        for variant in rule.get("variants", []):
            req |= {i["class"] for i in variant.get("required", [])}
        sets[code] = req
    shown = 0
    for a, b in itertools.combinations(sorted(sets), 2):
        inter = sets[a] & sets[b]
        if not inter:
            continue
        # неразличимы, если набор одного целиком лежит в наборе другого
        if sets[a] <= sets[b] or sets[b] <= sets[a]:
            print(f"  {a:9} и {b:9} — общие классы: {', '.join(sorted(inter))}")
            shown += 1
    if not shown:
        print("  таких пар нет")

    print("\nчастота классов в правилах (чем чаще, тем меньше информации несёт):")
    freq = Counter()
    for req in sets.values():
        freq.update(req)
    for cls, n in freq.most_common():
        tag = "specific" if cls in specific else "generic"
        print(f"  {cls:20} в {n} этапах   [{tag}]")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    rules_all, specific = load_rules(RULES)
    rules = checkable(rules_all)
    print(f"правил всего {len(rules_all)}, проверяемых по технике {len(rules)}")
    part1(rules, specific)
    part2(rules, specific)
    part3(rules, specific)


if __name__ == "__main__":
    main()
