"""Где на кадре строка штампа и как она делится на знаки.

Штамп CCTV — «ДД-ММ-ГГГГ ЧЧ:ММ:СС» в левом верхнем углу, на одном месте у всех
камер одного разрешения. Шрифт не моноширинный: цифра шире разделителя («-», пробел,
«:»), поэтому сетка — не равный шаг, а раскладка «цифра / разделитель». Числа сняты
по чистым кадрам организаторов (небо за строкой).
"""

from dataclasses import dataclass

FORMAT = "DD-MM-YYYY HH:MM:SS"
SEPARATORS = {2: "-", 5: "-", 10: " ", 13: ":", 16: ":"}
DIGIT_POSITIONS = tuple(i for i, ch in enumerate(FORMAT) if ch not in "-: ")


@dataclass(frozen=True)
class Profile:
    name: str  # «2592x1944»
    width: int
    height: int
    y0: int
    y1: int
    x0: float  # левая граница первой ячейки
    digit: float  # ширина ячейки цифры
    sep: float  # ширина ячейки разделителя
    # Признаки ячейки (stamp/features.py): «ring» — контур и заливка у кольца знака
    # (тонкий шрифт 2592×1944), «local» — отличие от размытого окружения (жирный шрифт
    # 1920×1080, у которого контур тонкий). Выбраны по оценке на кадрах шести камер
    feature: str
    cell: tuple[int, int]  # нормированный размер ячейки (ширина, высота)
    # Цифра уверенна (= 1.0), если лучший эталон отрывается от второго на столько
    full_margin: float

    def edges(self, dx: float = 0.0) -> list[float]:
        xs = [self.x0 + dx]
        for ch in FORMAT:
            xs.append(xs[-1] + (self.sep if ch in "-: " else self.digit))
        return xs


PROFILES: dict[tuple[int, int], Profile] = {
    (2592, 1944): Profile("2592x1944", 2592, 1944, 84, 122, 38.0, 28.0, 16.0, "ring", (16, 24), 0.039),
    (1920, 1080): Profile("1920x1080", 1920, 1080, 43, 73, 28.0, 18.0, 10.0, "local", (18, 30), 0.039),
}


def profile_for(width: int, height: int) -> Profile | None:
    return PROFILES.get((width, height))
