# -*- coding: utf-8 -*-
"""Парсер справочника видов работ («Сводный перечень строительных работ_ЛТЦ.xlsx»).

Справочник — источник плановой части системы: из него строится WBS, к которой
затем привязываются даты календарного графика и правила «этап → техника».

Две особенности исходного файла, ради которых написан отдельный парсер:

1. Колонка «№ п/п» частично испорчена автоформатированием Excel. Номера вида
   «10.1.» распознаны как даты и хранятся числовыми серийными значениями
   (45667 → 10.01.2025 → исходное «10.1.»). Пострадали только подразделы 1–12:
   «10.13.» уцелело, потому что месяца 13 не существует и Excel оставил текст.
   Это же свойство служит проверкой гипотезы восстановления.

2. Уровень вложенности не закодирован ни отступом, ни группировкой строк —
   только форматированием (жирность + заливка). Поэтому уровень считается по
   номеру, а стили используются как независимая перекрёстная проверка.

Зависимостей нет: xlsx читается как zip + XML средствами стандартной библиотеки.
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

# Колонки C..K — матрица применимости вида работ к типу объекта.
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

# Стиль ячейки колонки A (индекс в cellXfs) → уровень WBS. Из xl/styles.xml:
# 14 — жирный 14pt на заливке D9D9D9, 17 — жирный на F2F2F2.
#
# Однозначно кодируются только уровни 1–2: глубже форматирование переиспользовано
# и уровню не соответствует (стиль 25 поровну делится между уровнями 3 и 4).
# Поэтому проверка по стилям намеренно ограничена разделами и подразделами.
STYLE_LEVEL = {"14": 1, "17": 2}

EXCEL_EPOCH = dt.date(1899, 12, 30)  # серийная дата 1 == 1900-01-01


@dataclass
class Work:
    row: int                     # номер строки в исходном xlsx — для трассировки
    code: str                    # канонический номер, напр. "10.11.1"
    raw_code: str                # то, что реально лежало в ячейке
    repaired: bool               # был ли номер восстановлен из серийной даты
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
    """Схлопывает переносы строк и двойные пробелы внутри наименований работ."""
    return re.sub(r"\s+", " ", text).strip()


def repair_code(raw: str, current_section: str | None) -> tuple[str, bool]:
    """Восстанавливает номер, съеденный автоформатированием Excel.

    Серийное число трактуется как дата: день — номер раздела, месяц — номер
    подраздела. Восстановление принимается только если день совпал с разделом,
    в котором строка физически находится, иначе номер остаётся сырым и строка
    попадёт в отчёт о расхождениях.
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
    style_levels: list[tuple[int, int]] = []   # (уровень по номеру, уровень по стилю)
    section: str | None = None
    # Последняя пронумерованная работа каждого уровня — чтобы подвесить к ней
    # детализирующие строки без номера.
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

        # Раздел верхнего уровня («10.», «12.») переключает контекст для repair_code.
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

    # Проверка 1: совпадает ли уровень, посчитанный по восстановленному номеру,
    # с уровнем, заложенным в форматирование ячейки (только разделы/подразделы).
    agree = sum(1 for by_code, by_style in style_levels if by_code == by_style)
    for by_code, by_style in style_levels:
        if by_code != by_style:
            issues.append(f"уровень по номеру {by_code} ≠ уровню по стилю {by_style}")

    # Проверка 2: каждая ссылка parent указывает на существующий номер работы.
    # Это ловит и ошибки восстановления номеров, и разрывы в иерархии.
    known = {w.code for w in works}
    for w in works:
        if w.parent and w.parent not in known:
            issues.append(f"строка {w.row}: родитель {w.parent!r} не найден ({w.name[:40]}…)")

    stats = {
        "rows": len(works),
        "repaired_codes": sum(w.repaired for w in works),
        "unnumbered": sum(1 for w in works if "#" in w.code),
        "levels": dict(sorted(Counter(w.level for w in works).items())),
        "by_object_type": {t: sum(1 for w in works if t in w.object_types)
                           for t in OBJECT_TYPES.values()},
        "style_crosscheck_lvl1_2": f"{agree}/{len(style_levels)} совпало",
        "orphan_parents": sum(1 for w in works if w.parent and w.parent not in {x.code for x in works}),
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
