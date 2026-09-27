"""чтение впечатанного времени съёмки с кадров уличных камер.

Архив с камер пришёл без пригодных метаданных: EXIF пустой, а в именах файлов
стоит момент выгрузки с диска, а не момент съёмки. Настоящее время есть только
одним местом — оно впечатано в кадр слева сверху как `03-08-2026 08:00:02`.

Без него архив бесполезен для всей цепочки: и свод по паре «площадка и дата», и
сравнение соседних кадров держатся на времени съёмки.

**Почему не OCR.** Готовый распознаватель текста на этих кадрах даёт 4–5 секунд
на кадр и путается, когда штамп ложится на провода или металлоконструкции. Но
это не произвольный текст: знакогенератор камеры рисует моноширинный шрифт
всегда в одном месте и одного размера. Поэтому мы режем строку на 14 ячеек по
известной сетке и сравниваем каждую с эталоном знака. Это быстрее OCR на три
порядка и не зависит от того, что попало на фон.

Признак для сравнения — не яркость, а морфологический градиент: знак обведён
тёмным контуром и залит светлым, так что по контуру он виден и на небе, и на
тёмной крыше.

**Эталоны знаков строятся из самих кадров** (`--learn`): берутся кадры, для
которых время известно, и из них нарезаются образцы каждой цифры. Разметка
лежит в `configs/stamp_samples.json`, править её может человек.

Кадр, который не прочитался уверенно, **остаётся без времени**. Кадры идут почти
ровно через полчаса, и достроить пропуск арифметикой заманчиво, но нельзя:
именно фактическое время съёмки — то, ради чего архив и нужен.

    python tools/read_camera_stamps.py --learn        # построить эталоны знаков
    python tools/read_camera_stamps.py                # прочитать весь архив
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ML = Path(__file__).resolve().parents[1]
SAMPLES = ML / "configs" / "stamp_samples.json"
TEMPLATES = ML / "configs" / "stamp_templates.npz"

# Окно, в которое обязана попасть дата съёмки: отсекает мусор вроде «13-08-2062».
YEAR_MIN, YEAR_MAX = 2020, 2030

# Сетка знакогенератора для кадров 2592x1944, в координатах вырезанной полосы.
# Измерена по накопленной маске на трёх камерах независимо — совпала до пикселя.
GEOMETRY = {
    (2592, 1944): {
        "band": (56, 96),
        "x": [17, 45, 89, 117, 161, 189, 217, 245, 291, 317, 361, 389, 433, 461],
        "w": 26,
    },
    # Кадры 1920x1080 снимает другая модель камеры: шрифт тот же, но мельче
    # (масштаб 0.68 от крупного). Сетку пришлось подбирать по размеченным
    # кадрам, а не по совпадению с эталонами: эталоны крупной камеры на мелкий
    # шрифт не ложатся, и подбор по ним садился в ложный минимум — знаки
    # «узнавались» на сдвинутой сетке. Критерий подбора — доля верно
    # распознанных знаков на кадрах с известным временем: 248 из 280.
    (1920, 1080): {
        "band": (35, 62),
        "x": [6, 25, 55, 74, 104, 123, 142, 161, 192, 210, 240, 259, 289, 308],
        "w": 18,
    },
}

GEOMETRY_KEYS = {f"{w}x{h}" for w, h in GEOMETRY}

CELL = (24, 34)          # к чему приводим ячейку перед сравнением
MIN_SCORE = 0.30         # ниже — знак не опознан
MIN_MARGIN = 0.03        # отрыв от второго кандидата


def imread(path: Path, gray: bool = True) -> np.ndarray | None:
    """cv2.imread не открывает пути с кириллицей — читаем через буфер."""
    data = np.fromfile(str(path), dtype=np.uint8)
    if not data.size:
        return None
    flag = cv2.IMREAD_GRAYSCALE if gray else cv2.IMREAD_COLOR
    return cv2.imdecode(data, flag)


def stamp_area(frame: np.ndarray) -> np.ndarray:
    """Левый верхний угол в относительных долях: штамп всегда там."""
    h, w = frame.shape[:2]
    return frame[int(0.014 * h):int(0.075 * h), int(0.008 * w):int(0.270 * w)]


def ink(area: np.ndarray) -> np.ndarray:
    """Контур знака. Не зависит от того, светлый под ним фон или тёмный."""
    grad = cv2.morphologyEx(area, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8))
    return (grad > 55).astype(np.float32)


def cells(frame: np.ndarray, jitter: int = 3) -> list[list[np.ndarray]] | None:
    """Для каждой из 14 позиций — несколько вариантов выреза со сдвигом.

    Сетка измерена по накопленной маске и может быть на пиксель-другой неточна:
    знакогенератор у разных прошивок сдвинут чуть по-разному. Вместо подгонки
    координат под конкретную камеру пробуем небольшой сдвиг и берём тот, при
    котором знак опознаётся увереннее. Так один и тот же код работает и там, где
    сетка идеальна, и там, где она сдвинута.
    """
    key = (frame.shape[1], frame.shape[0])
    geom = GEOMETRY.get(key)
    if geom is None:
        return None
    strip = ink(stamp_area(frame))
    y1, y2 = geom["band"]
    if y2 > strip.shape[0]:
        return None
    width = geom["w"]
    out = []
    for x in geom["x"]:
        options = []
        for dx in range(-jitter, jitter + 1):
            left = x + dx
            if left < 0 or left + width > strip.shape[1]:
                continue
            options.append(cv2.resize(strip[y1:y2, left:left + width], CELL,
                                      interpolation=cv2.INTER_AREA))
        if not options:
            return None
        out.append(options)
    return out


def score(cell: np.ndarray, template: np.ndarray) -> float:
    """Нормированная корреляция: устойчива к тому, сколько всего попало в ячейку."""
    a = cell - cell.mean()
    b = template - template.mean()
    denom = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / denom) if denom > 1e-6 else 0.0


def size_key(frame: np.ndarray) -> str:
    return f"{frame.shape[1]}x{frame.shape[0]}"


def learn(cameras: Path) -> dict[str, dict[str, np.ndarray]]:
    """Эталоны знаков из кадров с известным временем, отдельно по разрешениям.

    Общий набор эталонов на оба разрешения не годится: знак 21 пикселя шириной,
    растянутый до размера знака в 26 пикселей, теряет детали, и совпадение
    падает вдвое. Проверено — на кадрах 1920x1080 общие эталоны давали 0 из 40.
    """
    marks = json.loads(SAMPLES.read_text(encoding="utf-8"))
    buckets: dict[str, dict[str, list[np.ndarray]]] = {}
    used: dict[str, int] = {}
    for item in marks["samples"]:
        files = sorted((cameras / item["camera"]).glob("*.jpg"))
        if item["index"] >= len(files):
            continue
        frame = imread(files[item["index"]])
        got = cells(frame, jitter=0) if frame is not None else None
        digits = item["value"]
        if got is None or len(digits) != len(got):
            continue
        key = size_key(frame)
        used[key] = used.get(key, 0) + 1
        for options, digit in zip(got, digits):
            buckets.setdefault(key, {}).setdefault(digit, []).append(options[0])

    flat, report = {}, []
    for key, digits in sorted(buckets.items()):
        missing = sorted(set("0123456789") - set(digits))
        report.append(f"  {key}: по {used[key]} кадрам, знаков {len(digits)}"
                      + (f"; НЕ ХВАТАЕТ {missing}" if missing else ""))
        for digit, samples in digits.items():
            flat[f"{key}|{digit}"] = np.mean(samples, axis=0)
    print("эталоны построены:")
    print("\n".join(report) or "  ничего не собрано")
    np.savez(TEMPLATES, **flat)
    print(f"сохранено: {TEMPLATES}")
    return load_templates()


def load_templates() -> dict[str, dict[str, np.ndarray]]:
    if not TEMPLATES.exists():
        raise SystemExit(f"нет эталонов {TEMPLATES}: запустите с --learn")
    data = np.load(TEMPLATES)
    out: dict[str, dict[str, np.ndarray]] = {}
    for name in data.files:
        key, digit = name.split("|")
        out.setdefault(key, {})[digit] = data[name]
    return out


def read_stamp(frame: np.ndarray,
               templates: dict[str, dict[str, np.ndarray]]) -> tuple[datetime | None, str]:
    """Время съёмки и пояснение, если прочитать не удалось."""
    key = size_key(frame)
    if key not in GEOMETRY_KEYS:
        return None, f"нет сетки для {key}"
    if key not in templates:
        return None, f"нет эталонов для {key}"
    marks = templates[key]
    got = cells(frame)
    if got is None:
        return None, f"не удалось нарезать строку ({key})"
    digits = ""
    for options in got:
        # Лучшая пара «сдвиг + знак». Второй кандидат берётся среди ДРУГИХ
        # знаков, а не других сдвигов того же знака: иначе отрыв всегда нулевой.
        by_digit = {d: max(score(cell, t) for cell in options)
                    for d, t in marks.items()}
        ranked = sorted(((v, d) for d, v in by_digit.items()), reverse=True)
        best, second = ranked[0], ranked[1]
        if best[0] < MIN_SCORE or best[0] - second[0] < MIN_MARGIN:
            return None, f"знак не опознан (совпадение {best[0]:.2f})"
        digits += best[1]
    try:
        value = datetime.strptime(digits, "%d%m%Y%H%M%S")
    except ValueError:
        return None, f"нереальная дата «{digits}»"
    if not YEAR_MIN <= value.year <= YEAR_MAX:
        return None, f"год вне окна: {value.year}"
    return value, ""


def consistency(rows: list[dict]) -> None:
    """Самопроверка прочитанного: сколько кадров выбивается из ритма съёмки.

    Проверять чтение нечем — эталонного ответа у нас нет. Но камера снимает с
    постоянным шагом, и этого достаточно: если время прочитано неверно, кадр
    почти наверняка не ляжет на общий ритм. Шаг берём из самих данных
    (медиана интервалов), ничего не предполагая заранее.

    Доля выбившихся — **верхняя оценка доли ошибок**, а не точная цифра: часть
    отклонений может быть настоящей (камера иногда пишет два кадра подряд).
    Зато она считается на всех данных, а не на двадцати размеченных кадрах.
    """
    from statistics import median

    by_camera: dict[str, list[datetime]] = {}
    for row in rows:
        by_camera.setdefault(row["camera"], []).append(
            datetime.fromisoformat(row["timestamp"]))

    print("\nсогласованность с ритмом съёмки (верхняя оценка доли ошибок):")
    total_off = 0
    for camera, stamps in sorted(by_camera.items()):
        stamps.sort()
        gaps = [(b - a).total_seconds() / 60 for a, b in zip(stamps, stamps[1:])]
        step = median([g for g in gaps if g > 1] or [0])
        if not step:
            continue
        # Кадр «на ритме», если его минута близка к узлу сетки с этим шагом.
        off = [t for t in stamps
               if min((t.minute * 60 + t.second) % (step * 60),
                      step * 60 - (t.minute * 60 + t.second) % (step * 60)) > 180]
        total_off += len(off)
        print(f"  {camera}: шаг {step:.0f} мин, вне ритма {len(off)} из {len(stamps)}"
              f" ({len(off) / len(stamps):.1%})")
    print(f"  всего вне ритма: {total_off} из {len(rows)}"
          f" ({total_off / max(1, len(rows)):.1%})")


class OcrFallback:
    """Медленный, но независимый способ прочитать штамп — готовым OCR.

    Нужен там, где сопоставление с эталонами не справляется. На кадрах
    1920x1080 знак мельче, фон плотнее, и по отдельным знакам мы угадываем 89% —
    звучит прилично, но строка из 14 знаков целиком верна почти никогда. Замер
    на размеченных кадрах: **ни одного** полностью верного чтения ни при каком
    пороге. Там, где быстрый способ не работает, честнее заплатить секундами.

    Цена: 4–5 секунд на кадр против 9 миллисекунд у эталонов. Поэтому OCR
    включается только как запасной путь и только для отказавших кадров.
    """

    def __init__(self) -> None:
        from rapidocr_onnxruntime import RapidOCR
        self._ocr = RapidOCR()

    def __call__(self, frame: np.ndarray) -> tuple[datetime | None, str]:
        import re
        area = stamp_area(frame)
        for k in (2, 3):
            big = cv2.resize(area, (area.shape[1] * k, area.shape[0] * k),
                             interpolation=cv2.INTER_CUBIC)
            result, _ = self._ocr(big)
            if not result:
                continue
            ordered = sorted(result, key=lambda box: box[0][0][0])
            digits = re.sub(r"\D", "", "".join(part[1] for part in ordered))
            if len(digits) != 14:
                continue
            try:
                value = datetime.strptime(digits, "%d%m%Y%H%M%S")
            except ValueError:
                continue
            if YEAR_MIN <= value.year <= YEAR_MAX:
                return value, ""
        return None, "OCR не дал разбираемой строки"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cameras", type=Path, default=ML / "data/raw/cameras")
    ap.add_argument("-o", "--out", type=Path, default=ML / "data/processed/camera_stamps.csv")
    ap.add_argument("--learn", action="store_true", help="построить эталоны знаков и выйти")
    ap.add_argument("--limit", type=int, default=0, help="сколько кадров на камеру (0 — все)")
    ap.add_argument("--only", nargs="*", metavar="КАМЕРА",
                    help="обработать только эти подпапки")
    ap.add_argument("--ocr-fallback", action="store_true",
                    help="для кадров, где эталоны не справились, пробовать OCR (медленно)")
    args = ap.parse_args()

    if args.learn:
        learn(args.cameras)
        return 0

    templates = load_templates()
    fallback = OcrFallback() if args.ocr_fallback else None
    rows, unread, by_ocr = [], [], 0
    wanted = set(args.only or [])
    for folder in sorted(p for p in args.cameras.iterdir() if p.is_dir()):
        if wanted and folder.name not in wanted:
            continue
        files = sorted(folder.glob("*.jpg"))
        if args.limit:
            files = files[:args.limit]
        read = 0
        for path in files:
            frame = imread(path)
            if frame is None:
                unread.append((folder.name, path.name, "файл не читается"))
                continue
            value, why = read_stamp(frame, templates)
            if value is None and fallback is not None:
                value, why_ocr = fallback(frame)
                if value is not None:
                    by_ocr += 1
                else:
                    why = f"{why}; {why_ocr}"
            if value is None:
                unread.append((folder.name, path.name, why))
                continue
            read += 1
            rows.append({"camera": folder.name, "file": path.name,
                         "timestamp": value.isoformat(sep=" "),
                         "date": value.date().isoformat(),
                         "width": frame.shape[1], "height": frame.shape[0]})
        total = len(files)
        print(f"{folder.name}: прочитано {read} из {total} "
              f"({read / total:.0%})" if total else f"{folder.name}: пусто", flush=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["camera", "file", "timestamp", "date",
                                               "width", "height"], delimiter=";")
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["camera"], r["timestamp"])))

    if unread:
        bad = args.out.with_name(args.out.stem + "_unread.csv")
        with open(bad, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f, delimiter=";")
            w.writerow(["camera", "file", "reason"])
            w.writerows(unread)
        print(f"\nбез времени: {len(unread)} кадр(ов) — список в {bad.name}")
        print("Время им не присваивается: достраивать его арифметикой нельзя.")

    if by_ocr:
        print(f"из них прочитано запасным путём (OCR): {by_ocr}")
    consistency(rows)
    print(f"\nрезультат: {args.out} ({len(rows)} строк)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
