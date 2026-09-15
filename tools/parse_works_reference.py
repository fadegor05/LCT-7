# -*- coding: utf-8 -*-
"""Разбор справочника видов работ в плоский список работ с иерархией.

Читает xlsx как zip + XML, без внешних зависимостей. Восстанавливает номера,
испорченные автоформатированием Excel, и достраивает уровни вложенности.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
Q = "{%s}" % NS
NSMAP = {"m": NS}

OBJECT_TYPES = {
    "C": "Жильё",
    "D": "Образование",
    "E": "Здравоохранение",
    "F": "Спорт",
    "G": "Культура",
    "H": "Административные здания",
    "I": "ДОУ",
    "J": "Офисно-деловой центр",
    "K": "Дороги",
}

# Стиль ячейки колонки A → уровень WBS. Глубже второго уровня форматирование
# переиспользовано и уровню не соответствует, поэтому сверка ограничена
# разделами и подразделами.
STYLE_LEVEL = {"14": 1, "17": 2}

EXCEL_EPOCH = dt.date(1899, 12, 30)


@dataclass
class Work:
    row: int
    code: str
    raw_code: str
    repaired: bool
    level: int
    name: str
    parent: str | None
    object_types: list[str] = field(default_factory=list)


def _cell_col(ref: str) -> str:
    return "".join(ch for ch in ref if ch.isalpha())


def _load_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(Q + "t")) for si in root.findall("m:si", NSMAP)]


def _cell_text(cell: ET.Element, shared: list[str]) -> str:
    v = cell.find("m:v", NSMAP)
    if v is None or v.text is None:
        return ""
    return shared[int(v.text)] if cell.get("t") == "s" else v.text


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def repair_code(raw: str, current_section: str | None) -> tuple[str, bool]:
    """Восстанавливает номер, распознанный Excel как дата.

    Номера вида «10.1.» сохранены серийными числами: 45667 → 10.01.2025 → «10.1».
    День трактуется как раздел, месяц как подраздел. Восстановление принимается
    только если день совпал с разделом, в котором строка физически лежит.
    """
    raw = raw.strip()
    if not re.fullmatch(r"\d{5}", raw):
        return raw.rstrip("."), False

    date = EXCEL_EPOCH + dt.timedelta(days=int(raw))
    if current_section is not None and str(date.day) != current_section:
        return raw, False
    return f"{date.day}.{date.month}", True


def parse(xlsx: Path) -> tuple[list[Work], dict]:
    with zipfile.ZipFile(xlsx) as zf:
        shared = _load_shared_strings(zf)
        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))

    works: list[Work] = []
    issues: list[str] = []
    style_levels: list[tuple[int, int]] = []
    section: str | None = None
    last_by_level: dict[int, Work] = {}

    for row in sheet.findall(".//m:row", NSMAP):
        cells = {_cell_col(c.get("r")): c for c in row.findall("m:c", NSMAP)}
        name_cell = cells.get("B")
        if name_cell is None:
            continue
        name = _normalize(_cell_text(name_cell, shared))
        if not name or name == "Вид работ":
            continue

        row_no = int(row.get("r"))
        code_cell = cells.get("A")
        raw_code = _cell_text(code_cell, shared).strip() if code_cell is not None else ""

        if re.fullmatch(r"\d{1,2}\.?", raw_code):
            section = raw_code.rstrip(".")

        code, repaired = repair_code(raw_code, section)
        unresolved = bool(re.fullmatch(r"\d{5}", code))
        if unresolved:
            issues.append(f"строка {row_no}: номер {raw_code!r} не восстановлен ({name[:40]}…)")

        if code and not unresolved:
            level = code.count(".") + 1
            parent = code.rsplit(".", 1)[0] if "." in code else None
        else:
            # Строка без номера — детализация последней пронумерованной работы.
            anchor = max(last_by_level) if last_by_level else 0
            level = anchor + 1
            parent = last_by_level[anchor].code if anchor else None
            code = f"{parent}.#{row_no}" if parent else f"#{row_no}"

        style_id = code_cell.get("s") if code_cell is not None else None
        if style_id in STYLE_LEVEL:
            style_levels.append((level, STYLE_LEVEL[style_id]))

        work = Work(
            row=row_no,
            code=code,
            raw_code=raw_code,
            repaired=repaired,
            level=level,
            name=name,
            parent=parent,
            object_types=[name_ru for col, name_ru in OBJECT_TYPES.items()
                          if col in cells and _cell_text(cells[col], shared).strip()],
        )
        works.append(work)

        if "#" not in work.code:
            last_by_level[level] = work
            for deeper in [lvl for lvl in last_by_level if lvl > level]:
                del last_by_level[deeper]

    agree = sum(1 for by_code, by_style in style_levels if by_code == by_style)
    for by_code, by_style in style_levels:
        if by_code != by_style:
            issues.append(f"уровень по номеру {by_code} ≠ уровню по стилю {by_style}")

    known = {w.code for w in works}
    orphans = [w for w in works if w.parent and w.parent not in known]
    for w in orphans:
        issues.append(f"строка {w.row}: родитель {w.parent!r} не найден ({w.name[:40]}…)")

    stats = {
        "rows": len(works),
        "repaired_codes": sum(w.repaired for w in works),
        "unnumbered": sum(1 for w in works if "#" in w.code),
        "levels": dict(sorted(Counter(w.level for w in works).items())),
        "by_object_type": {t: sum(1 for w in works if t in w.object_types)
                           for t in OBJECT_TYPES.values()},
        "style_crosscheck_lvl1_2": f"{agree}/{len(style_levels)} совпало",
        "orphan_parents": len(orphans),
        "issues": issues,
    }
    return works, stats


def main() -> int:
    ap = argparse.ArgumentParser(description="Парсинг справочника видов работ в JSON/CSV")
    ap.add_argument("xlsx", type=Path)
    ap.add_argument("-o", "--out", type=Path, default=Path("data/processed"))
    args = ap.parse_args()

    works, stats = parse(args.xlsx)
    args.out.mkdir(parents=True, exist_ok=True)

    (args.out / "works_reference.json").write_text(
        json.dumps([asdict(w) for w in works], ensure_ascii=False, indent=2), encoding="utf-8")

    with (args.out / "works_reference.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["row", "code", "level", "parent", "name", "object_types"])
        for w in works:
            writer.writerow([w.row, w.code, w.level, w.parent or "", w.name, "|".join(w.object_types)])

    json.dump(stats, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
