"""прогон детектора с открытым словарём по папке снимков; 
нужен как нижняя планка качества и как источник черновой разметки, которую человек правит вместо рисования 
с нуля; текстовые промпты и их соответствие нашим классам вынесены в конфиг, чтобы менять набор без правки кода
"""

import argparse, json
from collections import Counter 
from pathlib import Path
from PIL import Image
import torch
from ultralytics import YOLOE
import re
from datetime import datetime

EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}

def load_prompts(path) -> dict[str, str]:
    with open(path, 'r', encoding='utf-8') as F:
        mapping = json.load(F)

    return mapping

def natural_key(path: Path) -> list:
    """Screenshot_2 перед Screenshot_10: числа сравниваются как числа."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", path.name)]

def collect_images(source: Path) -> list[Path]:
    if source.is_file():
        names = source.read_text(encoding="utf-8").split()
        return [Path(n) for n in names]
    files = [p for p in source.iterdir() if p.suffix.lower() in EXTENSIONS]
    return sorted(files, key=natural_key)

def build_model(weights, prompts, device) -> YOLOE:
    model = YOLOE(weights)
    model.to(device)

    embeddings = model.get_text_pe(prompts)
    model.set_classes(prompts, embeddings)

    return model

def detect_one(model, path, params, mapping) -> dict:
    result = model(path, **params)
    r = result[0]
    detections = []

    for (cls_id, conf, bbox) in zip(r.boxes.cls.tolist(), r.boxes.conf.tolist(), r.boxes.xyxyn.tolist()):
        raw = r.names[int(cls_id)]
        detections.append({
            "class_raw": raw,
            "class_ours": mapping[raw],
            "conf": round(conf, 3),
            "bbox": [round(v, 4) for v in bbox]
        })

    height, width = r.orig_shape
    
    return {
        "image": path.name,
        "width": width,
        "height": height,
        "speed_ms": r.speed,
        "detections": detections
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--out", type=Path, default=Path("data/processed/detections_zeroshot.json"), help="куда писать результат")
    parser.add_argument("--prompts", type=Path, default=Path("configs/prompt.json"), help="набор промптов")
    parser.add_argument("--weights", type=str, default="yoloe-26s-seg.pt", help="какие веса")
    parser.add_argument("--conf", type=float, default=0.05, help="нижний порог уверенности")
    parser.add_argument("--iou", type=float, default=0.7, help="порог подавления дублей")
    parser.add_argument("--limit", type=int, default=None, help="взять первые N кадров — для быстрых проб")

    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--save-viz", action="store_true")

    args = parser.parse_args()

    if args.device == "auto":
        if torch.cuda.is_available():
            args.device = "cuda"
        else:
            args.device = "cpu"

    print(f"device: {args.device}")

    mapping = load_prompts(args.prompts)
    print(f"Загружено промптов: {len(mapping)}")

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

    model = build_model(args.weights, list(mapping.keys()), params["device"])

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
            "model": model.model_name,
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