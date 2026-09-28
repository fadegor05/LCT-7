"""оценка модели на внешнем наборе в формате YOLO — теми же группами классов.

Зачем отдельно от `eval_groups.py`: на нашей оценочной выборке (p03, p08) по
некоторым классам слишком мало рамок, чтобы цифра что-то значила. По самосвалам
их было две. Признать «не измерено» честно, но недостаточно: если у класса есть
внешний набор с сотнями рамок, число можно получить.

Считается тем же кодом, что и основная метрика: рамки сводятся в группы
`eval_groups.GROUP`, AP при IoU 0.5, точность и полнота при conf 0.25. Разница
только в источнике эталона — не наша разметка, а метки набора.

**Как читать результат.** Это качество **в домене того набора**, а не на
московских фотоотчётах. Для MOCS домен близкий (общие планы строек с земли), но
не тот же, и класс `truck` там объединяет самосвалы с прочими грузовиками. Цифра
отвечает на вопрос «умеет ли модель этот класс вообще», а не «какова точность на
объекте заказчика».

Сплит должен быть **отложенным**: MOCS мы обучали на `train`, поэтому мерим на
`val`.

    python tools/mocs_to_ours.py --src data/external/mocs --out data/interim/mocs_val --splits val
    python tools/eval_external.py data/interim/mocs_val/val --weights weights/mocs_m_best.pt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML / "tools"))

import eval_groups as E          # noqa: E402
from mocs_to_ours import read_names  # noqa: E402


def load_gt(root: Path, classes: list[str]) -> dict[str, list]:
    """Метки YOLO (класс, центр, размер в долях) → наш формат (группа, углы)."""
    gt = {}
    for img in sorted((root / "images").glob("*")):
        boxes = []
        lbl = root / "labels" / (img.stem + ".txt")
        if lbl.exists():
            for line in lbl.read_text().splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                name = classes[int(parts[0])]
                x, y, w, h = map(float, parts[1:5])
                boxes.append((E.G.get(name, "?" + name),
                              [x - w / 2, y - h / 2, x + w / 2, y + h / 2]))
        gt[img.name] = boxes
    return gt


def predict(weights: str, root: Path, gt: dict[str, list], imgsz: int) -> dict[str, list]:
    from ultralytics import YOLO

    model = YOLO(weights)
    out = {}
    for name in gt:
        # conf 0.01: кривая AP строится по всем срабатываниям, порог 0.25
        # применяется уже внутри evaluate — там, где считаются P и R
        r = model.predict(str(root / "images" / name), imgsz=imgsz, conf=0.01, verbose=False)[0]
        out[name] = [(E.G[model.names[int(c)]], b.tolist(), float(p))
                     for c, b, p in zip(r.boxes.cls, r.boxes.xyxyn, r.boxes.conf)]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root", type=Path, help="папка сплита с images/ и labels/")
    ap.add_argument("--weights", default="weights/mocs_m_best.pt")
    ap.add_argument("--names", type=Path,
                    default=ML / "data/external/lct7-kaggle-thin/data.yaml",
                    help="data.yaml, задающий порядок наших классов")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--out", type=Path, default=ML / "data/processed/eval_external.json")
    args = ap.parse_args()

    classes = read_names(args.names)
    gt = load_gt(args.root, classes)
    dets = predict(args.weights, args.root, gt, args.imgsz)
    res = E.evaluate(dets, gt)
    E.report(f"{args.root} ({len(gt)} кадров), веса {Path(args.weights).stem}", res)

    args.out.write_text(json.dumps({
        "set": str(args.root), "weights": args.weights, "frames": len(gt),
        "map50": round(res["map50"], 4),
        "groups": {g: {k: (round(v, 4) if isinstance(v, float) else v)
                       for k, v in d.items()} for g, d in res["groups"].items()},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nзаписано: {args.out}")


if __name__ == "__main__":
    main()
