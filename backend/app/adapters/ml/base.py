"""Базовые типы и контракты ML-адаптера.

Модуль определяет протокол DetectorClient и типы данных для работы с детекциями.
Детекции от ML-сервиса содержат класс объекта, уверенность и bbox как доли размера.
"""

from dataclasses import dataclass
from typing import Protocol


class DetectorError(Exception):
    """Ошибка при работе с детектором."""

    pass


@dataclass(frozen=True)
class RawDetection:
    """Одна детекция из ML-сервиса.

    Attributes:
        class_ours: Класс объекта (из LABELING_SPEC.md)
        conf: Уверенность в [0, 1]
        bbox: Bounding box как (x1, y1, x2, y2) — доли размера кадра
    """

    class_ours: str
    conf: float
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class DetectionResult:
    """Результат детекции одного кадра.

    Attributes:
        model_version: Версия модели (напр. "yoloe-26s-seg.pt")
        detections: Список найденных объектов (может быть пустым)
    """

    model_version: str
    detections: list[RawDetection]


class DetectorClient(Protocol):
    """Протокол клиента детектора.

    Детектор может быть отключен (вернёт None),
    либо возвращает результат с детекциями.
    """

    async def detect(
        self, image: bytes, filename: str, content_type: str | None = None
    ) -> DetectionResult | None:
        """Детектировать объекты на кадре.

        Args:
            image: Байты изображения
            filename: Имя файла (для логирования и multipart)
            content_type: MIME-тип (напр. "image/jpeg"), опционально

        Returns:
            DetectionResult с детекциями, или None если детектор отключен

        Raises:
            DetectorError: При ошибке сервиса или валидации
        """
        ...
