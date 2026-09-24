"""HTTP-клиент для ML-детектора.

Модуль определяет HttpDetectorClient — адаптер к ML HTTP-сервису.

Контракт ML HTTP-сервиса (см. ml/docs/CONTRACTS.md §1):

    POST /detect (или другой path в url)

    Request: multipart/form-data с полем `file` (изображение)

    Response:
    {
        "model": "yoloe-26s-seg.pt",
        "detections": [
            {
                "class_ours": "excavator",
                "conf": 0.914,
                "bbox": [0.1, 0.2, 0.3, 0.4]
            }
        ]
    }

Поле `bbox` — доли размера кадра [x1, y1, x2, y2], origine top-left.
Округление: bbox до 4 знаков, conf до 3 знаков (как в CONTRACTS.md).
"""

import httpx
from pydantic import BaseModel, Field, field_validator

from app.adapters.ml.base import DetectionResult, DetectorError, RawDetection


class _DetectionSchema(BaseModel):
    """Pydantic-схема одной детекции в ответе ML-сервиса.

    Игнорирует неизвестные поля.
    """

    class_ours: str
    conf: float
    bbox: list[float] = Field(min_length=4, max_length=4)

    model_config = {"extra": "ignore"}

    @field_validator("conf")
    @classmethod
    def validate_conf(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError(f"conf must be in [0, 1], got {v}")
        return v

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, v: list[float]) -> list[float]:
        x1, y1, x2, y2 = v
        # Проверяем диапазон с tolerance 1e-6
        TOLERANCE = 1e-6
        for i, val in enumerate(v):
            if val < -TOLERANCE or val > 1 + TOLERANCE:
                raise ValueError(f"bbox coordinate {i} out of range [0, 1]: {val}")

        # Проверяем x2 > x1 и y2 > y1
        if x2 <= x1:
            raise ValueError(f"bbox: x2 ({x2}) must be > x1 ({x1})")
        if y2 <= y1:
            raise ValueError(f"bbox: y2 ({y2}) must be > y1 ({y1})")

        return v


class _ResponseSchema(BaseModel):
    """Pydantic-схема ответа ML-сервиса."""

    model: str
    detections: list[_DetectionSchema] = []

    model_config = {"extra": "ignore"}

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("model must be non-empty")
        return v


class HttpDetectorClient:
    """Клиент для HTTP ML-сервиса.

    Отправляет multipart/form-data запрос с изображением и парсит JSON ответ.

    Args:
        url: URL ML-сервиса (базовый path для POST)
        timeout_s: Timeout для HTTP запроса (default 30.0 сек)
        client: Инъектированный httpx.AsyncClient (для тестов).
                Если None, создаётся новый клиент per call.
    """

    def __init__(
        self,
        url: str,
        timeout_s: float = 30.0,
        client: httpx.AsyncClient | None = None,
    ):
        self.url = url
        self.timeout_s = timeout_s
        self._client = client

    async def detect(
        self, image: bytes, filename: str, content_type: str | None = None
    ) -> DetectionResult | None:
        """Отправить изображение на детекцию.

        Args:
            image: Байты изображения
            filename: Имя файла для multipart
            content_type: MIME-тип (напр. "image/jpeg"), опционально

        Returns:
            DetectionResult с округленными detections, или None если детектор отключен

        Raises:
            DetectorError: HTTP ошибка, невалидный JSON, ошибка валидации
        """
        try:
            if self._client:
                # Использовать инъектированный клиент (для тестов)
                response = await self._client.post(
                    self.url,
                    files={"file": (filename, image, content_type)},
                    timeout=self.timeout_s,
                )
            else:
                # Создать временный клиент per call
                async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                    response = await client.post(
                        self.url,
                        files={"file": (filename, image, content_type)},
                    )

            # Проверить статус
            if response.status_code >= 400:
                raise DetectorError(f"HTTP {response.status_code} от детектора")

            # Парсить JSON
            try:
                data = response.json()
            except Exception as e:
                raise DetectorError("Ошибка парсинга JSON от детектора") from e

            # Валидировать через pydantic
            try:
                parsed = _ResponseSchema(**data)
            except Exception as e:
                raise DetectorError(f"Невалидный ответ от детектора: {str(e)}") from e

            # Конвертировать в RawDetection с округлением
            detections = []
            for det in parsed.detections:
                # Clamping bbox в пределы [0, 1]
                x1, y1, x2, y2 = det.bbox
                x1 = max(0.0, min(1.0, x1))
                y1 = max(0.0, min(1.0, y1))
                x2 = max(0.0, min(1.0, x2))
                y2 = max(0.0, min(1.0, y2))

                # Округление: bbox до 4 знаков, conf до 3
                bbox_rounded = (
                    round(x1, 4),
                    round(y1, 4),
                    round(x2, 4),
                    round(y2, 4),
                )
                conf_rounded = round(det.conf, 3)

                detections.append(
                    RawDetection(
                        class_ours=det.class_ours,
                        conf=conf_rounded,
                        bbox=bbox_rounded,
                    )
                )

            return DetectionResult(model_version=parsed.model, detections=detections)

        except DetectorError:
            # Re-raise DetectorError как есть
            raise
        except httpx.TimeoutException as e:
            raise DetectorError("Timeout при запросе к детектору") from e
        except httpx.ConnectError as e:
            raise DetectorError("Ошибка подключения к детектору") from e
        except Exception as e:
            # Ловим любые другие ошибки (напр. network errors)
            raise DetectorError(f"Ошибка детектора: {type(e).__name__}") from e
