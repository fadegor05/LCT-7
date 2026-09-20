"""дообучение детектора на смеси: Kaggle CCTV + APOCE + наши кадры (D-014).

Наши 24 кадра тонут среди 3 400 чужих, поэтому список обучающих изображений
собирается вручную, и наши кадры в нём повторяются --repeat раз. Ultralytics
принимает .txt со списком путей, а повтор строки — это и есть oversampling.

Стартуем с весов Захара, а не с COCO: они уже знают технику с камер, нам нужно
добавить буровые и копры, снятые с земли. Шаг обучения ниже обычного, иначе
дообучение сотрёт выученное (катастрофическое забывание).

Проверка — только на наших p03/p08: именно на них меряется то, ради чего всё.
Качество на камерах проверяем отдельно, после, чтобы увидеть, что забылось.
"""

import argparse
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
EXT = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}


def images(folder: Path) -> list[Path]:
    return sorted(p.resolve() for p in folder.iterdir() if p.suffix.lower() in EXT)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ours", type=Path, default=ML / "data/interim/ours_yolo")
    ap.add_argument("--kaggle", type=Path, default=ML / "data/external/lct7-kaggle-thin")
    ap.add_argument("--apoce", type=Path, default=ML / "data/external/lct7-apoce")
    ap.add_argument("--weights", type=str, default=str(ML / "weights/yolo26s_k_apoce_best.pt"))
    ap.add_argument("--repeat", type=int, default=10, help="во сколько раз повторить наши кадры")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr0", type=float, default=0.002, help="ниже обычного 0.01: дообучение, не обучение")
    ap.add_argument("--name", default="ours_mix")
    ap.add_argument("--project", type=Path, default=ML / "runs")
    args = ap.parse_args()

    ours = images(args.ours / "train/images")
    kaggle = images(args.kaggle / "train/images")
    apoce = images(args.apoce / "train/images")
    listing = kaggle + apoce + ours * args.repeat

    cfg_dir = args.project / "cfg"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    train_txt = cfg_dir / f"{args.name}_train.txt"
    train_txt.write_text("\n".join(p.as_posix() for p in listing) + "\n", encoding="utf-8")

    names = (args.ours / "data.yaml").read_text(encoding="utf-8").split("names:")[1]
    data_yaml = cfg_dir / f"{args.name}_data.yaml"
    data_yaml.write_text(
        f"train: {train_txt.resolve().as_posix()}\n"
        f"val: {(args.ours / 'val/images').resolve().as_posix()}\n"
        f"names:{names}", encoding="utf-8")

    print(f"Kaggle {len(kaggle)} + APOCE {len(apoce)} + наши {len(ours)}x{args.repeat} "
          f"= {len(listing)} кадров в эпохе")
    print(f"старт с {Path(args.weights).name}, lr0 {args.lr0}, {args.epochs} эпох, imgsz {args.imgsz}")

    from ultralytics import YOLO
    model = YOLO(args.weights)
    model.train(data=str(data_yaml), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                lr0=args.lr0, project=str(args.project), name=args.name, seed=0,
                patience=10, workers=4, exist_ok=True, plots=False, cache=False)
    print(f"веса: {args.project / args.name / 'weights/best.pt'}")
    return 0


if __name__ == "__main__":
    main()
