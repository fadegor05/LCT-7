"""подбор порогов для гибрида: сетка по двум числам, проверка leave-one-site-out.

Детекторы заново не гоняются: оба файла детекций уже готовы, слияние — пересборка
в памяти, поэтому 100+ комбинаций считаются за секунды.

Критерий из наших решений: максимум точности при полноте не ниже --min-recall.
Точность важнее полноты, потому что лишняя рамка = ложное подтверждение этапа,
и отставание прячется; пропуск даёт ложную тревогу, а её видно по снимкам в алерте.

Подбираем на одной площадке, проверяем на другой (и наоборот). Выбирать надо не
пик, а середину плато: одиночный максимум на 23 кадрах — почти наверняка случайность.
"""

import argparse, json
from pathlib import Path

from merge_detections import collect, resolve
from eval_groups import G, evaluate, load_gt


def merged_dets(sources: dict[str, dict], confs: dict[str, float], conflict_iou: float,
                images) -> dict[str, list]:
    """Слияние с заданными порогами -> {кадр: [(группа, bbox, conf), ...]} для evaluate."""
    config = {"sources": {name: {"conf": c} for name, c in confs.items()}}
    out = {}
    for image in images:
        boxes = resolve(collect(sources, config, image), conflict_iou)
        out[image] = [(G[b["class_ours"]], b["bbox"], b["conf"])
                      for b in boxes if b["class_ours"] in G]
    return out


def frange(lo, hi, step):
    out, v = [], lo
    while v <= hi + 1e-9:
        out.append(round(v, 3)); v += step
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, default=Path("configs/merge.json"))
    ap.add_argument("--sites", nargs="+", default=["p03", "p08"], help="площадки-фолды")
    ap.add_argument("--min-recall", type=float, default=0.5)
    ap.add_argument("--grid-a", nargs=3, type=float, default=[0.05, 0.50, 0.05],
                    metavar=("LO", "HI", "STEP"), help="сетка для первого источника")
    ap.add_argument("--grid-b", nargs=3, type=float, default=[0.20, 0.80, 0.05],
                    metavar=("LO", "HI", "STEP"), help="сетка для второго источника")
    ap.add_argument("--out", type=Path, default=Path("data/processed/tune_merge.json"))
    args = ap.parse_args()

    config = json.loads(args.config.read_text(encoding="utf-8"))
    names = list(config["sources"])
    if len(names) != 2:
        raise SystemExit("перебор рассчитан на два источника")
    sources = {n: {rec["image"]: rec
                   for rec in json.loads(Path(cfg["file"]).read_text(encoding="utf-8"))["images"]}
               for n, cfg in config["sources"].items()}
    conflict_iou = config["conflict_iou"]

    gt = {site: load_gt({site}) for site in args.sites}
    for site, g in gt.items():
        print(f"{site}: кадров {len(g)}, рамок {sum(len(v) for v in g.values())}")

    grid_a = frange(*args.grid_a)
    grid_b = frange(*args.grid_b)
    print(f"комбинаций: {len(grid_a) * len(grid_b)}")

    rows = []
    for a in grid_a:
        for b in grid_b:
            confs = {names[0]: a, names[1]: b}
            row = {"confs": confs, "sites": {}}
            for site, g in gt.items():
                res = evaluate(merged_dets(sources, confs, conflict_iou, g), g,
                               conf_min=min(a, b))
                row["sites"][site] = {k: res[k] for k in ("precision", "recall", "f05", "map50")}
            rows.append(row)

    def ok(site_res):
        return site_res["recall"] >= args.min_recall

    print(f"\n--- подбор на одной площадке, проверка на другой (полнота >= {args.min_recall})")
    for fit in args.sites:
        test = [s for s in args.sites if s != fit]
        good = [r for r in rows if ok(r["sites"][fit])]
        if not good:
            print(f"подбор на {fit}: ни одна комбинация не даёт нужной полноты")
            continue
        best = max(good, key=lambda r: r["sites"][fit]["precision"])
        c = best["confs"]
        line = f"подбор на {fit}: {names[0]} {c[names[0]]:.2f}, {names[1]} {c[names[1]]:.2f}" \
               f" -> P {best['sites'][fit]['precision']:.2f} R {best['sites'][fit]['recall']:.2f}"
        for t in test:
            line += f" | на {t}: P {best['sites'][t]['precision']:.2f} R {best['sites'][t]['recall']:.2f}"
        print(line)

    print("\n--- лучшие 10 по среднему F0.5 обеих площадок (ищем плато, а не пик)")
    def mean_f05(r):
        return sum(v["f05"] for v in r["sites"].values()) / len(r["sites"])
    header = f"{names[0]:>10}{names[1]:>12}" + "".join(f"{s+' P/R':>12}" for s in args.sites) + f"{'F0.5':>8}"
    print(header)
    for r in sorted(rows, key=mean_f05, reverse=True)[:10]:
        c = r["confs"]
        cells = "".join(f"{v['precision']:.2f}/{v['recall']:.2f}".rjust(12) for v in r["sites"].values())
        print(f"{c[names[0]]:>10.2f}{c[names[1]]:>12.2f}{cells}{mean_f05(r):>8.3f}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nвсе комбинации: {args.out}")
    return 0


if __name__ == "__main__":
    main()
