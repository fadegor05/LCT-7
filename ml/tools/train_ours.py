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
    ap.add_argument("--extra", type=Path, nargs="*", default=[],
                    help="дополнительные наборы в формате YOLO (например MOCS)")
    ap.add_argument("--weights", type=str, default=str(ML / "weights/yolo26s_k_apoce_best.pt"))
    ap.add_argument("--repeat", type=int, default=10, help="во сколько раз повторить наши кадры")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr0", type=float, default=0.002, help="ниже обычного 0.01: дообучение, не обучение")
    ap.add_argument("--workers", type=int, default=2,
                    help="процессов загрузчика; на Windows каждый заново грузит torch, "
                         "при 4+ падает WinError 1455 (мал файл подкачки)")
    ap.add_argument("--patience", type=int, default=15)
    ap.add_argument("--strong-aug", action="store_true",
                    help="агрессивная аугментация: при 73 кадрах разнообразие важнее точности копии")
    ap.add_argument("--name", default="ours_mix")
    ap.add_argument("--project", type=Path, default=ML / "runs")
    args = ap.parse_args()

    ours = images(args.ours / "train/images")
    kaggle = images(args.kaggle / "train/images")
    apoce = images(args.apoce / "train/images")
    extra = [p for d in args.extra for p in images(d / "train/images")]
    listing = kaggle + apoce + extra + ours * args.repeat

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

    print(f"Kaggle {len(kaggle)} + APOCE {len(apoce)} + доп. {len(extra)} + "
          f"наши {len(ours)}x{args.repeat} = {len(listing)} кадров в эпохе")
    print(f"старт с {Path(args.weights).name}, lr0 {args.lr0}, {args.epochs} эпох, imgsz {args.imgsz}")

    from ultralytics import YOLO
    model = YOLO(args.weights)
    aug = dict(mosaic=1.0, copy_paste=0.3, scale=0.7, degrees=5.0, translate=0.2,
               fliplr=0.5, hsv_v=0.5, close_mosaic=10) if args.strong_aug else {}
    model.train(data=str(data_yaml), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch,
                lr0=args.lr0, project=str(args.project), name=args.name, seed=0,
                patience=args.patience, workers=args.workers, exist_ok=True,
                plots=False, cache=False, **aug)
    print(f"веса: {args.project / args.name / 'weights/best.pt'}")
    return 0


if __name__ == "__main__":
    main()
