"""календарный план заказчика -> наш формат графика.

Два реальных файла со строек (24.09.2026) показали, в каком виде план приходит:

1. **Excel**: иерархическая нумерация (1, 1.1, 2, 2.1), название этапа, начало,
   окончание. Даты — числа Excel, но часть записана текстом, и среди них
   встречается **«30.02.2027»**: такого дня не существует. Больше десяти строк.
2. **PDF из MS Project**: 111 задач, даты с днём недели («Пн 07.06.19»),
   двузначный год.

Отсюда два требования, которые заранее не выдумаешь: принимать оба формата и
**не падать на некорректных датах**, а помечать строку и продолжать.

Сопоставление названий с нашими этапами — в `configs/stage_mapping.json`. Это
методика, а не константа: заказчик на Q&A (35:39) просил давать её править
через интерфейс (D-009).

    python tools/parse_schedule.py plan.xlsx --site p12 -o data/reference/schedule_p12.csv
"""

import argparse, csv, json, re, sys, zipfile
from datetime import date, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

ML = Path(__file__).resolve().parents[1]
NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
EXCEL_EPOCH = date(1899, 12, 30)          # у Excel собственная эпоха
WEEKDAY = re.compile(r"^(?:Пн|Вт|Ср|Чт|Пт|Сб|Вс)\s+")


