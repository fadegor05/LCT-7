"""HTTP-клиент для ML-детектора.

Модуль определяет HttpDetectorClient — адаптер к ML HTTP-сервису.

Контракт ML HTTP-сервиса (см. ml/docs/CONTRACTS.md §1):

    POST {base}/detect (или {base}/detect если base содержит /detect)

    Request: multipart/form-data с полем `file` (изображение)

    Response:
    {
        "model": "mocs_m_best@3f1c9a0b7e21",
        "image": "Screenshot_26.png",
        "width": 1219,
        "height": 809,
        "speed_ms": {...},
        "detections": [
            {
                "class_raw": "drilling_rig",
                "class_ours": "drilling_rig",
                "conf": 0.88,
                "bbox": [0.5396, 0.0, 0.6227, 0.6529]
            }
        ]
    }

Поле `bbox` — доли размера кадра [x1, y1, x2, y2], origine top-left.
Округление: bbox до 4 знаков, conf до 3 знаков.
"""

import asyncio
import logging
import re
from typing import NewType

import httpx
from pydantic import BaseModel, Field, field_validator

from app.adapters.ml.base import DetectionResult, DetectorError, DetectorInfo, RawDetection
from app.core.settings import DetectorSettings

logger = logging.getLogger(__name__)

# NewType для обозначения DetectorHttpClient
DetectorHttpClient = NewType("DetectorHttpClient", httpx.AsyncClient)

# Expected contract version
EXPECTED_CONTRACT = "detect/v1"


def normalize_base_url(url: str) -> str:
    """Нормализовать базовый URL.

    Убирает trailing '/', удаляет '/detect' суффикс (с warning).

    Args:
        url: Базовый URL

    Returns:
        Нормализованный URL

    Example:
        normalize_base_url("http://ml:8000/detect/") -> "http://ml:8000"
        normalize_base_url("http://ml:8000/") -> "http://ml:8000"
    """
    url = url.strip()
    # Remove trailing / first
    if url.endswith("/"):
        url = url[:-1]
    # Then check for /detect suffix
    if url.endswith("/detect"):
        logger.warning(f"URL ends with /detect, removing: {url}")
        url = url[:-7]
    return url


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
    """Pydantic-схема ответа ML-сервиса от /detect."""

    model: str | None = None
    width: int | None = None
    height: int | None = None
    speed_ms: dict[str, float] | None = None
    detections: list[_DetectionSchema] = []

    model_config = {"extra": "ignore"}


class _MetaSchema(BaseModel):
    """Pydantic-схема ответа ML-сервиса от /meta."""

    model: str | None = None
    weights: str | None = None
    class_names: list[str] = Field(default_factory=list)
    conf: float | None = None
    device: str | None = None
    contract: str | None = None

    model_config = {"extra": "ignore"}


class _HealthSchema(BaseModel):
    """Pydantic-схема ответа ML-сервиса от /health."""

    model_loaded: bool = False

    model_config = {"extra": "ignore"}


