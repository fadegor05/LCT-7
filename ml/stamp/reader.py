"""Чтение штампа по эталонам знаков (§9.2): без OCR для известных разрешений.

1. Профиль по размеру кадра; неизвестный размер — не здесь (запасной путь OCR).
2. Есть ли строка штампа: разделители «-», «-», «:», «:» на своих местах похожи на
   эталоны. Нет — `found = false`: только тогда бэкенд смотрит на имя файла.
3. Каждая цифра — ближайший эталон среди допустимых на этой позиции (день 0–3…,
   месяц 0–1…, часы 0–2…, минуты и секунды 0–5…), затем календарная проверка.
4. Уверенность — по самой слабой цифре: насколько лучший эталон отрывается от
   второго. Сомнительная цифра опускает уверенность всей строки: неверное время
   хуже, чем ручная проверка.
"""

from dataclasses import dataclass
from datetime import datetime

import numpy as np

from stamp.features import cell_maps
from stamp.layout import DIGIT_POSITIONS, FORMAT, SEPARATORS, Profile, profile_for
from stamp.templates import Templates

# Строка штампа есть, если разделители в среднем похожи на эталоны не меньше этого.
# На 500 кадрах камер: настоящие строки — от 0.55, то же окно без штампа — до 0.41
FOUND_SCORE = 0.48
# Цифра читается, если лучший эталон похож хотя бы так
MIN_DIGIT_SCORE = 0.15

ALLOWED: dict[int, str] = {
    0: "0123", 3: "01", 6: "2", 7: "0", 11: "012", 14: "012345", 17: "012345",
}
DIGITS = "0123456789"


@dataclass(frozen=True)
class StampRead:
    found: bool
    captured_at: datetime | None
    confidence: float
    text: str | None  # прочитанная строка, для отладки и оценки
    weakest: int | None  # позиция самой сомнительной цифры


def read_cells(maps: list[np.ndarray], templates: Templates, full_margin: float) -> StampRead:
    seps = [templates.best(maps[i], SEPARATORS[i]) for i in SEPARATORS if SEPARATORS[i] != " "]
    sep_score = float(np.mean([s[0][0] if s else 0.0 for s in seps]))
    if sep_score < FOUND_SCORE:
        return StampRead(False, None, 0.0, None, None)
    chars = list(FORMAT)
    confidences: dict[int, float] = {}
    for i in DIGIT_POSITIONS:
        scored = templates.best(maps[i], ALLOWED.get(i, DIGITS))
        if not scored:
            return StampRead(True, None, 0.0, None, i)
        best_score, best = scored[0]
        second = scored[1][0] if len(scored) > 1 else 0.0
        chars[i] = best
        confidences[i] = (
            0.0 if best_score < MIN_DIGIT_SCORE else min(1.0, (best_score - second) / full_margin)
        )
    text = "".join(chars)
    weakest = min(confidences, key=confidences.get)
    try:
        moment = datetime.strptime(text, "%d-%m-%Y %H:%M:%S")
    except ValueError:  # 31-02, 25:…: штамп есть, но прочитан неверно
        return StampRead(True, None, 0.0, text, weakest)
    return StampRead(True, moment, round(confidences[weakest], 3), text, weakest)


def read_gray(gray: np.ndarray, templates: dict[str, Templates]) -> tuple[StampRead, Profile] | None:
    """None — разрешение без профиля или без эталонов: решать запасному пути."""
    profile = profile_for(gray.shape[1], gray.shape[0])
    if profile is None or profile.name not in templates:
        return None
    maps = cell_maps(gray, profile)
    return read_cells(maps, templates[profile.name], profile.full_margin), profile