def parse_date(value) -> tuple:
    """Дата и пояснение, если разобрать не удалось.

    Возвращает (None, причина) вместо исключения: одна битая строка не должна
    ронять разбор всего плана. В реальном файле таких строк 11 из 67.
    """
    if value is None or str(value).strip() == "":
        return None, "пусто"
    raw = str(value).strip()
    if re.fullmatch(r"\d+(\.\d+)?", raw):                 # число Excel
        try:
            return EXCEL_EPOCH + timedelta(days=int(float(raw))), ""
        except (ValueError, OverflowError):
            return None, "не число Excel: " + raw
    text = WEEKDAY.sub("", raw)                            # «Пн 07.06.19» -> «07.06.19»
    for fmt in ("%d.%m.%Y", "%d.%m.%y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date(), ""
        except ValueError:
            continue
    return None, "некорректная дата: " + raw


def read_xlsx(path: Path) -> list:
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        shared = ["".join(t.text or "" for t in si.iter(NS + "t"))
                  for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(NS + "si")]
    rows = []
    for sheet in sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet")):
        for row in ET.fromstring(z.read(sheet)).iter(NS + "row"):
            cells = {}
            for c in row.iter(NS + "c"):
                col = re.match(r"[A-Z]+", c.get("r")).group()
                v = c.find(NS + "v")
                if v is None:
                    continue
                cells[col] = shared[int(v.text)] if c.get("t") == "s" else v.text
            if cells:
                rows.append(cells)

    # колонки заранее не известны: в выданном файле это C/D/E/F, но полагаться
    # на буквы нельзя — берём самый длинный текст как название, числа как даты
    out = []
    for cells in rows:
        values = [cells[c] for c in sorted(cells)]
        texts = [v for v in values if v and not re.fullmatch(r"[\d.]+", str(v))]
        dates = [v for v in values if re.fullmatch(r"\d{5}(\.\d+)?", str(v))
                 or re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", str(v))]
        name = max(texts, key=len) if texts else ""
        num = next((v for v in values if re.fullmatch(r"\d+(\.\d+)*\.?", str(v))), "")
        if len(name) < 8:                                  # шапка, подписи, пустые строки
            continue
        out.append({"num": str(num), "name": name,
                    "start": dates[0] if dates else "",
                    "end": dates[1] if len(dates) > 1 else ""})
    return out


def read_pdf(path: Path) -> list:
    try:
        import pymupdf
    except ImportError:
        raise SystemExit("для PDF нужен pymupdf: pip install pymupdf")
    text = "\n".join(page.get_text() for page in pymupdf.open(path))
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    is_date = re.compile(r"^(?:Пн|Вт|Ср|Чт|Пт|Сб|Вс)\s+\d{2}\.\d{2}\.\d{2}$")
    out, i = [], 0
    while i < len(lines):
        if lines[i].isdigit():
            num, i = lines[i], i + 1
            name = []
            while i < len(lines) and not is_date.match(lines[i]) and not lines[i].isdigit():
                name.append(lines[i])
                i += 1
            start = lines[i] if i < len(lines) and is_date.match(lines[i]) else ""
            i += 1 if start else 0
            end = lines[i] if i < len(lines) and is_date.match(lines[i]) else ""
            i += 1 if end else 0
            if name:
                out.append({"num": num, "name": " ".join(name), "start": start, "end": end})
        else:
            i += 1
    return out


def load_mapping(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [(re.compile(r["pattern"], re.I), r["stage_code"], r.get("stage_name", ""))
            for r in data["rules"]]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("plan", type=Path, help="xlsx или pdf от заказчика")
    ap.add_argument("--site", required=True, help="идентификатор площадки")
    ap.add_argument("--mapping", type=Path, default=ML / "configs/stage_mapping.json")
    ap.add_argument("-o", "--out", type=Path, default=None)
    ap.add_argument("--keep-unmapped", action="store_true",
                    help="оставить строки без нашего этапа (по умолчанию только считаются)")
    ap.add_argument("--no-merge", action="store_true",
                    help="не сводить повторы одного этапа в один интервал")
    args = ap.parse_args()

    raw = read_xlsx(args.plan) if args.plan.suffix.lower() == ".xlsx" else read_pdf(args.plan)
    mapping = load_mapping(args.mapping)

    out, skipped, bad_dates = [], [], []
    for r in raw:
        start, err1 = parse_date(r["start"])
        end, err2 = parse_date(r["end"])
        if (err1 and r["start"]) or (err2 and r["end"]):
            bad_dates.append((r["name"][:46], err1 or err2))
        code = name = None
        for pattern, stage_code, stage_name in mapping:
            if pattern.search(r["name"]):
                code, name = stage_code, stage_name
                break
        if code is None:
            skipped.append(r["name"][:60])
            if not args.keep_unmapped:
                continue
            code, name = "", r["name"]
        if not start or not end:
            continue                                       # без обеих дат строка бесполезна
        out.append({"site_id": args.site, "stage_code": code,
                    "stage_name": name or r["name"],
                    "planned_start": start.isoformat(), "planned_end": end.isoformat(),
                    "note": "из плана: " + r["num"] + " " + r["name"][:60]})

    # В реальных планах один наш этап встречается несколько раз: каркас идёт
    # отдельной строкой на каждую секцию или этаж. Цепочке нужен один интервал
    # на этап, поэтому сводим к минимальному началу и максимальному окончанию.
    merged = 0
    if not args.no_merge:
        by_code = {}
        for r in out:
            key = (r["site_id"], r["stage_code"])
            if key in by_code:
                prev = by_code[key]
                prev["planned_start"] = min(prev["planned_start"], r["planned_start"])
                prev["planned_end"] = max(prev["planned_end"], r["planned_end"])
                prev["note"] += " | +" + r["note"].split(": ", 1)[-1][:28]
                merged += 1
            else:
                by_code[key] = dict(r)
        out = sorted(by_code.values(), key=lambda r: r["planned_start"])

    print("строк в плане: %d; распознано этапов: %d" % (len(raw), len(out)))
    if merged:
        print("сведено повторов одного этапа: %d (секции и этажи идут отдельными строками)" % merged)
    if bad_dates:
        print("\nстрок с нечитаемыми датами: %d — пропущены, разбор не прерван" % len(bad_dates))
        for name, why in bad_dates[:5]:
            print("   %-48s%s" % (name, why))
    if skipped:
        print("\nбез нашего этапа: %d (внутренние работы, оборудование, сдача)" % len(skipped))
        for name in skipped[:5]:
            print("   " + name)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["site_id", "stage_code", "stage_name",
                                              "planned_start", "planned_end", "note"],
                               delimiter=";")
            w.writeheader()
            w.writerows(out)
        print("\nрезультат: " + str(args.out))
    else:
        for r in out[:12]:
            print("   %-10s%-40s%s .. %s" % (r["stage_code"], r["stage_name"][:38],
                                             r["planned_start"], r["planned_end"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
