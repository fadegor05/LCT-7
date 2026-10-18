"""Pydantic-схемы камер стройки и их рабочих зон."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Вершин больше этого редактор не ставит; защита от мусора в запросе
MAX_ZONE_POINTS = 100
# Площадь зоны в долях кадра: меньше — вершины почти на одной линии, зона пустая
MIN_ZONE_AREA = 1e-4
# Снимать не чаще раза в минуту и не реже раза в сутки
MIN_CAPTURE_EVERY_S = 60
MAX_CAPTURE_EVERY_S = 86400


def _area(points: list[list[float]]) -> float:
    """Площадь многоугольника по формуле шнурования."""
    total = 0.0
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1], strict=True):
        total += x1 * y2 - x2 * y1
    return abs(total) / 2


def _check_zone(value: list[list[float]] | None) -> list[list[float]] | None:
    if value is None:
        return None
    if not 3 <= len(value) <= MAX_ZONE_POINTS:
        raise ValueError(f"зона — от 3 до {MAX_ZONE_POINTS} вершин")
    for point in value:
        if len(point) != 2 or not all(0 <= c <= 1 for c in point):
            raise ValueError("вершина зоны — [x, y] в долях кадра от 0 до 1")
    if _area(value) < MIN_ZONE_AREA:
        raise ValueError("вершины зоны лежат почти на одной линии")
    return [[float(x), float(y)] for x, y in value]


class CameraIn(BaseModel):
    """Создание камеры."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    # Ссылка проверяется в CameraService: pydantic-ошибка вернула бы её саму (с учётными данными)
    stream_url: str | None = None
    # Без интервала камера со ссылкой снимает по умолчанию раз в 5 минут (см. service)
    capture_every_s: int | None = Field(
        default=None, ge=MIN_CAPTURE_EVERY_S, le=MAX_CAPTURE_EVERY_S
    )
    zone: list[list[float]] | None = None

    _zone = field_validator("zone")(_check_zone)


class CameraUpdate(BaseModel):
    """Частичная правка: поля, которых нет в запросе, не меняются.

    `zone: null` — убрать зону, `stream_url: null` — убрать ссылку.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    stream_url: str | None = None
    capture_every_s: int | None = Field(
        default=None, ge=MIN_CAPTURE_EVERY_S, le=MAX_CAPTURE_EVERY_S
    )
    zone: list[list[float]] | None = None

    @field_validator("name", mode="before")
    @classmethod
    def _name_not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("название не может быть пустым")
        return value

    _zone = field_validator("zone")(_check_zone)


class CameraRead(BaseModel):
    """Чтение камеры; frames_count — сколько фотографий привязано к камере."""

    id: uuid.UUID
    name: str
    stream_url: str | None
    capture_every_s: int | None
    last_capture_at: datetime | None
    last_capture_error: str | None
    # Момент последней попытки (удачной или нет) и сбои подряд; у новой камеры — пусто и 0
    last_capture_attempt_at: datetime | None = None
    capture_failures: int = 0
    zone: list[list[float]] | None
    frames_count: int
    created_at: datetime
