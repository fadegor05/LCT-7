"""Наблюдаемость целевых величин на выданных данных.

Отвечает на три вопроса, от которых зависит, что система вообще вправе
утверждать:

1. Сколько кадров имеют ключ ``(площадка, дата)`` — единицу, на которой
   строится всё сопоставление с графиком.
2. Какого размера объекты на кадре — нужен ли tiling (открытый пункт G1-02).
3. Насколько человек вообще способен судить об активности техники по одному
   кадру — верхняя граница для D-007.

Запуск::

    python tools/eda_observability.py
"""

from __future__ import annotations

import collections
import csv
import datetime as dt
import glob
import json
import math
import os
import statistics as st

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITES = os.path.join(ROOT, "data", "reference", "sites.csv")
LABELS = os.path.join(ROOT, "data", "reference", "labels")
STAMPS = os.path.join(ROOT, "data", "reference", "date_stamps_groundtruth.csv")


def read_sites() -> list[dict]:
    with open(SITES, encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh, delimiter=";"))


def read_boxes() -> list[dict]:
    """Рамки из X-AnyLabeling. Активность лежит в ``description``."""
    boxes = []
    for path in glob.glob(os.path.join(LABELS, "*", "*.json")):
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        image = os.path.basename(path)[:-5]
        site = os.path.basename(os.path.dirname(path))
        for shape in doc["shapes"]:
            desc = (shape.get("description") or "").strip()
            parts = dict(
                p.split("=", 1) for p in desc.split(";") if "=" in p
            )
            xs = [p[0] for p in shape["points"]]
            ys = [p[1] for p in shape["points"]]
            w, h = max(xs) - min(xs), max(ys) - min(ys)
            boxes.append(
                {
                    "image": image,
                    "site": site,
                    "label": shape["label"],
                    "activity": parts.get("activity", "MISSING").strip(),
                    "offsite": parts.get("offsite", "").strip() == "true",
                    "side": math.sqrt(w * h),
                }
            )
    return boxes


def section_key(sites: list[dict]) -> None:
    print("\n=== 1. Ключ (площадка, дата) ===")
    with open(STAMPS, encoding="utf-8-sig") as fh:
        stamped = {
            r["image"].replace(".png", "")
            for r in csv.DictReader(fh, delimiter=";")
            if (r.get("expected_date") or "").strip()
        }
    has_site = {r["image"].replace(".png", "") for r in sites if r["site_id"]}
    has_date = {r["image"].replace(".png", "") for r in sites if r["date"]}
    total = len(sites)
    both = has_site & has_date
    print(f"всего кадров           {total}")
    print(f"дата видна на кадре    {len(stamped)}")
    print(f"проставлена площадка   {len(has_site)}")
    print(f"проставлена дата       {len(has_date)}")
    print(f"ЕСТЬ ОБА              {len(both)}  <- только они участвуют в сопоставлении")
    print(f"нет ничего             {total - len(has_site | has_date)}")

    by_site: dict[str, list[str]] = collections.defaultdict(list)
    for row in sites:
        if row["site_id"] and row["date"]:
            by_site[row["site_id"]].append(row["date"])

    print("\nплощадка  кадров  дат  диапазон                       интервалы, дн.")
    multi = 0
    for site in sorted(by_site):
        dates = sorted(set(by_site[site]))
        days = [dt.date.fromisoformat(d) for d in dates]
        gaps = [(days[i + 1] - days[i]).days for i in range(len(days) - 1)]
        span = (days[-1] - days[0]).days
        if len(dates) > 1:
            multi += 1
        print(
            f"{site:9}{len(by_site[site]):>7}{len(dates):>5}  "
            f"{dates[0]}..{dates[-1]} ({span:>4} д)  {gaps}"
        )
    print(f"\nплощадок с более чем одной датой: {multi}  <- вся временная логика стоит на них")


def section_sizes(boxes: list[dict]) -> None:
    print("\n=== 2. Размер объектов (открытый пункт G1-02: нужен ли tiling) ===")
    by_label: dict[str, list[float]] = collections.defaultdict(list)
    for box in boxes:
        by_label[box["label"]].append(box["side"])
    print(f"{'класс':22}{'n':>4}{'медиана':>9}{'min':>7}{'max':>7}{'<32px':>8}{'<64px':>8}")
    for label in sorted(by_label, key=lambda k: -len(by_label[k])):
        sides = sorted(by_label[label])
        lt32 = sum(1 for s in sides if s < 32) / len(sides)
        lt64 = sum(1 for s in sides if s < 64) / len(sides)
        print(
            f"{label:22}{len(sides):>4}{st.median(sides):>9.0f}"
            f"{sides[0]:>7.0f}{sides[-1]:>7.0f}{lt32:>7.0%}{lt64:>7.0%}"
        )
    sides = sorted(b["side"] for b in boxes)
    print(
        f"\nвсего {len(sides)} рамок, медиана {st.median(sides):.0f} px, "
        f"<32px {sum(1 for s in sides if s < 32) / len(sides):.0%}, "
        f"<64px {sum(1 for s in sides if s < 64) / len(sides):.0%}"
    )


def section_activity(boxes: list[dict], sites: list[dict]) -> None:
    print("\n=== 3. Активность: что человек смог решить по одному кадру (D-007) ===")
    counts = collections.Counter(b["activity"] for b in boxes)
    judged = counts["working"] + counts["idle"]
    print(
        f"размечено {len(boxes)} рамок: working {counts['working']}, "
        f"idle {counts['idle']}, unknown {counts['unknown']}, "
        f"без атрибута {counts['MISSING']}"
    )
    print(f"доля объектов, по которым человек вынес суждение: {judged / len(boxes):.0%}")

    print(f"\n{'класс':22}{'working':>8}{'idle':>6}{'unknown':>9}{'нет':>5}")
    per_label: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for box in boxes:
        per_label[box["label"]][box["activity"]] += 1
    for label in sorted(per_label, key=lambda k: -sum(per_label[k].values())):
        c = per_label[label]
        print(
            f"{label:22}{c['working']:>8}{c['idle']:>6}"
            f"{c['unknown']:>9}{c['MISSING']:>5}"
        )

    date_of = {
        r["image"].replace(".png", ""): r["date"] for r in sites
    }
    print("\nраспределение суждений по группам (проверка на утечку площадки):")
    per_group: dict[tuple, collections.Counter] = collections.defaultdict(collections.Counter)
    for box in boxes:
        per_group[(box["site"], date_of.get(box["image"], "?"))][box["activity"]] += 1
    for key in sorted(per_group):
        c = per_group[key]
        print(
            f"  {key[0]} {key[1]}  working={c['working']:>2} "
            f"idle={c['idle']:>2} unknown={c['unknown']:>2}"
        )
    top = max(per_group.items(), key=lambda kv: kv[1]["working"] + kv[1]["idle"])
    share = (top[1]["working"] + top[1]["idle"]) / judged
    print(
        f"\nодна группа {top[0][0]} {top[0][1]} даёт {share:.0%} всех суждений "
        "— обучать и валидировать активность на этом нельзя"
    )


def main() -> None:
    sites = read_sites()
    boxes = read_boxes()
    section_key(sites)
    section_sizes(boxes)
    section_activity(boxes, sites)


if __name__ == "__main__":
    main()
