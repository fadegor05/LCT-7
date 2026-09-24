"""Оценка детектора на нашей разметке (p03/p08) по группам классов, IoU 0.5.

Группы нужны потому, что модели Захара знают экскаватор только как
`excavator_unknown`, а в нашей разметке стоит `excavator_crawler`: без
группировки верная находка засчиталась бы как промах.

Принимает готовый JSON детекций или веса .pt. Функции пригодны для импорта:
`load_gt`, `evaluate`, `match` использует tools/tune_merge.py.
"""
import json, glob, sys, collections
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
IMG = ML / "data/raw/dataset/images/Строительная_техника"
GROUP = {
    "excavator": ["excavator_crawler", "excavator_wheeled", "excavator_unknown"],
    "backhoe_loader": ["backhoe_loader"],
    "tower_crane": ["tower_crane"],
    "mobile_crane": ["truck_crane", "crawler_crane", "loader_crane", "crane_unknown"],
    "drilling": ["drilling_rig", "pile_driver", "dwall_rig", "drilling_unknown", "drilling_like"],
    "truck": ["dump_truck", "flatbed_truck", "truck_unknown"],
    "concrete_mixer": ["concrete_mixer"], "concrete_pump": ["concrete_pump"],
    "loader": ["wheel_loader", "telehandler", "loader_unknown"],
    "bulldozer": ["bulldozer"], "roller": ["roller"], "grader": ["grader"], "paver": ["paver"],
}
# точный класс -> группа; имя самой группы отображается в себя, чтобы модель,
# обученную сразу на группах (make_coarse_dataset.py), можно было мерить тем же кодом
G = {c: g for g, cs in GROUP.items() for c in cs}
G.update({g: g for g in GROUP})


def iou(a, b):
    ix = max(0, min(a[2], b[2]) - max(a[0], b[0])); iy = max(0, min(a[3], b[3]) - max(a[1], b[1]))
    i = ix * iy; u = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - i
    return i / u if u else 0


def load_gt(sites=None) -> dict[str, list]:
    """{имя кадра: [(группа, bbox в долях), ...]}; sites — например {"p03"}."""
    gt = {}
    for f in glob.glob(str(ML / "data/reference/labels/*/*.json")):
        if sites is not None and Path(f).parent.name not in sites:
            continue
        d = json.load(open(f, encoding="utf-8"))
        W, H = d["imageWidth"], d["imageHeight"]
        boxes = []
        for s in d["shapes"]:
            xs = [p[0] for p in s["points"]]; ys = [p[1] for p in s["points"]]
            boxes.append((G.get(s["label"], "?" + s["label"]),
                          [min(xs)/W, min(ys)/H, max(xs)/W, max(ys)/H]))
        gt[d["imagePath"]] = boxes
    return gt


def ap(tp_conf, npos):
    tp_conf.sort(key=lambda t: -t[1]); tp = fp = 0; prec = []; rec = []
    for t, _ in tp_conf:
        tp += t; fp += 1 - t; prec.append(tp / (tp + fp)); rec.append(tp / npos)
    s = 0; prev = 0
    for k in range(len(prec)):
        s += (rec[k] - prev) * max(prec[k:]); prev = rec[k]
    return s


def match(det, boxes, conf_min=0.25):
    """Сопоставление рамок кадра с разметкой. det: [(группа, bbox, conf), ...].

    Возвращает (preds, hits, fps, confusions): preds — пары (попал, conf) для AP,
    остальное — счётчики при пороге conf_min.
    """
    preds, hits, fps, confusions = [], collections.Counter(), collections.Counter(), collections.Counter()
    used = set()
    for g, b, p in sorted(det, key=lambda x: -x[2]):
        best, bi = 0, None
        for i, (gg, gb) in enumerate(boxes):
            if gg == g and i not in used:
                v = iou(b, gb)
                if v > best:
                    best, bi = v, i
        ok = best >= 0.5
        if ok:
            used.add(bi)
        preds.append((g, int(ok), p))
        if p >= conf_min:
            if ok:
                hits[g] += 1
            else:
                fps[g] += 1
                lab = max(((iou(b, gb), gg) for gg, gb in boxes), default=(0, "фон"))
                confusions[(g, lab[1] if lab[0] >= 0.3 else "фон")] += 1
    return preds, hits, fps, confusions


