"""простой техники по ряду кадров одной камеры.

Это ответ на требование ТЗ «определение факта работы и простоя техники»
(Q&A 11:58) в той единственной постановке, в которой оно наблюдаемо. По одному
кадру работа и простой не различаются: кадр — срез нулевой длительности, а
различие между ними — движение (D-017, `research/part_N_activity.md`, 33
источника, ни одного метода без сравнения кадров). Зато по **ряду** кадров с
неподвижной камеры различие измеримо прямо: машина либо сместилась, либо нет.

Как считаем:

1. кадры одной камеры упорядочиваем по времени;
2. объекты соседних кадров связываем по классу и перекрытию рамок (IoU);
3. считаем смещение центра рамки в долях её собственного размера — так мерка не
   зависит ни от разрешения, ни от того, ближе машина к камере или дальше;
4. смещение больше `--moved` — `moved`, меньше `--still` — `still`, между ними
   `unclear`: серая зона названа, а не спрятана в округлении;
5. по классу техники выдаём долю неподвижных наблюдений с интервалом Уилсона.

Чего метод **не** делает и что записано в `cannot_claim` результата:

- неподвижный экскаватор не обязательно простаивает: он копает с места, а
  поворот стрелы на снимке сверху смещает рамку мало. Поэтому величина названа
  «доля наблюдений без смещения», а не «доля простоя»;
- метод требует **неподвижной камеры**: если её подвинули, сместится всё сразу.
  Кадр, где сдвинулась доля объектов больше `--camera-moved`, из расчёта
  выбрасывается и попадает в счётчик `frames_skipped_camera_moved`. Проверка
  включается только при трёх и более связанных объектах: по одной машине сдвиг
  камеры от движения техники неотличим;
- интервал между кадрами должен быть коротким: при разрыве больше `--max-gap`
  минут пара кадров не сравнивается. За полчаса машина успевает уехать и
  вернуться, и «не сместилась» перестаёт что-либо значить.

Вход — тот же контракт детекций, что у всей цепочки (`docs/CONTRACTS.md`), плюс
поля `camera_id` и `timestamp` (ISO 8601). Выход — JSON с долями по классам.

    python tools/activity_series.py data/processed/detections_camera.json
    python tools/activity_series.py dets.json --moved 0.15 --max-gap 10
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ML / "tools"))

from match_schedule import wilson  # noqa: E402

# Ниже этого перекрытия две рамки считаем разными машинами, а не одной
# сместившейся. 0.3 — то же значение, что и при дедупликации в site_state.py.
LINK_IOU = 0.3
MIN_SAMPLES = 10  # порог, ниже которого долю не оцениваем (как в work_sampling)
CAMERA_CHECK_MIN = 3  # меньше объектов — сдвиг камеры от движения техники не отличить


def iou(a: list[float], b: list[float]) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union else 0.0


def shift(a: list[float], b: list[float]) -> float:
    """Смещение центра в долях собственного размера рамки.

    Делим на размер машины, а не на размер кадра: иначе дальняя техника всегда
    выглядела бы неподвижной просто потому, что её рамка мельче.
    """
    ax, ay = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    bx, by = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
    size = max((a[2] - a[0] + b[2] - b[0]) / 2, (a[3] - a[1] + b[3] - b[1]) / 2, 1e-6)
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5 / size


def link(prev: list[dict], cur: list[dict]) -> list[tuple[dict, dict]]:
    """Жадное связывание: каждой рамке — лучшая пара того же класса.

    Жадность здесь уместна: на площадке редко стоят две одинаковые машины в
    перекрывающихся рамках, а венгерский алгоритм добавил бы зависимость ради
    случая, которого на наших кадрах нет.
    """
    used, pairs = set(), []
    for c in cur:
        best, best_iou = None, LINK_IOU
        for i, p in enumerate(prev):
            if i in used or p["class_ours"] != c["class_ours"]:
                continue
            v = iou(p["bbox"], c["bbox"])
            if v > best_iou:
                best, best_iou = i, v
        if best is not None:
            used.add(best)
            pairs.append((prev[best], c))
    return pairs


def parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def analyse(frames: list[dict], moved: float = 0.10, still: float = 0.03,
            max_gap: int = 10, camera_moved: float = 0.8) -> dict:
    """Ряды кадров по камерам → доли неподвижных наблюдений по классам."""
    by_camera: dict[str, list[dict]] = defaultdict(list)
    skipped_no_time = 0
    for fr in frames:
        stamp = parse_time(fr.get("timestamp", ""))
        if stamp is None:
            skipped_no_time += 1
            continue
        by_camera[fr.get("camera_id") or ""].append({**fr, "_t": stamp})

    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    pairs_used = frames_skipped = gaps_skipped = 0

    for cam, series in by_camera.items():
        series.sort(key=lambda f: f["_t"])
        for prev, cur in zip(series, series[1:]):
            minutes = (cur["_t"] - prev["_t"]).total_seconds() / 60
            if minutes <= 0 or minutes > max_gap:
                gaps_skipped += 1
                continue
            linked = link(prev.get("detections", []), cur.get("detections", []))
            if not linked:
                continue
            shifts = [(p, c, shift(p["bbox"], c["bbox"])) for p, c in linked]
            # Если сдвинулось почти всё сразу — это камера, а не техника.
            # Правило применимо только когда объектов хватает: по одной машине
            # сдвиг камеры и честно едущий экскаватор неразличимы, и выбрасывать
            # такую пару значило бы терять ровно те наблюдения, ради которых всё
            # и считается. Порог в три объекта нашла проверка на построенных
            # рядах (tests/test_pipeline.py).
            if (len(shifts) >= CAMERA_CHECK_MIN
                    and sum(1 for *_, s in shifts if s > moved) / len(shifts) >= camera_moved):
                frames_skipped += 1
                continue
            for _, c, s in shifts:
                verdict = "moved" if s > moved else "still" if s < still else "unclear"
                counts[c["class_ours"]][verdict] += 1
                pairs_used += 1

    classes = []
    for cls, c in sorted(counts.items()):
        decided = c["moved"] + c["still"]
        row = {"class": cls, "pairs": decided + c["unclear"],
               "moved": c["moved"], "still": c["still"], "unclear": c["unclear"]}
        if decided >= MIN_SAMPLES:
            low, high = wilson(c["still"], decided)
            row["still_share"] = round(c["still"] / decided, 3)
            row["interval"] = [round(low, 3), round(high, 3)]
            row["basis"] = (f"{c['still']} наблюдений без смещения из {decided} "
                            f"определённых; интервал Уилсона 95%")
        else:
            row["basis"] = (f"определённых наблюдений {decided} — меньше порога "
                            f"{MIN_SAMPLES}, доля не оценивается")
        classes.append(row)

    return {
        "classes": classes,
        "meta": {"cameras": len(by_camera), "frames": len(frames),
                 "pairs_used": pairs_used,
                 "frames_without_time": skipped_no_time,
                 "frames_skipped_camera_moved": frames_skipped,
                 "pairs_skipped_gap": gaps_skipped,
                 "thresholds": {"moved": moved, "still": still,
                                "max_gap_minutes": max_gap}},
        "cannot_claim": ("Измеряется смещение рамки между кадрами, а не работа. "
                         "Машина без смещения может работать с места (экскаватор "
                         "копает, кран поворачивает стрелу), поэтому величина "
                         "названа «доля наблюдений без смещения», а не «доля "
                         "простоя». Метод верен только для неподвижной камеры."),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dets", type=Path, help="детекции с полями camera_id и timestamp")
    ap.add_argument("--moved", type=float, default=0.10,
                    help="смещение центра в долях размера рамки, выше — «сместилась»")
    ap.add_argument("--still", type=float, default=0.03, help="ниже — «не сместилась»")
    ap.add_argument("--max-gap", type=int, default=10,
                    help="максимальный разрыв между кадрами, минут")
    ap.add_argument("--out", type=Path, default=ML / "data/processed/activity_series.json")
    args = ap.parse_args()

    data = json.loads(args.dets.read_text(encoding="utf-8"))
    result = analyse(data["images"], args.moved, args.still, args.max_gap)

    for row in result["classes"]:
        share = row.get("still_share")
        if share is None:
            print(f"{row['class']:<20} {row['basis']}")
        else:
            low, high = row["interval"]
            print(f"{row['class']:<20} без смещения {share:.0%} "
                  f"[{low:.0%}..{high:.0%}] по {row['pairs']} парам")
    print(f"\n{result['meta']}")
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"записано: {args.out}")


if __name__ == "__main__":
    main()
