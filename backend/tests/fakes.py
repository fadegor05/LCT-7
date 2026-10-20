"""Fake implementations для тестирования."""

from pathlib import Path

from app.adapters.ml.assistant import AssistantAnswer, AssistantError
from app.adapters.ml.base import DetectionResult, DetectorInfo
from app.adapters.ml.schedule_llm import GridRow, LlmScheduleResult


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

    def __init__(self, sequence: list, configured: bool = True):
        """Initialize with a sequence of results or exceptions.

        Args:
            sequence: List of DetectionResult, Exception, or None values to return in order
            configured: Whether detector is configured (default True)
        """
        self.sequence = sequence
        self.index = 0
        self.calls: list[tuple[str, int]] = []
        self._configured = configured

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
        """ScriptedDetector is configured (configurable via constructor)."""
        return self._configured


class FakeAssistantClient:
    """Fake ассистент для тестирования.

    Позволяет конфигурировать результаты и отслеживать вызовы.
    """

    def __init__(
        self,
        answer: AssistantAnswer | None = None,
        error: AssistantError | None = None,
        enabled: bool = True,
    ):
        """Инициализировать fake ассистента.

        Args:
            answer: Результат по умолчанию (если None, вернёт default answer)
            error: Исключение для выброса (если задано, переопределяет answer)
            enabled: Значение available() (по умолчанию True)
        """
        self.answer = answer or AssistantAnswer(
            answer="Fake answer",
            verified=True,
            numbers_not_in_report=[],
            numbers_of_other_site=[],
            limits="",
        )
        self.error = error
        self.enabled = enabled
        self.calls: list[tuple[str, dict, str | None]] = []  # (question, report, site_id)

    async def ask(self, question: str, report: dict, site_id: str | None = None) -> AssistantAnswer:
        """Задать вопрос (fake реализация).

        Записывает информацию о вызове и возвращает предконфигурированный результат
        или выбрасывает исключение.

        Args:
            question: Вопрос
            report: Отчёт
            site_id: ID площадки

        Returns:
            Предконфигурированный результат

        Raises:
            Предконфигурированное исключение, если оно задано
        """
        self.calls.append((question, report, site_id))

        if self.error is not None:
            raise self.error

        return self.answer

    async def available(self) -> bool:
        """Проверить доступность (fake реализация).

        Returns:
            Предконфигурированное значение (по умолчанию True)
        """
        return self.enabled


class FakeScheduleLlmClient:
    """Fake LLM-разбор плана: отдаёт заданный результат или бросает заданную ошибку."""

    def __init__(
        self,
        result: LlmScheduleResult | None = None,
        error: AssistantError | None = None,
    ):
        self.result = result or LlmScheduleResult(rows=[], issues=[])
        self.error = error
        self.calls: list[list[GridRow]] = []

    async def parse(self, rows) -> LlmScheduleResult:
        self.calls.append(list(rows))
        if self.error is not None:
            raise self.error
        return self.result


def jpeg_bytes(color: tuple[int, int, int] = (120, 120, 120)) -> bytes:
    """Настоящий JPEG (Pillow), который принимает загрузка фотографий."""
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (160, 120), color=color).save(buf, format="JPEG")
    return buf.getvalue()


class FakeGrabber:
    """Стрим камеры: по ссылке отдаёт новый JPEG (не дубликат) или заданную ошибку.

    `busy` — имитирует занятую камеру (второй снимок параллельно), `calls` — все запросы.
    """

    def __init__(self) -> None:
        self.errors: dict[str, str] = {}
        self.calls: list[str] = []
        self.busy = False

    async def grab(self, url: str) -> bytes:
        from app.adapters.stream.base import StreamBusy, StreamError

        self.calls.append(url)
        if self.busy:
            raise StreamBusy("Снимок с этой камеры уже идёт")
        if url in self.errors:
            raise StreamError(self.errors[url])
        shade = len(self.calls) * 37 % 250
        return jpeg_bytes(color=(shade, 120, 150))


class FakeFrameExtractor:
    """Кадры из видео без ffmpeg: длительность и кадры задают тесты, `error` — VideoError.

    `calls` — (имя файла, шаг, лимит кадров) для каждого извлечения.
    """

    def __init__(self) -> None:
        self.duration = 180.0
        self.frames: list[bytes] = [
            jpeg_bytes(color=(40, 40, 40)),
            jpeg_bytes(color=(90, 90, 90)),
            jpeg_bytes(color=(140, 140, 140)),
        ]
        self.error: Exception | None = None
        self.calls: list[tuple[str, int, int]] = []

    async def duration_s(self, path: Path) -> float:
        if self.error is not None:
            raise self.error
        return self.duration

    async def extract(self, path: Path, step_s: int, max_frames: int) -> list[bytes]:
        self.calls.append((path.name, step_s, max_frames))
        if self.error is not None:
            raise self.error
        return list(self.frames)