def evaluate(dets: dict[str, list], gt: dict[str, list], conf_min=0.25) -> dict:
    """dets: {кадр: [(группа, bbox, conf), ...]}. Считает AP по группам и P/R при conf_min."""
    by_group = collections.defaultdict(list)
    npos, hits, fps, confusions = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
    for name, boxes in gt.items():
        for g, _ in boxes:
            npos[g] += 1
        preds, h, f, c = match(dets.get(name, []), boxes, conf_min)
        for g, ok, p in preds:
            by_group[g].append((ok, p))
        hits += h; fps += f; confusions += c
    groups = {}
    for g in set(npos) | set(by_group):
        tp, fp = hits[g], fps[g]
        groups[g] = {
            "n": npos[g],
            "ap50": ap(by_group[g], npos[g]) if npos[g] else float("nan"),
            "r": tp / npos[g] if npos[g] else 0.0,
            "p": tp / (tp + fp) if tp + fp else 0.0,
            "tp": tp, "fp": fp,
        }
    aps = [v["ap50"] for v in groups.values() if v["n"]]
    tp_all, fp_all, n_all = sum(hits.values()), sum(fps.values()), sum(npos.values())
    recall = tp_all / n_all if n_all else 0.0
    precision = tp_all / (tp_all + fp_all) if tp_all + fp_all else 0.0
    f05 = (1.25 * precision * recall / (0.25 * precision + recall)) if precision + recall else 0.0
    return {"groups": groups, "map50": sum(aps) / len(aps) if aps else 0.0,
            "precision": precision, "recall": recall, "f05": f05, "confusions": confusions}


def dets_from_json(path) -> dict[str, list]:
    d = json.load(open(path, encoding="utf-8"))
    return {im["image"]: [(G[x["class_ours"]], x["bbox"], x["conf"])
                          for x in im["detections"] if x["class_ours"] in G]
            for im in d["images"]}


def dets_from_weights(weights, gt, imgsz=960, conf=0.01) -> dict[str, list]:
    from ultralytics import YOLO
    m = YOLO(weights)
    out = {}
    for name in gt:
        r = m.predict(str(IMG / name), imgsz=imgsz, conf=conf, verbose=False)[0]
        out[name] = [(G[m.names[int(c)]], b.tolist(), float(p))
                     for c, b, p in zip(r.boxes.cls, r.boxes.xyxyn, r.boxes.conf)]
    return out


def report(title, res):
    print(f"\n=== {title}  (IoU 0.5; P/R при conf 0.25)")
    print(f"{'группа':<16}{'рамок':>6}{'AP50':>7}{'R':>7}{'P':>7}")
    for g, v in sorted(res["groups"].items(), key=lambda kv: -kv[1]["n"]):
        print(f"{g:<16}{v['n']:>6}{v['ap50']:>7.3f}{v['r']:>7.2f}{v['p']:>7.2f}")
    print(f"mAP50 по группам с рамками: {res['map50']:.3f}; "
          f"в целом P {res['precision']:.2f} R {res['recall']:.2f} F0.5 {res['f05']:.2f}")
    print("ложные срабатывания (conf>=0.25): предсказано -> на самом деле:",
          ", ".join(f"{a}->{b} {n}" for (a, b), n in res["confusions"].most_common(8)))


def main(argv):
    gt = load_gt()
    for w in argv:
        dets = dets_from_json(w) if w.endswith(".json") else dets_from_weights(w, gt)
        report(Path(w).stem, evaluate(dets, gt))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
