# -*- coding: utf-8 -*-
"""Ручная разметка → формат детекций, чтобы прогнать цепочку на эталоне.

Это B0-oracle: те же site_state.py и match_schedule.py, но на входе не
предсказания модели, а размеченные человеком рамки. Сравнение двух отчётов
показывает цену ошибок восприятия в терминах бизнес-вывода — сколько статусов
этапов меняется, — а не в mAP.

Техника с `offsite=true` (краны соседних строек) в подсчёт не идёт: для обучения
детектора такие рамки нужны, для состояния площадки — нет.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


def parse_attributes(description: str | None) -> dict[str, str]:
    attrs = {}
    for part in (description or "").split(";"):
        key, _, value = part.strip().partition("=")
        if key.strip():
            attrs[key.strip()] = value.strip()
    return attrs


def convert(folder: Path, keep_offsite: bool) -> tuple[list[dict], Counter, int]:
    records, counter, skipped = [], Counter(), 0
    for path in sorted(folder.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        width = data.get("imageWidth")
        height = data.get("imageHeight")
        if not width or not height:
            continue

        detections = []
        for shape in data.get("shapes", []):
            attrs = parse_attributes(shape.get("description"))
            if attrs.get("offsite") == "true" and not keep_offsite:
                skipped += 1
                continue
            xs = [p[0] for p in shape["points"]]
            ys = [p[1] for p in shape["points"]]
            detections.append({
                "class_raw": shape["label"],
                "class_ours": shape["label"],
                "conf": 1.0,
                "bbox": [round(min(xs) / width, 4), round(min(ys) / height, 4),
                         round(max(xs) / width, 4), round(max(ys) / height, 4)],
                "activity": attrs.get("activity", "unknown"),
            })
            counter[shape["label"]] += 1

        records.append({
            "image": data.get("imagePath", f"{path.stem}.png"),
            "width": width,
            "height": height,
            "speed_ms": {"preprocess": 0.0, "inference": 0.0, "postprocess": 0.0},
            "detections": detections,
        })
    return records, counter, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folders", nargs="+", type=Path, help="папки с json разметки")
    parser.add_argument("-o", "--out", type=Path,
                        default=Path("data/processed/detections_oracle.json"))
    parser.add_argument("--keep-offsite", action="store_true",
                        help="не отбрасывать технику соседних строек")
    args = parser.parse_args()

    all_records, total, skipped_total = [], Counter(), 0
    for folder in args.folders:
        records, counter, skipped = convert(folder, args.keep_offsite)
        all_records.extend(records)
        total.update(counter)
        skipped_total += skipped
        print(f"{folder}: кадров {len(records)}, рамок {sum(counter.values())}, "
              f"отброшено offsite {skipped}")

    payload = {
        "meta": {
            "model": "ручная разметка (B0-oracle)",
            "params": {"source": [str(f) for f in args.folders],
                       "keep_offsite": args.keep_offsite},
            "created": datetime.now().isoformat(timespec="seconds"),
            "images": len(all_records),
        },
        "images": all_records,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nвсего кадров: {len(all_records)}, рамок: {sum(total.values())}, "
          f"отброшено offsite: {skipped_total}")
    for label, n in total.most_common():
        print(f"  {n:4d}  {label}")
    print(f"\nрезультат: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