class HttpDetectorClient:
    """Клиент для HTTP ML-сервиса.

    Отправляет multipart/form-data запрос с изображением и парсит JSON ответ.
    Поддерживает retry логику, кэширование, семафор для ограничения одновременных запросов.

    Args:
        base_url: Базовый URL ML-сервиса (напр. http://ml:8000)
        client: httpx.AsyncClient для отправки запросов
        settings: DetectorSettings с параметрами retry и timeout
        sleep: Функция для задержки (для тестов)
    """

    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient,
        settings: DetectorSettings,
        sleep=asyncio.sleep,
    ):
        """Инициализировать HttpDetectorClient.

        Args:
            base_url: Базовый URL
            client: httpx.AsyncClient
            settings: DetectorSettings
            sleep: Async функция для ожидания (по умолчанию asyncio.sleep)
        """
        self.base_url = normalize_base_url(base_url)
        self.client = client
        self.settings = settings
        self._sleep = sleep
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._info_cache: DetectorInfo | None = None
        self._info_cache_valid = False

    @property
    def configured(self) -> bool:
        """HttpDetectorClient всегда настроен."""
        return True

    async def _wait_before_retry(self, attempt: int, spent: float) -> float | None:
        """Подождать перед повтором с exponential backoff.

        Args:
            attempt: Номер попытки (начиная с 1)
            spent: Уже потраченное время сна (в секундах)

        Returns:
            Новая сумма потраченного времени, или None если бюджет исчерпан
        """
        backoff_index = min(attempt - 1, len(self.settings.retry_backoff_s) - 1)
        sleep_time = self.settings.retry_backoff_s[backoff_index]
        if spent + sleep_time <= self.settings.retry_budget_s:
            await self._sleep(sleep_time)
            return spent + sleep_time
        return None

    async def detect(
        self, image: bytes, filename: str, content_type: str | None = None
    ) -> DetectionResult | None:
        """Отправить изображение на детекцию с retry логикой.

        Args:
            image: Байты изображения
            filename: Имя файла для multipart и логирования
            content_type: MIME-тип (напр. "image/jpeg"), опционально

        Returns:
            DetectionResult с детекциями

        Raises:
            DetectorError: При ошибке, которую нельзя повторить
                          или исчерпании retry бюджета
        """
        url = f"{self.base_url}/detect"
        timeout = httpx.Timeout(self.settings.timeout_s, connect=self.settings.connect_timeout_s)

        retry_503_count = 0
        retry_other_count = 0
        total_sleep = 0.0

        while True:
            try:
                async with self._semaphore:
                    response = await self.client.post(
                        url,
                        files={"file": (filename, image, content_type)},
                        timeout=timeout,
                    )

                # Обработка статуса 503
                if response.status_code == 503:
                    if retry_503_count < self.settings.retry_503:
                        retry_503_count += 1
                        new_spent = await self._wait_before_retry(retry_503_count, total_sleep)
                        if new_spent is not None:
                            total_sleep = new_spent
                            continue
                    # Исчерпаны попытки
                    raise DetectorError(
                        "503 Service Unavailable (exhausted retries)", transient=True
                    )

                # Обработка других 4xx (включая 400, 413, 422)
                if 400 <= response.status_code < 500:
                    raise DetectorError(
                        f"HTTP {response.status_code} from detector",
                        transient=False,
                    )

                # Обработка других 5xx
                if response.status_code >= 500:
                    if retry_other_count < self.settings.retry_other:
                        retry_other_count += 1
                        new_spent = await self._wait_before_retry(retry_other_count, total_sleep)
                        if new_spent is not None:
                            total_sleep = new_spent
                            continue
                    raise DetectorError(
                        f"HTTP {response.status_code} from detector (exhausted retries)",
                        transient=True,
                    )

                # 200 OK - парсим ответ
                if response.status_code == 200:
                    try:
                        data = response.json()
                    except Exception as e:
                        logger.error(f"Failed to parse JSON response from detector: {e}")
                        raise DetectorError(
                            "Invalid JSON response from detector", transient=False
                        ) from e

                    try:
                        parsed = _ResponseSchema(**data)
                    except Exception as e:
                        logger.error(f"Response schema mismatch from detector: {e}")
                        raise DetectorError(
                            "Response schema mismatch from detector", transient=False
                        ) from e

                    # Получить model_version
                    model_version = parsed.model
                    if not model_version:
                        # Fallback to info()
                        info = await self.info()
                        if info is None:
                            raise DetectorError(
                                "Missing model in response and info() unavailable",
                                transient=True,
                            )
                        model_version = info.model_version

                    # Конвертировать в RawDetection с округлением и clamping
                    detections = []
                    for det in parsed.detections:
                        x1, y1, x2, y2 = det.bbox
                        # Clamping
                        x1 = max(0.0, min(1.0, x1))
                        y1 = max(0.0, min(1.0, y1))
                        x2 = max(0.0, min(1.0, x2))
                        y2 = max(0.0, min(1.0, y2))

                        # Округление
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

                    result = DetectionResult(
                        model_version=model_version,
                        detections=detections,
                        width=parsed.width,
                        height=parsed.height,
                    )

                    # Логирование
                    speed_str = ""
                    if parsed.speed_ms and "total" in parsed.speed_ms:
                        speed_str = f" speed_ms.total={parsed.speed_ms['total']}"
                    logger.info(
                        "Detected: %s model=%s detections=%d%s",
                        filename,
                        model_version,
                        len(detections),
                        speed_str,
                    )

                    return result

                # Неожиданный статус код
                raise DetectorError(
                    f"Unexpected HTTP status {response.status_code}", transient=False
                )

            except DetectorError:
                raise
            except httpx.TimeoutException as e:
                if retry_other_count < self.settings.retry_other:
                    retry_other_count += 1
                    new_spent = await self._wait_before_retry(retry_other_count, total_sleep)
                    if new_spent is not None:
                        total_sleep = new_spent
                        continue
                raise DetectorError("Timeout (exhausted retries)", transient=True) from e
            except httpx.TransportError as e:
                if retry_other_count < self.settings.retry_other:
                    retry_other_count += 1
                    new_spent = await self._wait_before_retry(retry_other_count, total_sleep)
                    if new_spent is not None:
                        total_sleep = new_spent
                        continue
                raise DetectorError("Connection error (exhausted retries)", transient=True) from e

    async def info(self) -> DetectorInfo | None:
        """Получить информацию о детекторе от /meta.

        Результат кэшируется после первого успешного вызова.
        На ошибку возвращает None и сбрасывает кэш.

        Returns:
            DetectorInfo или None при ошибке
        """
        if self._info_cache_valid:
            return self._info_cache

        try:
            url = f"{self.base_url}/meta"
            timeout = httpx.Timeout(
                self.settings.timeout_s,
                connect=self.settings.connect_timeout_s,
            )
            response = await self.client.get(url, timeout=timeout)

            if response.status_code != 200:
                logger.warning(f"Failed to get detector info: HTTP {response.status_code}")
                self._info_cache_valid = False
                self._info_cache = None
                return None

            try:
                data = response.json()
                parsed = _MetaSchema(**data)
            except Exception as e:
                logger.warning(f"Failed to parse detector info: {e}")
                self._info_cache_valid = False
                self._info_cache = None
                return None

            # Получить model_version (model или weights)
            model_version = parsed.model or parsed.weights
            if not model_version:
                logger.warning("Detector info missing both 'model' and 'weights'")
                self._info_cache_valid = False
                self._info_cache = None
                return None

            # Проверить contract
            if parsed.contract:
                # Parse "<name>/v<major>[.<minor>]"
                match = re.match(r"^(\w+)/v(\d+)(?:\.(\d+))?$", parsed.contract)
                if match:
                    name, major_str, _minor = match.groups()
                    major = int(major_str)
                    if name != "detect" or major != 1:
                        logger.error(
                            "Detector contract mismatch: expected '%s', got '%s'",
                            EXPECTED_CONTRACT,
                            parsed.contract,
                        )
                else:
                    logger.error("Detector contract format unrecognized: '%s'", parsed.contract)

            info = DetectorInfo(
                model_version=model_version,
                class_names=tuple(parsed.class_names),
                conf_threshold=parsed.conf,
                device=parsed.device,
                contract=parsed.contract,
            )
            self._info_cache = info
            self._info_cache_valid = True
            return info

        except Exception as e:
            logger.warning(f"Unexpected error getting detector info: {e}")
            self._info_cache_valid = False
            self._info_cache = None
            return None

    async def ready(self) -> bool:
        """Проверить, готов ли детектор (model_loaded).

        Вызывает GET /health и проверяет model_loaded.

        Returns:
            True если model_loaded=true, False иначе
        """
        try:
            url = f"{self.base_url}/health"
            timeout = httpx.Timeout(
                self.settings.timeout_s,
                connect=self.settings.connect_timeout_s,
            )
            response = await self.client.get(url, timeout=timeout)

            if response.status_code != 200:
                return False

            try:
                data = response.json()
                parsed = _HealthSchema(**data)
                return parsed.model_loaded
            except Exception:
                return False

        except Exception:
            return False
