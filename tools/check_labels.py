# -*- coding: utf-8 -*-
"""Проверка разметки: классы из словаря, атрибут активности, вырожденные рамки.

Опечатка в имени класса не ломает ничего сразу: файл читается, обучение идёт, а
класс `truck_unkniwn` тихо живёт отдельной сущностью с одним примером. Находится
такое обычно на этапе, когда переразмечать поздно. Поэтому словарь классов
фиксирован в LABELING_SPEC.md, а всё, чего в нём нет, — ошибка.

Атрибут активности проверяется отдельно: по D-007 «работает / простаивает» —
обязательная функция, и пустое поле здесь не то же самое, что `unknown`.
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

CLASSES = {
    "excavator_crawler", "excavator_wheeled", "backhoe_loader", "excavator_unknown",
    "tower_crane", "truck_crane", "crawler_crane", "loader_crane", "crane_unknown",
    "drilling_rig", "pile_driver", "dwall_rig", "drilling_unknown",
    "dump_truck", "concrete_mixer", "concrete_pump", "flatbed_truck", "truck_unknown",
    "bulldozer", "roller", "grader", "paver",
    "wheel_loader", "telehandler",
    # coarse-классы: ставятся, когда точный тип не различим
    "excavator_like", "crane_like", "drilling_like", "truck_like",
    "earthmoving", "loader_like",
}
ATTRIBUTES = {
    # ключ: допустимые значения. Описание рамки — это список пар key=value
    # через «;»: activity=idle;offsite=true
    "activity": {"working", "idle", "unknown"},
    "offsite": {"true", "false"},
}
MIN_SIDE_PX = 8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path, help="папка с json разметки")
    parser.add_argument("--strict-activity", action="store_true",
                        help="считать пустой атрибут активности ошибкой, а не предупреждением")
    args = parser.parse_args()

    files = sorted(args.folder.glob("*.json"))
    if not files:
        print(f"в {args.folder} нет json-файлов", file=sys.stderr)
        return 1

    cls_counter, act_counter = collections.Counter(), collections.Counter()
    errors, warnings = [], []
    total = 0

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        for i, shape in enumerate(data.get("shapes", []), start=1):
            total += 1
            label = shape.get("label", "")
            cls_counter[label] += 1

            if label not in CLASSES:
                near = [c for c in CLASSES if c[:5] == label[:5]]
                hint = f" — возможно, {near[0]}" if near else ""
                errors.append(f"{path.name} рамка {i}: класс «{label}» не из словаря{hint}")

            desc = (shape.get("description") or "").strip()
            act_counter[desc or "(пусто)"] += 1
            if desc:
                for part in desc.split(";"):
                    part = part.strip()
                    if not part:
                        continue
                    key, _, value = part.partition("=")
                    key, value = key.strip(), value.strip()
                    if key not in ATTRIBUTES:
                        errors.append(f"{path.name} рамка {i}: неизвестный атрибут «{key}» в «{desc}»")
                    elif value not in ATTRIBUTES[key]:
                        errors.append(f"{path.name} рамка {i}: у «{key}» значение «{value}» вне списка "
                                      f"{sorted(ATTRIBUTES[key])}")
            if not desc:
                (errors if args.strict_activity else warnings).append(
                    f"{path.name} рамка {i}: не заполнен атрибут активности")

            points = shape.get("points", [])
            if len(points) == 2:
                (x1, y1), (x2, y2) = points
                if abs(x2 - x1) < MIN_SIDE_PX or abs(y2 - y1) < MIN_SIDE_PX:
                    warnings.append(f"{path.name} рамка {i}: вырожденная рамка "
                                    f"{abs(x2-x1):.0f}x{abs(y2-y1):.0f} px")

    print(f"файлов: {len(files)}, рамок: {total}\n")
    print("классы:")
    for label, n in cls_counter.most_common():
        mark = "  " if label in CLASSES else "!!"
        print(f" {mark} {n:4d}  {label}")
    print("\nактивность:")
    for value, n in act_counter.most_common():
        print(f"    {n:4d}  {value}")

    if errors:
        print(f"\nошибки ({len(errors)}):")
        for e in errors[:20]:
            print(f"  {e}")
        if len(errors) > 20:
            print(f"  ... ещё {len(errors) - 20}")
    if warnings:
        print(f"\nпредупреждения ({len(warnings)}): показаны первые 5")
        for w in warnings[:5]:
            print(f"  {w}")

    if not errors:
        print("\nошибок нет")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
