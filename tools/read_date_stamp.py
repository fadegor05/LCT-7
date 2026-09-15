# -*- coding: utf-8 -*-
"""Распознавание даты, впечатанной в снимок строительной площадки.

Зачем: без даты снимок невозможно сопоставить с календарным графиком. EXIF в
выданном датасете отсутствует (PNG несёт только dpi/gamma/srgb), а дата вплавлена
в правый нижний угол кадра фотофиксацией камеры. Это единственный источник
временной привязки.

Сложность в том, что штамп встречается минимум в трёх начертаниях (тонкий
красный, жирный оранжевый, белый) и лежит поверх произвольного фона — неба,
снега, оранжевого грунта. Один порог бинаризации на все случаи не работает.

Подход — многогипотезность с жёсткой проверкой результата:

1. Снимок обрезается до правого нижнего угла и увеличивается — штамп мелкий.
2. Строится несколько вариантов предобработки (оригинал и маски под каждое
   начертание). Каждый прогоняется через OCR независимо.
3. Фрагменты одной строки склеиваются по вертикальной близости: жирный штамп
   часто распознаётся кусками («21.» + «.01:2024»).
4. Результат нормализуется (типовые путаницы OCR: ':' вместо '.', 'O' вместо
   '0') и проверяется на соответствие ДД.ММ.ГГГГ и на календарную валидность.
5. Побеждает вариант с наибольшей уверенностью; при разногласии между
   вариантами берётся дата, набравшая больше голосов.

Структура ДД.ММ.ГГГГ и проверка даты работают как фильтр ложных срабатываний:
текст, не складывающийся в реальную дату, отбрасывается целиком. Поэтому лучше
вернуть None с причиной, чем правдоподобное, но выдуманное число — снимок без
даты честнее показать оператору для ручной привязки.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, asdict
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

# Штамп всегда в правом нижнем углу; берём с запасом.
ROI_TOP, ROI_LEFT = 0.84, 0.38
UPSCALE = 2

# Год вне этого диапазона — почти наверняка ошибка распознавания, а не съёмка.
YEAR_MIN, YEAR_MAX = 2015, 2035

# Типовые путаницы OCR на цифровом штампе.
CONFUSIONS = str.maketrans({
    ":": ".", ";": ".", ",": ".", "·": ".", "•": ".",
    "O": "0", "o": "0", "Q": "0", "D": "0",
    "l": "1", "I": "1", "|": "1", "!": "1",
    "S": "5", "s": "5", "B": "8", "g": "9", "?": "7",
})

DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")


@dataclass
class StampResult:
    image: str
    date: str | None          # ISO, если распознано
    confidence: float | None
    variant: str | None       # какой вариант предобработки дал ответ
    agreeing: int             # сколько независимых вариантов дали ту же дату
    raw: str | None           # исходный текст до нормализации
    note: str = ""


def _roi(img: np.ndarray) -> np.ndarray:
    h, w, _ = img.shape
    roi = img[int(h * ROI_TOP):, int(w * ROI_LEFT):]
    return cv2.resize(roi, (roi.shape[1] * UPSCALE, roi.shape[0] * UPSCALE),
                      interpolation=cv2.INTER_LANCZOS4)


def _variants(roi: np.ndarray):
    """Оригинал плюс по маске на каждое известное начертание штампа.

    Маски рендерятся как чёрный текст на белом — OCR на таком заметно
    устойчивее, чем на цветном тексте поверх фактуры.
    """
    yield "raw", roi

    r, g, b = (roi[..., i].astype(np.int16) for i in range(3))
    mx, mn = roi.max(2).astype(np.int16), roi.min(2).astype(np.int16)

    warmth = r - np.maximum(g, b)          # красный и оранжевый штампы
    thr = float(max(30, min(75, np.percentile(warmth, 99.5) * 0.5)))
    yield "warm", _as_text_image(warmth > thr)

    yield "white", _as_text_image((mn > 185) & (mx - mn < 40))

    # Top-hat по «теплоте»: снимает широкий фон и оставляет тонкие штрихи.
    # Единственная гипотеза, которая берёт тёплый штамп на тёплом же грунте,
    # где глобальный порог выделяет заодно и фон.
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (61, 61))
    hat = cv2.morphologyEx(np.clip(warmth, 0, 255).astype(np.uint8), cv2.MORPH_TOPHAT, kernel)
    hat = cv2.normalize(hat, None, 0, 255, cv2.NORM_MINMAX)
    _, binary = cv2.threshold(hat, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield "warm_tophat", cv2.cvtColor(255 - binary, cv2.COLOR_GRAY2RGB)

    # Локальный контраст — на случай начертания, не покрытого двумя масками выше.
    grey = cv2.cvtColor(roi, cv2.COLOR_RGB2GRAY)
    yield "adaptive", cv2.cvtColor(
        cv2.adaptiveThreshold(grey, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                              cv2.THRESH_BINARY, 31, -12), cv2.COLOR_GRAY2RGB)


def _as_text_image(mask: np.ndarray) -> np.ndarray:
    m = cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((2, 2), np.uint8))
    return cv2.cvtColor((1 - m) * 255, cv2.COLOR_GRAY2RGB)


def _join_fragments(det) -> list[tuple[str, float]]:
    """Склеивает куски одной строки: жирный штамп часто рвётся на фрагменты."""
    if not det:
        return []
    items = []
    for box, text, conf in det:
        ys = [p[1] for p in box]
        xs = [p[0] for p in box]
        items.append((float(np.mean(ys)), float(np.min(xs)), text, float(conf)))
    items.sort()

    lines: list[list] = []
    for cy, x, text, conf in items:
        for ln in lines:
            if abs(ln[0][0] - cy) < 14:     # та же строка по вертикали
                ln.append((cy, x, text, conf))
                break
        else:
            lines.append([(cy, x, text, conf)])

    out = []
    for ln in lines:
        ln.sort(key=lambda t: t[1])
        out.append(("".join(t[2] for t in ln), min(t[3] for t in ln)))
    return out


def _parse(text: str) -> dt.date | None:
    cleaned = text.translate(CONFUSIONS)
    cleaned = re.sub(r"[^\d.]", "", cleaned)
    # Склейка фрагментов даёт задвоенные разделители («21.» + «.01.2024»).
    cleaned = re.sub(r"\.{2,}", ".", cleaned)
    for d, m, y in DATE_RE.findall(cleaned):
        year = int(y)
        if not (YEAR_MIN <= year <= YEAR_MAX):
            continue
        try:
            return dt.date(year, int(m), int(d))   # отсеивает 32.13.2024 и т.п.
        except ValueError:
            continue
    return None


def read_stamp(path: Path, ocr) -> StampResult:
    img = np.asarray(Image.open(path).convert("RGB"))
    roi = _roi(img)

    hits: list[tuple[dt.date, float, str, str]] = []
    for name, variant in _variants(roi):
        det, _ = ocr(variant)
        for text, conf in _join_fragments(det):
            date = _parse(text)
            if date:
                hits.append((date, conf, name, text))

    if not hits:
        return StampResult(path.name, None, None, None, 0, None,
                           "штамп не найден или не читается — нужна ручная привязка")

    # Голосование между вариантами; внутри победившей даты берём лучший прогон.
    # Голоса считаем по РАЗНЫМ вариантам: один вариант может дать несколько строк.
    votes = Counter()
    for date, _, variant, _ in hits:
        votes[date] = len({v for d, _, v, _ in hits if d == date})
    best_date = max(votes, key=lambda d: (votes[d], max(h[1] for h in hits if h[0] == d)))
    best = max((h for h in hits if h[0] == best_date), key=lambda h: h[1])

    note = ""
    if len(votes) > 1:
        other = ", ".join(f"{d.isoformat()}×{c}" for d, c in votes.items() if d != best_date)
        note = f"разногласие гипотез (выбрано ×{votes[best_date]}; также: {other})"
    elif votes[best_date] == 1:
        note = "подтверждено одной гипотезой — проверить вручную"

    return StampResult(path.name, best_date.isoformat(), round(best[1], 3), best[2],
                       votes[best_date], best[3], note)


def main() -> int:
    ap = argparse.ArgumentParser(description="OCR даты, впечатанной в снимок")
    ap.add_argument("images", type=Path, help="папка со снимками")
    ap.add_argument("-o", "--out", type=Path, default=Path("data/processed"))
    args = ap.parse_args()

    from rapidocr_onnxruntime import RapidOCR
    ocr = RapidOCR()

    files = sorted(args.images.glob("*.png"),
                   key=lambda p: int("".join(c for c in p.stem if c.isdigit()) or 0))
    results = []
    for i, f in enumerate(files, 1):
        results.append(read_stamp(f, ocr))
        print(f"\r{i}/{len(files)}", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "date_stamps.json").write_text(
        json.dumps([asdict(r) for r in results], ensure_ascii=False, indent=2), encoding="utf-8")
    with (args.out / "date_stamps.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=";")
        w.writerow(["image", "date", "confidence", "agreeing", "variant", "raw", "note"])
        for r in results:
            w.writerow([r.image, r.date or "", r.confidence or "", r.agreeing,
                        r.variant or "", r.raw or "", r.note])

    ok = [r for r in results if r.date]
    summary = {
        "images": len(results),
        "recognized": len(ok),
        "unrecognized": len(results) - len(ok),
        "single_hypothesis": sum(1 for r in ok if r.agreeing == 1),
        "disagreements": sum(1 for r in ok if "разногласие" in r.note),
        "by_variant": dict(Counter(r.variant for r in ok)),
        "date_range": [min(r.date for r in ok), max(r.date for r in ok)] if ok else None,
    }
    json.dump(summary, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
