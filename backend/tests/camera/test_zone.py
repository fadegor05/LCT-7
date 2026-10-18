"""Попадание рамки в рабочую зону камеры: точка — центр нижней кромки рамки."""

import pytest

from app.domains.camera.zone import bbox_in_zone, foot, point_in_polygon

SQUARE = [[0.1, 0.2], [0.9, 0.2], [0.9, 0.95], [0.1, 0.95]]
# Вогнутая «П»-форма: ножка слева, ножка справа, выемка сверху по центру
CONCAVE = [
    [0.1, 0.1],
    [0.4, 0.1],
    [0.4, 0.5],
    [0.6, 0.5],
    [0.6, 0.1],
    [0.9, 0.1],
    [0.9, 0.9],
    [0.1, 0.9],
]


def test_foot_is_bottom_center_of_bbox() -> None:
    assert foot([0.2, 0.3, 0.6, 0.8]) == pytest.approx((0.4, 0.8))


def test_point_inside_square() -> None:
    assert point_in_polygon((0.5, 0.5), SQUARE) is True


def test_point_outside_square() -> None:
    assert point_in_polygon((0.05, 0.5), SQUARE) is False
    assert point_in_polygon((0.5, 0.99), SQUARE) is False


def test_polygon_closing_edge_is_used() -> None:
    # Ребро от последней вершины к первой: точка левее него — снаружи
    assert point_in_polygon((0.95, 0.5), SQUARE) is False


def test_point_on_left_border_is_inside_by_ray_rule() -> None:
    # Полуоткрытое правило луча: левая граница включена, правая — нет.
    # Поведение совпадает с clean-mvp, на нём держится совпадение результатов.
    assert point_in_polygon((0.1, 0.5), SQUARE) is True
    assert point_in_polygon((0.9, 0.5), SQUARE) is False


def test_concave_notch_is_outside() -> None:
    assert point_in_polygon((0.5, 0.3), CONCAVE) is False  # в выемке
    assert point_in_polygon((0.25, 0.3), CONCAVE) is True  # левая ножка
    assert point_in_polygon((0.75, 0.3), CONCAVE) is True  # правая ножка
    assert point_in_polygon((0.5, 0.7), CONCAVE) is True  # перемычка внизу


def test_bbox_in_zone_tests_foot_not_center() -> None:
    # Центр рамки внутри зоны, а нижняя кромка уже ниже её нижней границы (0.95)
    inside_center_outside_foot = [0.4, 0.5, 0.6, 1.0]
    assert bbox_in_zone(inside_center_outside_foot, SQUARE) is False
    # Рамка стоит на земле внутри зоны
    assert bbox_in_zone([0.4, 0.5, 0.6, 0.9], SQUARE) is True


def test_bbox_in_zone_none_without_zone() -> None:
    assert bbox_in_zone([0.4, 0.5, 0.6, 0.9], None) is None


@pytest.mark.parametrize(
    "zone",
    [
        [],
        [[0.1, 0.1]],
        [[0.1, 0.1], [0.9, 0.9]],
    ],
)
def test_bbox_in_zone_none_for_fewer_than_three_points(zone: list) -> None:
    assert bbox_in_zone([0.4, 0.5, 0.6, 0.9], zone) is None


def test_bbox_in_zone_none_for_malformed_points() -> None:
    assert bbox_in_zone([0.4, 0.5, 0.6, 0.9], [[0.1], [0.9, 0.2], [0.5, 0.9]]) is None


def test_bbox_in_zone_none_for_malformed_bbox() -> None:
    assert bbox_in_zone([0.4, 0.5, 0.6], SQUARE) is None
