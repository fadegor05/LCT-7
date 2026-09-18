# -*- coding: utf-8 -*-
"""Детекции → черновик разметки для X-AnyLabeling.

Разметка с нуля — 5–7 часов на сотню кадров, правка готовых рамок — 2–3. Поэтому
детектор выступает как черновик: рамки он ставит точно (прогон 1.5), а классы
путает предсказуемо и правятся оптом.

Формат — LabelMe-совместимый JSON рядом с изображением: X-AnyLabeling открывает
такую папку и сразу показывает рамки. Атрибут активности (D-007: «работает /
простаивает» — обязательная функция по Q&A 11:58) кладётся в поле description
строкой `activity=unknown`; разметчик правит его на working или idle.
"""

from __future__ import annotations

import argparse
import json
import shutil
from collections import Counter
from pathlib import Path

LABELME_VERSION = "5.4.1"


def to_shapes(record: dict, min_conf: float) -> list[dict]:
    width, height = record["width"], record["height"]
    shapes = []
    for det in record["detections"]:
        if det["conf"] < min_conf:
            continue
        x1, y1, x2, y2 = det["bbox"]
        shapes.append({
            "label": det["class_ours"],
            "points": [[round(x1 * width, 1), round(y1 * height, 1)],
                       [round(x2 * width, 1), round(y2 * height, 1)]],
            "group_id": None,
            "description": "activity=unknown",
            "difficult": False,
            "shape_type": "rectangle",
            "flags": {},
            "attributes": {},
        })
    return shapes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("detections", type=Path, help="JSON от detect_zeroshot или detect_visual_prompt")
    parser.add_argument("-o", "--out", type=Path, default=Path("data/interim/label/batch01"),
                        help="папка для разметки: копии кадров + json рядом")
    parser.add_argument("--images", type=Path,
                        default=Path("data/raw/dataset/images/Строительная_техника"))
    parser.add_argument("--min-conf", type=float, default=0.2,
                        help="рамки ниже порога в черновик не попадают: их дешевле нарисовать, чем удалять")
    parser.add_argument("--only", nargs="*", default=None,
                        help="имена кадров; без них берутся все из файла детекций")
    args = parser.parse_args()

    data = json.loads(args.detections.read_text(encoding="utf-8"))
    records = data["images"]
    if args.only:
        wanted = set(args.only)
        records = [r for r in records if r["image"] in wanted]
    if not records:
        print("нет кадров для выгрузки")
        return 1

    args.out.mkdir(parents=True, exist_ok=True)
    counter, empty = Counter(), 0
    for record in records:
        src = args.images / record["image"]
        if not src.exists():
            print(f"пропуск, нет файла: {src}")
            continue
        shutil.copy2(src, args.out / record["image"])

        shapes = to_shapes(record, args.min_conf)
        if not shapes:
            empty += 1
        for s in shapes:
            counter[s["label"]] += 1

        (args.out / f"{Path(record['image']).stem}.json").write_text(
            json.dumps({
                "version": LABELME_VERSION,
                "flags": {},
                "shapes": shapes,
                "imagePath": record["image"],
                "imageData": None,
                "imageHeight": record["height"],
                "imageWidth": record["width"],
            }, ensure_ascii=False, indent=2), encoding="utf-8")

    classes = sorted({s for s in counter})
    (args.out / "classes.txt").write_text("\n".join(classes) + "\n", encoding="utf-8")

    print(f"кадров выгружено: {len(records)}, из них без рамок: {empty}")
    print(f"рамок всего: {sum(counter.values())}")
    for label, n in counter.most_common():
        print(f"  {n:4d}  {label}")
    print(f"\nпапка: {args.out}")
    print("открыть в X-AnyLabeling: File > Open Dir > указать эту папку")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
