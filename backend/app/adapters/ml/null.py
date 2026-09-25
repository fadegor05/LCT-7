"""NullDetector — детектор, который всегда отключен (возвращает None)."""

from app.adapters.ml.base import DetectionResult, DetectorInfo


class NullDetector:
    """Детектор-заглушка: реализует DetectorClient, но всегда возвращает None.

    Используется когда ML-сервис отключен в конфиге.
    """

    async def detect(
        self, image: bytes, filename: str, content_type: str | None = None
    ) -> DetectionResult | None:
        """Всегда возвращает None (детектор отключен)."""
        return None

    async def info(self) -> DetectorInfo | None:
        """Всегда возвращает None (детектор отключен)."""
        return None

    async def ready(self) -> bool:
        """Всегда возвращает False (детектор отключен)."""
        return False

    @property
    def configured(self) -> bool:
        """NullDetector не настроен."""
        return False
