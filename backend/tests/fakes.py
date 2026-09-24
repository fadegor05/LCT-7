"""Fake implementations для тестирования."""

from app.adapters.ml.base import DetectionResult


class FakeDetector:
    """Fake детектор для тестирования.

    Позволяет конфигурировать результаты и отслеживать вызовы.
    """

    def __init__(
        self,
        result: DetectionResult | None = None,
        error: Exception | None = None,
        disabled: bool = False,
    ):
        """Инициализировать fake детектор.

        Args:
            result: Результат по умолчанию (если None, вернёт
                    DetectionResult(model_version="fake-1", detections=[]))
            error: Исключение для выброса (если задано, переопределяет result)
            disabled: Если True, detect возвращает None (детектор отключен)
        """
        self.result = result or DetectionResult(model_version="fake-1", detections=[])
        self.error = error
        self.disabled = disabled
        self.calls: list[tuple[str, int]] = []  # (filename, size)

    async def detect(
        self, image: bytes, filename: str, content_type: str | None = None
    ) -> DetectionResult | None:
        """Детектировать объекты (fake реализация).

        Записывает информацию о вызове и возвращает предконфигурированный результат
        или выбрасывает исключение. Если disabled=True, возвращает None.

        Args:
            image: Байты изображения
            filename: Имя файла
            content_type: MIME-тип (не используется в fake)

        Returns:
            Предконфигурированный результат или None если disabled

        Raises:
            Предконфигурированное исключение, если оно задано
        """
        self.calls.append((filename, len(image)))

        if self.error is not None:
            raise self.error

        if self.disabled:
            return None

        return self.result
