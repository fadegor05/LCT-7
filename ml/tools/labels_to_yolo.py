"""разметка LabelMe -> формат YOLO для дообучения (D-014).

Классы берутся из data.yaml обучающего набора Захара: у его весов голова на 25
классов, и если порядок совпадает, дообучение идёт поверх без замены головы.

Кадр без рамок остаётся в наборе с пустым .txt — это отрицательный пример, он
учит модель не выдумывать технику на пустой площадке.
"""

import argparse, json, shutil, sys
from collections import Counter
from pathlib import Path

ML = Path(__file__).resolve().parents[1]

# наши классы, которых нет в голове модели, сводим к ближайшему грубому
ALIASES = {
    "drilling_like": "drilling_unknown",
    "crane_like": "crane_unknown",
    "excavator_like": "excavator_unknown",
    "truck_like": "truck_unknown",
    "loader_like": "loader_unknown",
}


def read_names(yaml_path: Path) -> list[str]:
    names, on = {}, False
    for line in yaml_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("names:"):
            on = True
        elif on and ":" in line:
            i, n = line.strip().split(":", 1)
            names[int(i)] = n.strip()
    return [names[i] for i in sorted(names)]


def parse_attrs(description: str | None) -> dict[str, str]:
    out = {}
    for part in (description or "").split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def convert(label_path: Path, names: dict[str, int], keep_offsite: bool) -> tuple[list[str], Counter, Counter]:
    d = json.loads(label_path.read_text(encoding="utf-8"))
    W, H = d["imageWidth"], d["imageHeight"]
    lines, used, skipped = [], Counter(), Counter()
    for shape in d["shapes"]:
        label = ALIASES.get(shape["label"], shape["label"])
        if label not in names:
            skipped[f"класс {shape['label']}"] += 1
            continue
        if not keep_offsite and parse_attrs(shape.get("description")).get("offsite") == "true":
            skipped["offsite"] += 1
            continue
        xs = [p[0] for p in shape["points"]]
        ys = [p[1] for p in shape["points"]]
        x1, y1 = max(0.0, min(xs)), max(0.0, min(ys))
        x2, y2 = min(float(W), max(xs)), min(float(H), max(ys))
        if x2 - x1 < 2 or y2 - y1 < 2:
            skipped["вырожденная рамка"] += 1
            continue
        cx, cy = (x1 + x2) / 2 / W, (y1 + y2) / 2 / H
        bw, bh = (x2 - x1) / W, (y2 - y1) / H
        lines.append(f"{names[label]} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}")
        used[label] += 1
    return lines, used, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--labels", type=Path, default=ML / "data/reference/labels")
    ap.add_argument("--images", type=Path, default=ML / "data/raw/dataset/images/Строительная_техника")
    ap.add_argument("--names", type=Path, default=ML / "data/external/lct7-kaggle-thin/data.yaml",
                    help="откуда брать порядок классов (голова модели Захара)")
    ap.add_argument("--out", type=Path, default=ML / "data/interim/ours_yolo")
    ap.add_argument("--train-sites", nargs="+", default=["p05", "p07", "p09", "p11"])
    ap.add_argument("--val-sites", nargs="+", default=["p03", "p08"])
    ap.add_argument("--keep-offsite", action="store_true",
                    help="брать в обучение и технику соседних площадок (по умолчанию — да, см. LABELING_SPEC 7b)")
    args = ap.parse_args()

    names_list = read_names(args.names)
    names = {n: i for i, n in enumerate(names_list)}

    total, per_split = Counter(), Counter()
    for split, sites in (("train", args.train_sites), ("val", args.val_sites)):
        img_dir = args.out / split / "images"
        lbl_dir = args.out / split / "labels"
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        for site in sites:
            for label_path in sorted((args.labels / site).glob("*.json")):
                stem = json.loads(label_path.read_text(encoding="utf-8"))["imagePath"]
                src = args.images / stem
                if not src.exists():
                    print(f"нет кадра {src}", file=sys.stderr)
                    continue
                lines, used, skipped = convert(label_path, names, args.keep_offsite)
                shutil.copy(src, img_dir / src.name)
                (lbl_dir / (src.stem + ".txt")).write_text("\n".join(lines), encoding="utf-8")
                total.update(used)
                per_split[split] += len(lines)
                per_split[split + " кадров"] += 1
                for k, v in skipped.items():
                    per_split["пропущено: " + k] += v

    yaml_path = args.out / "data.yaml"
    yaml_path.write_text(
        f"path: {args.out.resolve().as_posix()}\ntrain: train/images\nval: val/images\nnames:\n"
        + "\n".join(f"  {i}: {n}" for i, n in enumerate(names_list)) + "\n", encoding="utf-8")

    print(f"площадки в обучении: {', '.join(args.train_sites)}; в проверке: {', '.join(args.val_sites)}")
    for k, v in sorted(per_split.items()):
        print(f"  {k}: {v}")
    print("\nрамок по классам:")
    for cls, n in total.most_common():
        print(f"  {n:4d}  {cls}")
    print(f"\nконфиг: {yaml_path}")
    return 0


if __name__ == "__main__":
    main()
