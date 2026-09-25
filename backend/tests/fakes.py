"""Fake implementations для тестирования."""

from app.adapters.ml.base import DetectionResult, DetectorInfo


class FakeDetector:
    """Fake детектор для тестирования.

    Позволяет конфигурировать результаты и отслеживать вызовы.
    """

    def __init__(
        self,
        result: DetectionResult | None = None,
        info: DetectorInfo | None = None,
        error: Exception | None = None,
        disabled: bool = False,
        ready: bool = False,
    ):
        """Инициализировать fake детектор.

        Args:
            result: Результат по умолчанию (если None, вернёт
                    DetectionResult(model_version="fake-1", detections=[]))
            info: Результат info() (если None, вернёт None)
            error: Исключение для выброса (если задано, переопределяет result)
            disabled: Если True, detect возвращает None (детектор отключен)
            ready: Значение, которое вернёт ready()
        """
        self.result = result or DetectionResult(model_version="fake-1", detections=[])
        self.info_result = info
        self.error = error
        self.disabled = disabled
        self.ready_value = ready
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

    async def info(self) -> DetectorInfo | None:
        """Получить информацию о детекторе (fake реализация).

        Returns:
            Предконфигурированный DetectorInfo или None
        """
        return self.info_result

    async def ready(self) -> bool:
        """Проверить готовность детектора (fake реализация).

        Returns:
            Предконфигурированное значение (по умолчанию False)
        """
        return self.ready_value

    @property
    def configured(self) -> bool:
        """FakeDetector по умолчанию настроен."""
        return True


class ScriptedDetector:
    """Scripted detector that returns results/exceptions in sequence."""

    def __init__(self, sequence: list):
        """Initialize with a sequence of results or exceptions.

        Args:
            sequence: List of DetectionResult, Exception, or None values to return in order
        """
        self.sequence = sequence
        self.index = 0
        self.calls: list[tuple[str, int]] = []

    async def detect(
        self, image: bytes, filename: str, content_type: str | None = None
    ) -> DetectionResult | None:
        """Return next item in sequence."""
        if self.index >= len(self.sequence):
            raise RuntimeError(f"ScriptedDetector: ran out of sequence items (index {self.index})")

        self.calls.append((filename, len(image)))
        item = self.sequence[self.index]
        self.index += 1

        if isinstance(item, Exception):
            raise item
        return item

    async def info(self) -> DetectorInfo | None:
        """Return None (not used in backlog tests)."""
        return None

    async def ready(self) -> bool:
        """Return False."""
        return False

    @property
    def configured(self) -> bool:
        """ScriptedDetector is configured."""
        return True
