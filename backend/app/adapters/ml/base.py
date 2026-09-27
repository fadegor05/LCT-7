"""Базовые типы и контракты ML-адаптера.

Модуль определяет протокол DetectorClient и типы данных для работы с детекциями.
Детекции от ML-сервиса содержат класс объекта, уверенность и bbox как доли размера.
"""

from dataclasses import dataclass
from typing import Protocol


class DetectorError(Exception):
    """Ошибка при работе с детектором.

    Attributes:
        transient: True если ошибка временная (503, timeout, connect, 5xx)
                   и стоит повторить попытку позже.
    """

    def __init__(self, message: str, *, transient: bool = False) -> None:
        """Инициализировать ошибку детектора.

        Args:
            message: Сообщение об ошибке
            transient: True если ошибка временная и стоит повторить
        """
        super().__init__(message)
        self.transient = transient


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
        model_version: Версия модели (напр. "mocs_m_best@3f1c9a0b7e21")
        detections: Список найденных объектов (может быть пустым)
        width: Ширина изображения (int или None)
        height: Высота изображения (int или None)
    """

    model_version: str
    detections: list[RawDetection]
    width: int | None = None
    height: int | None = None


@dataclass(frozen=True)
class DetectorInfo:
    """Информация о детекторе от ML-сервиса.

    Attributes:
        model_version: Версия модели
        class_names: Кортеж названий классов в порядке сортировки
        conf_threshold: Порог уверенности (опционально)
        device: Устройство, на котором работает модель (опционально)
        contract: Версия контракта (опционально)
    """

    model_version: str
    class_names: tuple[str, ...]
    conf_threshold: float | None
    device: str | None
    contract: str | None


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

    async def info(self) -> DetectorInfo | None:
        """Получить информацию о детекторе.

        Returns:
            DetectorInfo с информацией о модели, или None если недоступен

        Raises:
            DetectorError: При критической ошибке
        """
        ...

    async def ready(self) -> bool:
        """Проверить, готов ли детектор к использованию.

        Returns:
            True если детектор готов и модель загружена, False иначе
        """
        ...

    @property
    def configured(self) -> bool:
        """True если детектор настроен (не NullDetector).

        Returns:
            True если это HttpDetectorClient, False если NullDetector
        """
        ...
