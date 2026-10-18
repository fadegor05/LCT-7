"""Попадание рамки детекции в рабочую зону камеры (доли кадра).

Точка проверки — центр нижней кромки рамки: там техника стоит на земле. Многоугольник
проверяется лучом вправо (чётность пересечений). Та же точка и та же проверка, что в
clean-mvp (observation/geometry.py), иначе зоны дадут разные ответы в разных ветках.
"""

from collections.abc import Sequence

Point = tuple[float, float]


def foot(bbox: Sequence[float]) -> Point:
    """Центр нижней кромки рамки [x1, y1, x2, y2]."""
    return (bbox[0] + bbox[2]) / 2, bbox[3]


def point_in_polygon(point: Point, polygon: Sequence[Sequence[float]]) -> bool:
    """Точка внутри многоугольника. Горизонтальные рёбра не учитываются, полуоткрытое правило."""
    x, y = point
    result = False
    for (x1, y1), (x2, y2) in zip(polygon, [*polygon[1:], polygon[0]], strict=True):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            result = not result
    return result


def bbox_in_zone(bbox: Sequence[float], zone: Sequence[Sequence[float]] | None) -> bool | None:
    """Стоит ли рамка в рабочей зоне камеры.

    None — зоны нет или она непригодна (меньше трёх вершин, не пары координат), либо
    рамка не из четырёх чисел: тогда проверки нет, и правило «вне зоны» не срабатывает.
    """
    if zone is None or len(zone) < 3 or any(len(p) != 2 for p in zone):
        return None
    if len(bbox) != 4:
        return None
    return point_in_polygon(foot(bbox), zone)
