"""проверка весов на произвольном наборе в формате YOLO.

Нужна, чтобы измерять забывание: что модель теряет на камерах Kaggle, научившись
буровым на наших кадрах.

`workers=0` намеренно: на Windows загрузчик порождает процессы заново, и запуск
через стандартный ввод (heredoc) у него зависает. Здесь файл, но запас надёжности
дешевле десятка секунд.
"""

import argparse
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("weights", nargs="+")
    ap.add_argument("--data", type=Path, required=True, help="data.yaml набора")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--split", default="val", choices=["val", "test"])
    args = ap.parse_args()

    from ultralytics import YOLO
    for w in args.weights:
        r = YOLO(w).val(data=str(args.data), imgsz=args.imgsz, batch=args.batch,
                        split=args.split, plots=False, workers=0, verbose=False)
        print(f"{Path(w).stem}: mAP50 {r.box.map50:.3f}  mAP50-95 {r.box.map:.3f}")
    return 0


if __name__ == "__main__":
    main()
