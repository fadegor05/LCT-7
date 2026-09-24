"""MOCS (41 тыс. кадров реальных строек) -> наша таксономия.

Закрывает пустые классы: копёр, бетононасос, каток, бульдозер — их в нашей
разметке было по 0-1 примеру (E13: единственный оставшийся рычаг — внешние
данные). Лицензия MIT, зеркало в формате YOLO: huggingface.co/datasets/AmiyaChan/mocs_yolo

**Копёр MOCS отображается в `drilling_unknown`, а не в `pile_driver`.** В MOCS
нет отдельного класса буровой установки, значит в `pile_driver` там собраны и
копры, и буровые. Специфичный класс на таких данных учить нельзя: ровно эта
путаница ломала статусы этапов в B0. Грубый класс честен: он говорит «машина с
мачтой», а различает их наша собственная разметка (93 буровые, 26 копров).

Кадры MOCS не размечены по нашим редким классам (экскаватор-погрузчик,
телескопический погрузчик), но это не пропуски-ловушки: таких машин там просто
нет в аннотациях, и модель увидит их как фон. Поэтому кадры, где размечены
только рабочие (класс 0), пропускаем целиком — в них почти наверняка есть
неразмеченная техника.
"""

import argparse, os, shutil
from collections import Counter
from pathlib import Path

ML = Path(__file__).resolve().parents[1]

MOCS = ["worker", "static_crane", "hanging_head", "crane", "roller", "bulldozer",
        "excavator", "truck", "loader", "pump_truck", "concrete_mixer",
        "pile_driver", "other_vehicle"]

# MOCS -> наш класс; None = рамку не переносим
TO_OURS = {
    "static_crane": "tower_crane",
    "crane": "crane_unknown",          # автокран и гусеничный в MOCS не разделены
    "roller": "roller",
    "bulldozer": "bulldozer",
    "excavator": "excavator_unknown",  # гусеничный/колёсный не разделены
    "truck": "truck_unknown",
    "loader": "loader_unknown",
    "pump_truck": "concrete_pump",
    "concrete_mixer": "concrete_mixer",
    "pile_driver": "drilling_unknown",  # см. docstring
    "worker": None,
    "hanging_head": None,              # крюк крана — не техника
    "other_vehicle": None,
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


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=ML / "data/external/mocs")
    ap.add_argument("--out", type=Path, default=ML / "data/interim/mocs_ours")
    ap.add_argument("--names", type=Path, default=ML / "data/external/lct7-kaggle-thin/data.yaml",
                    help="порядок классов нашей головы")
    ap.add_argument("--splits", nargs="+", default=["train"])
    ap.add_argument("--min-objects", type=int, default=1,
                    help="кадры, где после перевода не осталось рамок, пропускаем")
    ap.add_argument("--only-with", nargs="*", default=None,
                    help="брать только кадры, где есть хотя бы один из этих наших классов. "
                         "23 тыс. чужих кадров против наших 73 утянут модель в чужой домен, "
                         "поэтому берём срез по классам, которых у нас нет")
    args = ap.parse_args()

    ours = {n: i for i, n in enumerate(read_names(args.names))}
    missing = {v for v in TO_OURS.values() if v and v not in ours}
    if missing:
        raise SystemExit(f"классов нет в нашей голове: {missing}")

    stat, kept, skipped = Counter(), 0, Counter()
    for split in args.splits:
        img_dir = args.out / split / "images"
        lbl_dir = args.out / split / "labels"
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        for lbl in sorted((args.src / "labels" / split).glob("*.txt")):
            lines, frame_classes = [], set()
            for line in lbl.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) < 5:
                    continue
                mocs_name = MOCS[int(parts[0])]
                our = TO_OURS.get(mocs_name)
                if our is None:
                    skipped[mocs_name] += 1
                    continue
                lines.append(" ".join([str(ours[our])] + parts[1:5]))
                frame_classes.add(our)
                stat[our] += 1
            if len(lines) < args.min_objects:
                skipped["кадр без нашей техники"] += 1
                continue
            if args.only_with and not (frame_classes & set(args.only_with)):
                skipped["нет нужных классов"] += 1
                continue
            src_img = None
            for ext in (".jpg", ".jpeg", ".png"):
                cand = args.src / "images" / split / (lbl.stem + ext)
                if cand.exists():
                    src_img = cand
                    break
            if src_img is None:
                skipped["нет кадра"] += 1
                continue
            dst = img_dir / src_img.name
            if not dst.exists():
                try:
                    os.link(src_img, dst)
                except OSError:
                    shutil.copy(src_img, dst)
            (lbl_dir / (lbl.stem + ".txt")).write_text("\n".join(lines), encoding="utf-8")
            kept += 1

    print(f"кадров перенесено: {kept}")
    print("рамок по нашим классам:")
    for k, v in stat.most_common():
        print(f"  {v:>6}  {k}")
    print("пропущено:", dict(skipped.most_common(6)))
    return 0


if __name__ == "__main__":
    main()
