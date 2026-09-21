"""вырезы техники для второго этапа: классификатора «кран / буровая / копёр».

Зачем: главная ошибка детектора — путаница крана с буровой, 15 случаев в обе
стороны (замер на p03/p08). У крана и буровой одинаковая гусеничная база и
высокая вертикаль; различие — в её устройстве, и оно видно на вырезе лучше, чем
на всём кадре, где машина занимает 5% площади.

Детектор при этом остаётся прежним: он ищет объект, а класс внутри группы
уточняет отдельная модель. Задача классификатора проще — не искать, а различить.

Источники вырезов: наша разметка (точные классы) и MOCS (там кран и буровая
размечены отдельными классами, вырезов тысячи).
"""

import argparse, json, glob, random
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ML = Path(__file__).resolve().parents[1]
IMG = ML / "data/raw/dataset/images/Строительная_техника"

# что различаем на втором этапе; всё остальное вырезать незачем
TARGET = {
    "drilling_rig": "drilling_rig",
    "drilling_unknown": "drilling_rig",
    "drilling_like": "drilling_rig",
    "dwall_rig": "drilling_rig",
    "pile_driver": "pile_driver",
    "crawler_crane": "crane",
    "truck_crane": "crane",
    "tower_crane": "tower_crane",
    "crane_unknown": "crane",
}
PAD = 0.12          # поля вокруг рамки: контекст помогает отличить мачту от стрелы


def imread(path: Path):
    return cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)


def imwrite(path: Path, im) -> None:
    ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if ok:
        buf.tofile(str(path))


def crop(im, box_norm, size: int):
    h, w = im.shape[:2]
    x1, y1, x2, y2 = box_norm
    bw, bh = (x2 - x1) * w, (y2 - y1) * h
    x1 = max(0, int(x1 * w - bw * PAD)); x2 = min(w, int(x2 * w + bw * PAD))
    y1 = max(0, int(y1 * h - bh * PAD)); y2 = min(h, int(y2 * h + bh * PAD))
    if x2 - x1 < 16 or y2 - y1 < 16:
        return None
    c = im[y1:y2, x1:x2]
    # вписываем в квадрат, не растягивая: пропорции мачты важны
    s = size / max(c.shape[:2])
    c = cv2.resize(c, (max(1, int(c.shape[1] * s)), max(1, int(c.shape[0] * s))))
    canvas = np.zeros((size, size, 3), np.uint8)
    y0, x0 = (size - c.shape[0]) // 2, (size - c.shape[1]) // 2
    canvas[y0:y0 + c.shape[0], x0:x0 + c.shape[1]] = c
    return canvas


def from_labelme(out: Path, size: int, val_sites: set[str]) -> Counter:
    stat = Counter()
    for f in sorted(glob.glob(str(ML / "data/reference/labels/*/*.json"))):
        site = Path(f).parent.name
        split = "val" if site in val_sites else "train"
        d = json.loads(Path(f).read_text(encoding="utf-8"))
        im = None
        W, H = d["imageWidth"], d["imageHeight"]
        for i, s in enumerate(d["shapes"]):
            cls = TARGET.get(s["label"])
            if not cls:
                continue
            if im is None:
                im = imread(IMG / d["imagePath"])
                if im is None:
                    break
            xs = [p[0] for p in s["points"]]; ys = [p[1] for p in s["points"]]
            c = crop(im, [min(xs) / W, min(ys) / H, max(xs) / W, max(ys) / H], size)
            if c is None:
                stat["слишком мелкие"] += 1
                continue
            dst = out / split / cls
            dst.mkdir(parents=True, exist_ok=True)
            imwrite(dst / f"ours_{site}_{Path(f).stem}_{i}.jpg", c)
            stat[f"{split}/{cls}"] += 1
    return stat


def from_mocs(out: Path, size: int, limit: int, seed: int) -> Counter:
    """MOCS: static_crane -> tower_crane, crane -> crane, pile_driver -> drilling_rig.

    Копёр MOCS отображается в `drilling_rig` осознанно: там оба типа машин лежат
    в одном классе (проверено вырезами, E14), и для второго этапа это
    «машина с мачтой» против «кран».
    """
    names = ["worker", "static_crane", "hanging_head", "crane", "roller", "bulldozer",
             "excavator", "truck", "loader", "pump_truck", "concrete_mixer",
             "pile_driver", "other_vehicle"]
    keep = {"static_crane": "tower_crane", "crane": "crane", "pile_driver": "drilling_rig"}
    src = ML / "data/external/mocs"
    stat = Counter()
    files = sorted((src / "labels/train").glob("*.txt"))
    random.Random(seed).shuffle(files)
    for lbl in files:
        if all(stat[f"train/{c}"] >= limit for c in set(keep.values())):
            break
        rows = [r.split() for r in lbl.read_text(encoding="utf-8").splitlines() if r.strip()]
        want = [(keep[names[int(r[0])]], r) for r in rows
                if len(r) >= 5 and names[int(r[0])] in keep]
        want = [(c, r) for c, r in want if stat[f"train/{c}"] < limit]
        if not want:
            continue
        im = imread(src / "images/train" / (lbl.stem + ".jpg"))
        if im is None:
            continue
        for cls, r in want:
            x, y, bw, bh = map(float, r[1:5])
            c = crop(im, [x - bw / 2, y - bh / 2, x + bw / 2, y + bh / 2], size)
            if c is None:
                continue
            dst = out / "train" / cls
            dst.mkdir(parents=True, exist_ok=True)
            imwrite(dst / f"mocs_{lbl.stem}_{r[1][:6]}.jpg", c)
            stat[f"train/{cls}"] += 1
    return stat


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=ML / "data/interim/crops")
    ap.add_argument("--size", type=int, default=224)
    ap.add_argument("--mocs-limit", type=int, default=1200, help="вырезов на класс из MOCS")
    ap.add_argument("--val-sites", nargs="+", default=["p03", "p08"],
                    help="площадки оценки: те же, что у детектора, чтобы не было утечки")
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    ours = from_labelme(args.out, args.size, set(args.val_sites))
    print("из нашей разметки:")
    for k, v in sorted(ours.items()):
        print(f"  {k:<26}{v}")
    mocs = from_mocs(args.out, args.size, args.mocs_limit, args.seed)
    print("из MOCS:")
    for k, v in sorted(mocs.items()):
        print(f"  {k:<26}{v}")
    print(f"\nвырезы: {args.out}")
    return 0


if __name__ == "__main__":
    main()
