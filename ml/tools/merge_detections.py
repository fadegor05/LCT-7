"""слияние детекций двух моделей в один файл того же формата;
каждая модель сильна в своих классах (E8: YOLOE — буровые и краны, дообученная — экскаваторы,
миксеры, погрузчики), поэтому берём рамки от обеих, а спор за один объект решаем нормированной
уверенностью: conf, делённый на порог своего источника
"""

import argparse, json
from collections import Counter
from datetime import datetime
from pathlib import Path
from site_state import _iou, DEDUP_CONTAIN

from site_state import _iou

def load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_source(name: str, cfg: dict) -> dict[str, dict]:
    """Файл детекций -> {имя кадра: запись кадра}."""
    payload = json.loads(Path(cfg["file"]).read_text(encoding="utf-8"))
    by_image = {rec["image"]: rec for rec in payload["images"]}
    print(f"{name}: {len(by_image)} кадров, модель {payload['meta'].get('model')}")
    return by_image


def collect(sources: dict[str, dict[str, dict]], config: dict, image: str) -> list[dict]:
    """Все рамки одного кадра из всех источников, с нормированной силой."""
    boxes = []
    for name, by_image in sources.items():
        record = by_image.get(image)
        if record is None:
            continue
        conf_min = config["sources"][name]["conf"]
        for det in record["detections"]:
            # НАПИШИ СВОЙ КОД ЗДЕСЬ (1): пропустить рамку, если её conf ниже conf_min
            # одна строка: if ...: continue
            if det["conf"] < conf_min:
                continue

            # НАПИШИ СВОЙ КОД ЗДЕСЬ (2): нормированная сила рамки.
            # сырые conf двух моделей несравнимы (разные шкалы), поэтому меряем
            # запас над порогом своего источника: 1.0 — ровно на пороге, 2.0 — вдвое выше
            strength = det["conf"] / conf_min

            boxes.append({**det, "source": name, "strength": round(strength, 3)})
    boxes.sort(key=lambda b: -b["strength"])
    return boxes


def resolve(boxes: list[dict], conflict_iou: float) -> list[dict]:
    """Сильные рамки идут первыми; каждая следующая выбывает, если спорит за тот же объект.

    Спор — это заметное перекрытие с уже принятой рамкой ДРУГОГО класса: две модели
    назвали одну машину по-разному, и правым считаем того, кто увереннее относительно
    своего порога. Рамки одного класса не трогаем: их схлопнет dedup в site_state.py,
    там для этого есть отдельное правило с вложенностью.
    """
    kept: list[dict] = []
    for box in boxes:
        conflict = False
        for other in kept:
            if box["class_ours"] == other["class_ours"]:
                continue
            iou, contained = _iou(box["bbox"], other["bbox"])
            # НАПИШИ СВОЙ КОД ЗДЕСЬ (3): если рамки спорят за один объект — conflict = True и break
            # порог сравнения — conflict_iou; подумай, нужна ли здесь и contained
            # (вложенная рамка даёт низкий iou, но это всё равно тот же объект)
            if iou > conflict_iou or contained > DEDUP_CONTAIN:
                conflict = True
                break
        if not conflict:
            kept.append(box)
    return kept


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/merge.json"))
    parser.add_argument("--out", type=Path, default=Path("data/processed/detections_merged.json"))
    parser.add_argument("--keep-fields", action="store_true",
                        help="оставить служебные поля source и strength в детекциях")
    args = parser.parse_args()

    config = load_config(args.config)
    sources = {name: load_source(name, cfg) for name, cfg in config["sources"].items()}

    images = sorted(set().union(*(set(s) for s in sources.values())))
    common = set.intersection(*(set(s) for s in sources.values()))
    print(f"кадров всего: {len(images)}, общих для всех источников: {len(common)}")

    records = []
    class_counter = Counter()
    source_counter = Counter()
    dropped = 0

    for image in images:
        boxes = collect(sources, config, image)
        kept = resolve(boxes, config["conflict_iou"])
        dropped += len(boxes) - len(kept)

        # размеры кадра берём из любого источника, где кадр есть: они об одном файле
        size = next(s[image] for s in sources.values() if image in s)

        detections = []
        for box in kept:
            det = dict(box)
            if not args.keep_fields:
                det.pop("strength", None)
            detections.append(det)
            class_counter[box["class_ours"]] += 1
            source_counter[box["source"]] += 1

        records.append({
            "image": image,
            "width": size["width"],
            "height": size["height"],
            "speed_ms": size["speed_ms"],
            "detections": detections,
        })

    payload = {
        "meta": {
            "model": "merge:" + "+".join(sources),
            "params": {"sources": config["sources"], "conflict_iou": config["conflict_iou"]},
            "created": datetime.now().isoformat(timespec="seconds"),
            "images": len(records),
        },
        "images": records,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print("--" * 40)
    print(f"детекций после слияния: {sum(class_counter.values())}, снято по конфликту: {dropped}")
    print("по источникам:", dict(source_counter))
    print("")
    for cls_name, count in class_counter.most_common():
        print(f"{count:4d}  {cls_name}")
    print(f"результат: {args.out}")

    return 0


if __name__ == "__main__":
    main()
