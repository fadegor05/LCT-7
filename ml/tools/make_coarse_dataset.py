"""пересборка всех наборов в укрупнённые классы (группы наблюдаемости).

Зачем: на 580 наших рамках 19 классов дают по 4-6 примеров на редкий класс, и
8 процентных пунктов полноты теряются на путанице внутри группы (E12). Группа
«кран» из 76 примеров различима лучше, чем три кучки по 20.

Классы берутся из GROUP в tools/eval_groups.py — там же, где считается метрика,
чтобы обучение и оценка не разъехались.

Изображения не копируются, а связываются жёсткой ссылкой: 3 500 кадров на диске
лежат один раз.
"""

import argparse, os, shutil, sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from eval_groups import GROUP, G  # noqa: E402

ML = Path(__file__).resolve().parents[1]
GROUPS = sorted(GROUP)                      # порядок классов в новой голове
GID = {g: i for i, g in enumerate(GROUPS)}
EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def link(src: Path, dst: Path) -> None:
    if dst.exists():
        return
    try:
        os.link(src, dst)                   # жёсткая ссылка: без копии на диске
    except OSError:
        shutil.copy(src, dst)


def convert_split(src_images: Path, dst: Path, names: list[str]) -> Counter:
    """Один сплит: ссылки на кадры + переписанные метки с новыми номерами классов."""
    (dst / "images").mkdir(parents=True, exist_ok=True)
    (dst / "labels").mkdir(parents=True, exist_ok=True)
    src_labels = src_images.parent / "labels"
    stat = Counter()
    for img in sorted(p for p in src_images.iterdir() if p.suffix.lower() in EXT):
        lbl = src_labels / (img.stem + ".txt")
        if not lbl.exists():
            stat["без меток"] += 1
            continue
        lines = []
        for line in lbl.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            fine = names[int(parts[0])]
            group = G.get(fine)
            if group is None:
                stat[f"пропущен класс {fine}"] += 1
                continue
            lines.append(" ".join([str(GID[group])] + parts[1:]))
            stat[group] += 1
        link(img, dst / "images" / img.name)
        (dst / "labels" / (img.stem + ".txt")).write_text("\n".join(lines), encoding="utf-8")
        stat["кадров"] += 1
    return stat


def read_names(yaml_path: Path) -> list[str]:
    names, on = {}, False
    for line in yaml_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("names:"):
            on = True
        elif on and ":" in line:
            i, n = line.strip().split(":", 1)
            names[int(i)] = n.strip()
    return [names[i] for i in sorted(names)]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ours", type=Path, default=ML / "data/interim/ours_yolo_x")
    ap.add_argument("--kaggle", type=Path, default=ML / "data/external/lct7-kaggle-thin")
    ap.add_argument("--apoce", type=Path, default=ML / "data/external/lct7-apoce")
    ap.add_argument("--out", type=Path, default=ML / "data/interim/coarse")
    args = ap.parse_args()

    print("групп:", len(GROUPS), "->", ", ".join(GROUPS), "\n")

    jobs = [
        ("ours", args.ours, read_names(args.ours / "data.yaml"), ["train", "val"]),
        ("kaggle", args.kaggle, read_names(args.kaggle / "data.yaml"), ["train"]),
        ("apoce", args.apoce, read_names(args.apoce / "data.yaml"), ["train"]),
    ]
    for tag, root, names, splits in jobs:
        for split in splits:
            src = root / split / "images"
            if not src.is_dir():
                print(f"{tag}/{split}: нет папки {src}")
                continue
            stat = convert_split(src, args.out / tag / split, names)
            top = ", ".join(f"{k} {v}" for k, v in stat.most_common(6) if k != "кадров")
            print(f"{tag}/{split}: кадров {stat['кадров']}, {top}")

    yaml = args.out / "ours" / "data.yaml"
    yaml.write_text(
        f"path: {(args.out / 'ours').resolve().as_posix()}\ntrain: train/images\nval: val/images\nnames:\n"
        + "\n".join(f"  {i}: {g}" for i, g in enumerate(GROUPS)) + "\n", encoding="utf-8")
    print(f"\nконфиг: {yaml}")
    return 0


if __name__ == "__main__":
    main()
