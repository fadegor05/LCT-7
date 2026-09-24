"""Roboflow «Construction Dataset» (KlinterAI, CC BY 4.0) -> наша таксономия.

Единственный найденный открытый набор, где **буровые установки выделены явным
классом**, а не слиты с копрами: `piling rig` 238 объектов и `folded piling rig`
17 (машина со сложенной мачтой — таких примеров у нас нет вовсе). Это прямое
попадание в главную ошибку детектора (E12: путаница крана с буровой, 15 случаев).

Проверено глазами перед переносом:
- `piling rig`, `folded piling rig` — роторные буровые, копров среди них нет;
- `load carrying crane` — смесь гусеничных и башенных, поэтому грубый класс;
- `continuous flight auger drill`, `sectional flight auger` — крупный план шнека,
  то есть рамка на детали машины. **Не переносим:** детектор учится находить
  технику, а не её части.

Лицензия CC BY 4.0 — требует указания авторства, ссылка в README набора.
"""

import argparse, os, shutil
from collections import Counter
from pathlib import Path

ML = Path(__file__).resolve().parents[1]

TO_OURS = {
    "piling rig": "drilling_rig",
    "folded piling rig": "drilling_rig",
    "load carrying crane": "crane_unknown",
    "crane": "crane_unknown",
    "excavator": "excavator_unknown",
    "concrete mixer truck": "concrete_mixer",
    "dumper truck": "dump_truck",
    "dump truck": "dump_truck",
}


def read_names(yaml_path: Path) -> list[str]:
    """Имена классов по порядку. В одних data.yaml это список, в других —
    словарь «номер: имя»; перебор словаря дал бы номера вместо имён."""
    import yaml
    names = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))["names"]
    if isinstance(names, dict):
        return [names[k] for k in sorted(names, key=int)]
    return list(names)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=ML / "data/external/rf_construction")
    ap.add_argument("--out", type=Path, default=ML / "data/interim/rf_ours")
    ap.add_argument("--names", type=Path, default=ML / "data/external/lct7-kaggle-thin/data.yaml",
                    help="порядок классов нашей головы")
    args = ap.parse_args()

    ours = {n: i for i, n in enumerate(read_names(args.names))}
    rf = read_names(args.src / "data.yaml")
    mapping = {i: TO_OURS[n] for i, n in enumerate(rf) if n in TO_OURS}
    print("переносим классы:", {rf[i]: v for i, v in mapping.items()})

    stat, skipped, kept = Counter(), Counter(), 0
    for split in ("train", "valid", "test"):
        src_img = args.src / split / "images"
        if not src_img.is_dir():
            continue
        dst = args.out / "train"          # весь набор идёт в обучение: оценка только на наших кадрах
        (dst / "images").mkdir(parents=True, exist_ok=True)
        (dst / "labels").mkdir(parents=True, exist_ok=True)
        for lbl in sorted((args.src / split / "labels").glob("*.txt")):
            lines = []
            for row in lbl.read_text(encoding="utf-8").splitlines():
                parts = row.split()
                if len(parts) < 5:
                    continue
                cls = mapping.get(int(parts[0]))
                if cls is None:
                    skipped[rf[int(parts[0])]] += 1
                    continue
                lines.append(" ".join([str(ours[cls])] + parts[1:5]))
                stat[cls] += 1
            if not lines:
                skipped["кадр без нашей техники"] += 1
                continue
            img = None
            for ext in (".jpg", ".jpeg", ".png"):
                cand = src_img / (lbl.stem + ext)
                if cand.exists():
                    img = cand
                    break
            if img is None:
                continue
            target = dst / "images" / img.name
            if not target.exists():
                try:
                    os.link(img, target)
                except OSError:
                    shutil.copy(img, target)
            (dst / "labels" / (lbl.stem + ".txt")).write_text("\n".join(lines), encoding="utf-8")
            kept += 1

    print(f"\nкадров перенесено: {kept}")
    for k, v in stat.most_common():
        print(f"  {v:>5}  {k}")
    print("пропущено:", dict(skipped.most_common(5)))
    return 0


if __name__ == "__main__":
    main()
