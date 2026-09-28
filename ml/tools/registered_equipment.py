"""неподвижная техника, зарегистрированная оператором при настройке камеры.

Башенный кран стоит на одной точке неделями. Заставлять детектор узнавать его
заново на каждом кадре раз в пять минут — неверная постановка задачи, и на наших
камерах она провалилась: **0 распознанных из 13 наблюдаемых** (E26). Причина не
в модели — камера стоит низко и близко, мачта уходит за верхний край, и кран
выглядит горизонтальной полосой у границы кадра.

В эксплуатации такое решается не дообучением, а настройкой: при установке камеры
оператор один раз отмечает неподвижную технику и её зону. Реестр —
`configs/stationary_equipment.json`, обычные данные, правятся без участия
разработчика (та же логика, что у `configs/rules.json`, решение D-009).

**Главное правило этого модуля.** Зарегистрированная машина — это *утверждение
оператора*, а не наблюдение системы. Поэтому:

- у такой записи `source: "registered"`, у распознанной — `source: "detected"`;
- `conf` не выставляется в 1.0 и вообще не выдумывается: уверенности у
  утверждения нет, есть ответственность того, кто его внёс;
- дальше по цепочке источник виден в основании статуса и в оговорке отчёта.

Смешать эти два источника и промолчать значило бы выдать ручной ввод за
компьютерное зрение. Именно этого мы не делаем нигде в проекте.

**Период обязателен.** Кран монтируют и демонтируют; запись без границ
утверждала бы его присутствие вечно.

    python tools/registered_equipment.py --check          # сверить реестр с детекциями
    python tools/registered_equipment.py --apply dets.json -o dets_with_registered.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path

ML = Path(__file__).resolve().parents[1]
REGISTRY = ML / "configs" / "stationary_equipment.json"


def load_registry(path: Path = REGISTRY) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    for item in data.get("entries", []):
        entry = dict(item)
        entry["_from"] = datetime.strptime(item["from"], "%Y-%m-%d").date()
        entry["_to"] = datetime.strptime(item["to"], "%Y-%m-%d").date()
        if entry["_to"] < entry["_from"]:
            raise SystemExit(f"в реестре период задом наперёд: {item}")
        out.append(entry)
    return out


def active(registry: list[dict], camera_id: str, day: date) -> list[dict]:
    """Записи, действующие для этой камеры на эту дату."""
    return [e for e in registry
            if e["camera_id"] == camera_id and e["_from"] <= day <= e["_to"]]


def as_detections(entry: dict) -> list[dict]:
    """Запись реестра → записи в формате контракта §1, помеченные источником.

    По одной записи на зону: две машины — две зоны. Одна зона на двоих
    схлопнулась бы при дедупликации в `site_state.py`, и вторая машина
    потерялась бы молча.
    """
    return [{"class_raw": entry["class_ours"], "class_ours": entry["class_ours"],
             "bbox": list(zone), "source": "registered",
             "registered_by": entry.get("registered_by", ""),
             "note": entry.get("note", "")}
            for zone in entry["zones"]]


def apply(images: list[dict], registry: list[dict]) -> tuple[list[dict], Counter]:
    """Добавляет зарегистрированную технику в кадры. Ничего не удаляет.

    Если система сама распознала машину того же класса, запись реестра всё равно
    добавляется — а схлопывание дублей в `site_state.py` сведёт их по зоне.
    Так число не удваивается, но и наблюдение не подменяется утверждением.
    """
    added: Counter = Counter()
    out = []
    for im in images:
        day = im.get("date") or str(im.get("timestamp", ""))[:10]
        extra: list[dict] = []
        if day:
            try:
                parsed = datetime.strptime(day, "%Y-%m-%d").date()
            except ValueError:
                parsed = None
            if parsed is not None:
                for entry in active(registry, im.get("camera_id", ""), parsed):
                    extra.extend(as_detections(entry))
                    added[entry["class_ours"]] += len(entry["zones"])
        marked = [dict(d, source=d.get("source", "detected")) for d in im.get("detections", [])]
        out.append({**im, "detections": marked + extra})
    return out, added


def check(images: list[dict], registry: list[dict]) -> None:
    """Сверка реестра с тем, что система видит сама.

    Полезна дважды: показывает, что регистрация действительно закрывает дыру, и
    ловит устаревшую запись — если система вдруг перестала видеть там технику,
    которую и сама раньше находила, возможно, её увезли раньше срока.
    """
    print(f"{'камера':<14}{'класс':<16}{'кадров':>8}{'сама нашла':>12}{'доля':>8}")
    for entry in registry:
        cam, cls = entry["camera_id"], entry["class_ours"]
        frames = [im for im in images
                  if im.get("camera_id") == cam
                  and entry["from"] <= (im.get("date") or "") <= entry["to"]]
        seen = sum(1 for im in frames
                   if any(d["class_ours"] == cls and d.get("conf", 1) >= 0.25
                          and d.get("source", "detected") == "detected"
                          for d in im.get("detections", [])))
        share = seen / len(frames) if frames else 0
        print(f"{cam:<14}{cls:<16}{len(frames):>8}{seen:>12}{share:>7.0%}")
    print("\nМалая доля — норма: ради этого реестр и нужен. Доля около 100% —")
    print("повод запись убрать: система справляется сама, и дублировать незачем.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", type=Path, default=REGISTRY)
    ap.add_argument("--check", type=Path, nargs="?", const=ML / "data/processed/detections_cameras.json",
                    help="сверить реестр с детекциями")
    ap.add_argument("--apply", type=Path, help="детекции, в которые добавить реестр")
    ap.add_argument("-o", "--out", type=Path)
    args = ap.parse_args()

    registry = load_registry(args.registry)
    print(f"записей в реестре: {len(registry)}")

    if args.check:
        data = json.loads(args.check.read_text(encoding="utf-8"))
        check(data["images"], registry)
        return 0

    if args.apply:
        data = json.loads(args.apply.read_text(encoding="utf-8"))
        images, added = apply(data["images"], registry)
        out = args.out or args.apply.with_name(args.apply.stem + "_registered.json")
        meta = dict(data.get("meta", {}))
        meta["registered_added"] = dict(added)
        meta["registry"] = args.registry.name
        out.write_text(json.dumps({"meta": meta, "images": images}, ensure_ascii=False),
                       encoding="utf-8")
        print("добавлено из реестра:", ", ".join(f"{k} {v}" for k, v in added.items()) or "ничего")
        print(f"результат: {out}")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
