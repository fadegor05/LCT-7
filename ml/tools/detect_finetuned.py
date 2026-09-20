"""прогон дообученного детектора (YOLO с нашими классами) по папке снимков;
выход в том же формате, что у detect_zeroshot.py, чтобы дальше работала та же цепочка
(site_state, match_schedule, eval_groups); классы модели уже наши, поэтому маппинг тождественный
"""

from detect_zeroshot import collect_images, detect_one

import argparse, json
from collections import Counter
from pathlib import Path
import torch
from ultralytics import YOLO
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--weights", type=str, default="weights/yolo26s_k_apoce_best.pt", help="какие веса")
    parser.add_argument("--conf", type=float, default=0.05, help="нижний порог уверенности")
    parser.add_argument("--iou", type=float, default=0.7, help="порог подавления дублей")
    parser.add_argument("--out", type=Path, default=Path("data/processed/detections_finetuned.json"), help="куда писать результат")
    parser.add_argument("--imgsz", type=int, default=960, help="на 960 модель обучалась")
    parser.add_argument("--limit", type=int, default=None, help="взять первые N кадров — для быстрых проб")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])

    args = parser.parse_args()

    if args.device == "auto":
        if torch.cuda.is_available():
            args.device = "cuda"
        else:
            args.device = "cpu"

    print(f"device: {args.device}")

    model = YOLO(args.weights)
    mapping = {name: name for name in model.names.values()}
    print(f"классов в модели: {len(mapping)}")

    images = collect_images(args.source)[:args.limit]

    if len(images) == 0:
        print("Загружено 0 фото")
        return 1
    else:
        print(f"Загружено фото: {len(images)}")

    params = {
        "imgsz": args.imgsz,
        "conf": args.conf,
        "iou": args.iou,
        "device": args.device,
        "verbose": False
    }

    records = []
    class_counter = Counter()
    times = []
    empty_frames = 0

    for i, path in enumerate(images, start=1):
        record = detect_one(model, path, params, mapping)
        records.append(record)

        if len(record["detections"]) == 0:
            empty_frames += 1
        else:
            for d in record["detections"]:
                class_counter[d["class_ours"]] += 1

        times.append(record["speed_ms"]["inference"])

        if i % 10 == 0:
            print(f"{i}/{len(images)}")

    payload = {
        "meta": {
            "model": Path(args.weights).name,
            "params": params,
            "created": datetime.now().isoformat(timespec="seconds"),
            "images": len(records),
        },
        "images": records,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("--" * 40)
    print(f"кадров: {len(records)}, из них пустых: {empty_frames}")
    print(f"детекций всего: {sum(class_counter.values())}")
    print("")
    for cls_name, count in class_counter.most_common():
        print(f"{count:4d}  {cls_name}")
    print("")
    mean = sum(times[1:]) / max(len(times) - 1, 1)
    print(f"среднее время инференса: {mean:.1f} мс (без первого кадра)")
    print(f"результат: {args.out}")

    return 0


if __name__ == "__main__":
    main()
