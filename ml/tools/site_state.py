# -*- coding: utf-8 -*-
"""Состояние площадки на дату: детекции по кадрам → «что было на объекте в этот день».

Правила из configs/rules.json формулируются в терминах площадки, а не кадра:
«устройство свай = буровая установка + гусеничный кран». По одной фотографии это
не проверить — на одном кадре видно буровую, на другом кран, на третьем угол
забора. Поэтому детекции сводятся к паре «площадка + дата».

Здесь же происходит чистка: отсечение по порогу и схлопывание дублей. Дальше
логика сопоставления работает с чистыми числами и остаётся простой.

Ключевое решение — как свести несколько кадров одной даты в одно число на класс.
Взят МАКСИМУМ по кадрам, а не сумма: площадку снимают с нескольких ракурсов, и
один экскаватор попал бы в сумму пять раз. Максимум занижает, когда техника не
помещается в один кадр, зато никогда не завышает — для правил вида «нужен хотя бы
один буровой станок» это безопаснее. Обоснование и альтернативы: DECISIONS.md.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEFAULT_CONF = 0.25
DEDUP_IOU = 0.3          # рамки того же класса с большим перекрытием — один объект
DEDUP_CONTAIN = 0.7      # ... и вложенные: NMS их не давит, IoU у них низкий


def load_sites(path: Path) -> dict[str, tuple[str, str]]:
    """sites.csv → {имя файла: (site_id, date)}; пустые значения сохраняются."""
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return {r["image"]: (r["site_id"].strip(), r["date"].strip())
                for r in csv.DictReader(fh, delimiter=";")}


def load_thresholds(path: Path | None) -> dict[str, float]:
    """Порог уверенности отдельно на класс: у редких классов он ниже.

    Из прогона 1.3: медиана уверенности у excavator_crawler 0.21, а у
    drilling_rig 0.09 — единый порог либо пропускает шум, либо режет редкие
    классы. Файл необязателен; без него действует DEFAULT_CONF.
    """
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _iou(a: list[float], b: list[float]) -> tuple[float, float]:
    """IoU и доля меньшей рамки, попавшая внутрь большей."""
    x1, y1 = max(a[0], b[0]), max(a[1], b[1])
    x2, y2 = min(a[2], b[2]), min(a[3], b[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0, 0.0
    inter = (x2 - x1) * (y2 - y1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    smaller = min(area_a, area_b)
    return (inter / union if union else 0.0), (inter / smaller if smaller else 0.0)


def dedup(detections: list[dict]) -> list[dict]:
    """Схлопывает повторные рамки одного объекта внутри кадра.

    Подавление перекрытий в детекторе оставляет вложенные рамки: у рамки внутри
    рамки IoU низкий по построению (площадь малой, делённая на площадь большой),
    и стандартный порог 0.7 их не трогает. В прогоне 1.3 таких 12%.
    """
    kept: list[dict] = []
    for det in sorted(detections, key=lambda d: -d["conf"]):
        duplicate = False
        for prev in kept:
            if prev["class_ours"] != det["class_ours"]:
                continue
            iou, contained = _iou(prev["bbox"], det["bbox"])
            if iou > DEDUP_IOU or contained > DEDUP_CONTAIN:
                duplicate = True
                break
        if not duplicate:
            kept.append(det)
    return kept


def frame_counts(record: dict, thresholds: dict[str, float], default_conf: float) -> Counter:
    """Классы одного кадра после фильтрации по порогу и схлопывания дублей."""
    filtered = [d for d in record["detections"]
                if d["conf"] >= thresholds.get(d["class_ours"], default_conf)]
    return Counter(d["class_ours"] for d in dedup(filtered))


def build_states(records: list[dict], sites: dict[str, tuple[str, str]],
                 thresholds: dict[str, float], default_conf: float) -> tuple[list[dict], dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    skipped = Counter()

    for record in records:
        site_id, date = sites.get(record["image"], ("", ""))
        if not site_id:
            skipped["без площадки"] += 1
            continue
        if not date:
            skipped["площадка есть, даты нет"] += 1
            continue
        groups[(site_id, date)].append(record)

    states = []
    for (site_id, date), frames in sorted(groups.items()):
        per_frame = [frame_counts(f, thresholds, default_conf) for f in frames]

        # Максимум по кадрам: см. докстринг модуля.
        equipment: Counter = Counter()
        for counts in per_frame:
            for cls, n in counts.items():
                equipment[cls] = max(equipment[cls], n)

        states.append({
            "site_id": site_id,
            "date": date,
            "n_images": len(frames),
            "images": [f["image"] for f in frames],
            "equipment": dict(sorted(equipment.items(), key=lambda kv: -kv[1])),
            "per_frame_totals": [sum(c.values()) for c in per_frame],
            "observability": {
                "n_images": len(frames),
                "empty_frames": sum(1 for c in per_frame if not c),
            },
        })
    return states, dict(skipped)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--detections", type=Path,
                        default=Path("data/processed/detections_1280.json"))
    parser.add_argument("--sites", type=Path, default=Path("data/reference/sites.csv"))
    parser.add_argument("--thresholds", type=Path, default=Path("configs/thresholds.json"),
                        help="порог уверенности на класс; без файла действует --conf")
    parser.add_argument("--conf", type=float, default=DEFAULT_CONF,
                        help="порог по умолчанию для классов без своего значения")
    parser.add_argument("-o", "--out", type=Path,
                        default=Path("data/processed/site_state.json"))
    args = parser.parse_args()

    detections = json.loads(args.detections.read_text(encoding="utf-8"))
    records = detections["images"]
    sites = load_sites(args.sites)
    thresholds = load_thresholds(args.thresholds)

    states, skipped = build_states(records, sites, thresholds, args.conf)
    if not states:
        print("не собрано ни одного состояния: проверьте, что имена кадров в "
              "детекциях и в sites.csv совпадают", file=sys.stderr)
        return 1

    payload = {
        "meta": {
            "detections": str(args.detections),
            "sites": str(args.sites),
            "default_conf": args.conf,
            "thresholds": thresholds,
            "aggregation": "max_over_frames",
            "dedup": {"iou": DEDUP_IOU, "contained": DEDUP_CONTAIN},
            "source_images": len(records),
            "states": len(states),
        },
        "states": states,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    covered = sum(s["n_images"] for s in states)
    print(f"кадров на входе: {len(records)}")
    print(f"вошло в состояния: {covered}")
    for reason, n in skipped.items():
        print(f"  пропущено — {reason}: {n}")
    print(f"\nсостояний (площадка + дата): {len(states)}\n")
    for s in states:
        line = ", ".join(f"{cls} x{n}" for cls, n in s["equipment"].items()) or "техника не найдена"
        print(f"  {s['site_id']}  {s['date']}  ({s['n_images']} кадр.)  {line}")
    print(f"\nрезультат: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
