# -*- coding: utf-8 -*-
"""Детекция по визуальным промптам: образец-рамка вместо слова.

Текстовые промпты не разделяют буровую установку, копёр и гусеничный кран — в
обучении текстового энкодера они описаны похожими словами (прогон 1.3: медиана
уверенности у drilling_rig 0.09, уровень шума). Визуальный промпт сравнивает
внешний вид, и на локализации это работает заметно лучше.

Оговорка из прогона 1.5: сравнивается именно внешность, а не абстрактный класс.
С одним образцом на класс жёлтые буровые уходят в класс жёлтого крана. Поэтому
образцов на класс должно быть несколько и разных — цвет, производитель, ракурс.

Выход — та же схема, что у detect_zeroshot.py (docs/CONTRACTS.md), чтобы оба
детектора были взаимозаменяемы для следующих звеньев пайплайна.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
from ultralytics import YOLOE
from ultralytics.models.yolo.yoloe import YOLOEVPSegPredictor

EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def natural_key(path: Path) -> list:
    """Screenshot_2 перед Screenshot_10: числа сравниваются как числа."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", path.name)]


def collect_images(source: Path, limit: int | None) -> list[Path]:
    if source.is_file() and source.suffix.lower() in EXTENSIONS:
        return [source]
    if source.is_file():                       # текстовый список путей
        names = source.read_text(encoding="utf-8").split()
        return [Path(n) for n in names][:limit]
    files = [p for p in source.iterdir() if p.suffix.lower() in EXTENSIONS]
    return sorted(files, key=natural_key)[:limit]


def load_prompts(path: Path) -> tuple[Path, dict[str, np.ndarray], dict[int, str]]:
    """Конфиг → (кадр-образец, промпты для predict, соответствие индекс→класс)."""
    cfg = json.loads(path.read_text(encoding="utf-8"))
    boxes = np.array([p["bbox"] for p in cfg["prompts"]], dtype=np.float32)
    classes = np.array([p["cls"] for p in cfg["prompts"]], dtype=np.int32)
    names = {int(k): v for k, v in cfg["classes"].items()}

    refer = Path(cfg["refer_image"])
    if not refer.exists():
        raise SystemExit(f"кадр-образец не найден: {refer}")
    return refer, {"bboxes": boxes, "cls": classes}, names


def detect_one(model: YOLOE, path: Path, refer: Path, prompts: dict,
               names: dict[int, str], params: dict, viz_dir: Path | None) -> dict:
    result = model.predict(source=str(path), refer_image=str(refer),
                           visual_prompts=prompts, predictor=YOLOEVPSegPredictor,
                           **params)[0]

    detections = []
    for cls_id, conf, bbox in zip(result.boxes.cls.tolist(),
                                  result.boxes.conf.tolist(),
                                  result.boxes.xyxyn.tolist()):
        cls_name = names.get(int(cls_id), f"class_{int(cls_id)}")
        detections.append({
            "class_raw": cls_name,
            "class_ours": cls_name,
            "conf": round(conf, 3),
            "bbox": [round(v, 4) for v in bbox],
        })

    if viz_dir is not None:
        result.names = dict(names)
        viz_dir.mkdir(parents=True, exist_ok=True)
        result.plot(masks=False, line_width=2, pil=True).save(viz_dir / path.name)

    height, width = result.orig_shape
    return {
        "image": path.name,
        "width": width,
        "height": height,
        "speed_ms": result.speed,
        "detections": detections,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path,
                        help="папка со снимками, один снимок или текстовый список путей")
    parser.add_argument("-o", "--out", type=Path,
                        default=Path("data/processed/detections_visual.json"))
    parser.add_argument("--prompts", type=Path, default=Path("configs/visual_prompts.json"))
    parser.add_argument("--weights", type=str, default="yoloe-26s-seg.pt")
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument("--iou", type=float, default=0.5)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--save-viz", type=Path, default=None,
                        help="папка для кадров с отрисованными рамками")
    args = parser.parse_args()

    device = ("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device
    print(f"устройство: {device}")

    refer, prompts, names = load_prompts(args.prompts)
    counts = ", ".join(f"{n}: {int((prompts['cls'] == i).sum())}" for i, n in names.items())
    print(f"образцов по классам — {counts}")
    print(f"кадр-образец: {refer.name}")

    images = collect_images(args.source, args.limit)
    if not images:
        print("не найдено ни одного изображения", file=sys.stderr)
        return 1
    print(f"кадров: {len(images)}")

    model = YOLOE(args.weights)
    params = {"imgsz": args.imgsz, "conf": args.conf, "iou": args.iou,
              "device": device, "verbose": False}

    records, counter, times = [], Counter(), []
    for i, path in enumerate(images, start=1):
        record = detect_one(model, path, refer, prompts, names, params, args.save_viz)
        records.append(record)
        for det in record["detections"]:
            counter[det["class_ours"]] += 1
        times.append(record["speed_ms"]["inference"])
        if i % 10 == 0:
            print(f"{i}/{len(images)}")

    payload = {
        "meta": {
            "model": args.weights,
            "mode": "visual_prompts",
            "prompts_config": str(args.prompts),
            "refer_image": refer.name,
            "params": params,
            "created": datetime.now().isoformat(timespec="seconds"),
            "images": len(records),
        },
        "images": records,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    empty = sum(1 for r in records if not r["detections"])
    print("-" * 50)
    print(f"кадров: {len(records)}, из них пустых: {empty}")
    print(f"детекций всего: {sum(counter.values())}")
    for cls_name, n in counter.most_common():
        print(f"  {n:4d}  {cls_name}")
    mean = sum(times[1:]) / max(len(times) - 1, 1)
    print(f"среднее время инференса: {mean:.1f} мс (без первого кадра)")
    print(f"результат: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
