"""прогон детектора по кадрам уличных камер с привязкой ко времени съёмки.

Отдельно от `tools/detect_finetuned.py`, потому что у кадров с камер есть две
вещи, которых нет у фотоотчётов: **идентификатор камеры** и **время съёмки**.
Без них ряд кадров остаётся просто папкой картинок, а вся ценность архива
именно в порядке и интервалах.

Время берётся не из файловой системы и не из имени файла — там лежит момент
выгрузки, — а из `data/processed/camera_stamps.csv`, куда его записал
`tools/read_camera_stamps.py`, прочитав штамп прямо с кадра. Кадры, для которых
время прочитать не удалось, **в прогон не попадают**: детекции без времени в
ряду бесполезны и только создали бы видимость данных.

Формат выхода — контракт §1 (`docs/CONTRACTS.md`) плюс поля `camera_id` и
`timestamp`, которых ждёт `tools/activity_series.py`.

    python tools/detect_cameras.py --weights weights/mocs_m_best.pt
    python tools/detect_cameras.py --cameras cam01 --limit 50
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

ML = Path(__file__).resolve().parents[1]


def imread(path: Path):
    """cv2.imread не открывает пути с кириллицей — читаем через буфер."""
    import cv2
    data = np.fromfile(str(path), dtype=np.uint8)
    return cv2.imdecode(data, cv2.IMREAD_COLOR) if data.size else None


def load_stamps(path: Path, cameras: set[str] | None) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    if cameras:
        rows = [r for r in rows if r["camera"] in cameras]
    return sorted(rows, key=lambda r: (r["camera"], r["timestamp"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stamps", type=Path, default=ML / "data/processed/camera_stamps.csv")
    ap.add_argument("--root", type=Path, default=ML / "data/raw/cameras")
    ap.add_argument("--weights", default=str(ML / "weights/mocs_m_best.pt"))
    ap.add_argument("--conf", type=float, default=0.05,
                    help="низкий порог: отсекаем позже, чтобы можно было менять его без прогона")
    ap.add_argument("--iou", type=float, default=0.7)
    ap.add_argument("--imgsz", type=int, default=960, help="на этом размере модель обучалась")
    ap.add_argument("--cameras", nargs="*", help="только эти камеры")
    ap.add_argument("--limit", type=int, default=0, help="сколько кадров на камеру (0 — все)")
    ap.add_argument("-o", "--out", type=Path,
                    default=ML / "data/processed/detections_cameras.json")
    args = ap.parse_args()

    import torch
    from ultralytics import YOLO

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = YOLO(args.weights)
    names = model.names

    rows = load_stamps(args.stamps, set(args.cameras) if args.cameras else None)
    if args.limit:
        keep, seen = [], Counter()
        for r in rows:
            if seen[r["camera"]] < args.limit:
                keep.append(r)
                seen[r["camera"]] += 1
        rows = keep
    print(f"кадров со временем: {len(rows)} | устройство: {device} | веса: {Path(args.weights).name}")

    images, per_class, missing = [], Counter(), 0
    for i, row in enumerate(rows, 1):
        path = args.root / row["camera"] / row["file"]
        frame = imread(path)
        if frame is None:
            missing += 1
            continue
        result = model.predict(frame, imgsz=args.imgsz, conf=args.conf, iou=args.iou,
                               device=device, verbose=False)[0]
        detections = []
        for cls, box, conf in zip(result.boxes.cls, result.boxes.xyxyn, result.boxes.conf):
            name = names[int(cls)]
            per_class[name] += 1
            detections.append({"class_raw": name, "class_ours": name,
                               "conf": round(float(conf), 4),
                               "bbox": [round(float(v), 5) for v in box.tolist()]})
        images.append({"image": row["file"], "camera_id": row["camera"],
                       "timestamp": row["timestamp"], "date": row["date"],
                       "width": frame.shape[1], "height": frame.shape[0],
                       "detections": detections})
        if i % 100 == 0:
            print(f"  {i} из {len(rows)}", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({
        "meta": {"weights": Path(args.weights).name, "imgsz": args.imgsz,
                 "conf": args.conf, "iou": args.iou, "device": device,
                 "frames": len(images), "source": "уличные камеры",
                 "built": datetime.now().isoformat(timespec="seconds")},
        "images": images,
    }, ensure_ascii=False), encoding="utf-8")

    print(f"\nкадров обработано: {len(images)}" + (f", пропущено: {missing}" if missing else ""))
    print("детекций по классам:", ", ".join(f"{c} {n}" for c, n in per_class.most_common(12)))
    print(f"результат: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
