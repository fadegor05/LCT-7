"""вовлечённость техники в этап работ по одному кадру.

Определить по фотографии, работает машина или простаивает, нельзя: работа и
простой различаются производной конфигурации по времени, а кадр — срез нулевой
длительности. В литературе 2007-2026 нет ни одной работы, делающей это по одному
кадру (`research/part_N_activity.md`).

Заказчик на Q&A 21:53 сам предложил замену: определять «в соответствии с той
зоной, где находится техника», а пример аномалии на 20:29 — «экскаватор стоит у
въезда и никак не задействован в процессе производимого этапа». Это вовлечённость,
и она наблюдаема на одном кадре.

Три однокадровых признака:

1. **Парная техника** — самосвал у экскаватора, миксер у бетононасоса. Правило
   спаривания Chen et al. (ISARC 2020): машины в одной группе, если расстояние
   между центрами меньше `0.5 * (w1 + w2)`. Там же измерено: отсутствие самосвала
   рядом объясняет **74% всего времени простоя** экскаватора.
2. **Соответствие этапу** — класс машины входит в правило текущего этапа.
3. **Зона** — машина у края кадра и вне скопления техники. Геометрии площадки у
   нас нет (E7: кадры не группируются по пикселям), поэтому зона приближается
   расстоянием до основной группы техники на кадре.

Выход на машину: `engaged` / `not_engaged` / `unknown`. `unknown` — честный ответ,
когда признаков недостаточно, и его доля измеряется, а не прячется.
"""

import argparse, json
from collections import Counter
from pathlib import Path

ML = Path(__file__).resolve().parents[1]

# кто с кем работает в паре: класс -> классы-партнёры
PAIRS = {
    "excavator_crawler": ["dump_truck", "truck_unknown"],
    "excavator_wheeled": ["dump_truck", "truck_unknown"],
    "excavator_unknown": ["dump_truck", "truck_unknown"],
    "backhoe_loader": ["dump_truck", "truck_unknown"],
    "concrete_pump": ["concrete_mixer"],
    "concrete_mixer": ["concrete_pump", "tower_crane", "crawler_crane"],
    "drilling_rig": ["concrete_mixer", "concrete_pump", "crawler_crane", "flatbed_truck"],
    "pile_driver": ["crawler_crane", "flatbed_truck"],
    "dwall_rig": ["concrete_pump", "crawler_crane"],
    "tower_crane": ["concrete_mixer", "flatbed_truck"],
    "crawler_crane": ["flatbed_truck", "drilling_rig", "pile_driver"],
    "truck_crane": ["flatbed_truck"],
    "wheel_loader": ["dump_truck", "truck_unknown"],
    "dump_truck": ["excavator_crawler", "excavator_wheeled", "excavator_unknown",
                   "backhoe_loader", "wheel_loader"],
}


def centre(b):
    return (b[0] + b[2]) / 2, (b[1] + b[3]) / 2


def paired(det, others) -> str | None:
    """Партнёр рядом по правилу Chen: расстояние центров < 0.5*(w1+w2)."""
    partners = PAIRS.get(det["class_ours"], [])
    if not partners:
        return None
    cx, cy = centre(det["bbox"])
    w1 = det["bbox"][2] - det["bbox"][0]
    for o in others:
        if o["class_ours"] not in partners:
            continue
        ox, oy = centre(o["bbox"])
        w2 = o["bbox"][2] - o["bbox"][0]
        dist = ((cx - ox) ** 2 + (cy - oy) ** 2) ** 0.5
        if dist < 0.5 * (w1 + w2):
            return o["class_ours"]
    return None


def stage_classes(rules: dict, stage_code: str | None) -> set[str]:
    """Все классы, упомянутые в правиле этапа: техника этапа."""
    if not stage_code or stage_code not in rules:
        return set()
    out = set()
    for v in rules[stage_code].get("variants", []):
        for item in v.get("required", []) + v.get("auxiliary", []):
            out.add(item["class"])
    return out


def annotate_frame(record: dict, rules: dict, stage_code: str | None,
                   conf_min: float) -> list[dict]:
    dets = [d for d in record["detections"] if d["conf"] >= conf_min]
    relevant = stage_classes(rules, stage_code)
    out = []
    for d in dets:
        others = [o for o in dets if o is not d]
        partner = paired(d, others)
        in_stage = d["class_ours"] in relevant if relevant else None

        reasons = []
        if partner:
            reasons.append(f"рядом {partner}")
        if in_stage:
            reasons.append("техника текущего этапа")

        if partner and in_stage is not False:
            state = "engaged"
        elif in_stage is False and not partner:
            state = "not_engaged"
            reasons.append("класс не участвует в текущем этапе, партнёра рядом нет")
        else:
            state = "unknown"
            if not reasons:
                reasons.append("признаков недостаточно")

        out.append({**d, "engagement": state, "engagement_why": "; ".join(reasons)})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--detections", type=Path, default=ML / "data/processed/detections_mocs_mix.json")
    ap.add_argument("--rules", type=Path, default=ML / "configs/rules.json")
    ap.add_argument("--stage", default=None, help="код текущего этапа; без него судим только по паре")
    ap.add_argument("--conf", type=float, default=0.25)
    ap.add_argument("--out", type=Path, default=ML / "data/processed/engagement.json")
    args = ap.parse_args()

    data = json.loads(args.detections.read_text(encoding="utf-8"))
    rules_raw = json.loads(args.rules.read_text(encoding="utf-8"))
    rules = {r["stage_code"]: r for r in rules_raw["rules"]}
    for r in rules_raw["rules"]:
        for code in r.get("merged_from", []):
            rules[code] = r

    stat, by_class = Counter(), Counter()
    images = []
    for rec in data["images"]:
        dets = annotate_frame(rec, rules, args.stage, args.conf)
        for d in dets:
            stat[d["engagement"]] += 1
            by_class[(d["class_ours"], d["engagement"])] += 1
        images.append({**rec, "detections": dets})

    payload = {"meta": {**data["meta"], "engagement": {"conf": args.conf, "stage": args.stage,
                                                       "rule": "Chen ISARC 2020: dist < 0.5*(w1+w2)"}},
               "images": images}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    total = sum(stat.values())
    print(f"рамок: {total}")
    for k in ("engaged", "not_engaged", "unknown"):
        print(f"  {k:<12}{stat[k]:>5}  {stat[k]/total*100 if total else 0:.0f}%")
    print("\nпо классам (engaged / всего):")
    classes = {c for c, _ in by_class}
    for c in sorted(classes, key=lambda c: -sum(by_class[(c, s)] for s in ("engaged", "not_engaged", "unknown"))):
        tot = sum(by_class[(c, s)] for s in ("engaged", "not_engaged", "unknown"))
        print(f"  {c:<20}{by_class[(c,'engaged')]:>4} / {tot}")
    print(f"\nрезультат: {args.out}")
    return 0


if __name__ == "__main__":
    main()
