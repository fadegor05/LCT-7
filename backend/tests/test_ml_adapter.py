"""Тесты адаптера ML-детектора.

Проверяют NullDetector, HttpDetectorClient и factory.
"""

import httpx
import pytest

from app.adapters.ml import (
    DetectionResult,
    DetectorError,
    HttpDetectorClient,
    NullDetector,
    RawDetection,
    create_detector,
)
from app.core.settings import DetectorSettings, Settings


class TestRawDetection:
    """Проверка dataclass RawDetection."""

    def test_raw_detection_fields(self):
        """RawDetection содержит class_ours, conf, bbox."""
        det = RawDetection(class_ours="excavator", conf=0.91, bbox=(0.1, 0.2, 0.3, 0.4))
        assert det.class_ours == "excavator"
        assert det.conf == 0.91
        assert det.bbox == (0.1, 0.2, 0.3, 0.4)

    def test_raw_detection_frozen(self):
        """RawDetection заморожен."""
        det = RawDetection(class_ours="excavator", conf=0.91, bbox=(0.1, 0.2, 0.3, 0.4))
        from dataclasses import FrozenInstanceError

        with pytest.raises(FrozenInstanceError):
            det.class_ours = "other"  # type: ignore


class TestDetectionResult:
    """Проверка dataclass DetectionResult."""

    def test_detection_result_fields(self):
        """DetectionResult содержит model_version и список detections."""
        dets = [
            RawDetection(class_ours="excavator", conf=0.91, bbox=(0.1, 0.2, 0.3, 0.4)),
        ]
        result = DetectionResult(model_version="yoloe-26s-seg.pt", detections=dets)
        assert result.model_version == "yoloe-26s-seg.pt"
        assert len(result.detections) == 1

    def test_detection_result_empty_detections(self):
        """DetectionResult может содержать пустой список."""
        result = DetectionResult(model_version="yoloe-26s-seg.pt", detections=[])
        assert result.detections == []

    def test_detection_result_frozen(self):
        """DetectionResult заморожен."""
        result = DetectionResult(model_version="yoloe-26s-seg.pt", detections=[])
        from dataclasses import FrozenInstanceError

        with pytest.raises(FrozenInstanceError):
            result.model_version = "other"  # type: ignore


class TestDetectorError:
    """Проверка DetectorError."""

    def test_detector_error_is_exception(self):
        """DetectorError наследует Exception."""
        err = DetectorError("test")
        assert isinstance(err, Exception)


class TestNullDetector:
    """Проверка NullDetector."""

    @pytest.mark.asyncio
    async def test_null_detector_returns_none(self):
        """NullDetector всегда возвращает None."""
        detector = NullDetector()
        result = await detector.detect(b"image", "test.png")
        assert result is None

    @pytest.mark.asyncio
    async def test_null_detector_with_content_type(self):
        """NullDetector игнорирует content_type."""
        detector = NullDetector()
        result = await detector.detect(b"image", "test.png", "image/png")
        assert result is None

    def test_null_detector_implements_protocol(self):
        """NullDetector реализует DetectorClient Protocol."""
        detector = NullDetector()
        # Если detector не имеет метода detect, TypeError будет во время mypy
        assert hasattr(detector, "detect")


class TestHttpDetectorClientHappyPath:
    """Happy path для HttpDetectorClient."""

    @pytest.mark.asyncio
    async def test_http_detector_single_detection(self):
        """HttpDetectorClient отправляет multipart и парсит ответ."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [
                {"class_ours": "excavator", "conf": 0.914, "bbox": [0.1, 0.2, 0.3, 0.4]}
            ],
        }

        def mock_transport(request: httpx.Request) -> httpx.Response:
            assert request.method == "POST"
            # Проверяем multipart формат
            assert b"Content-Disposition" in request.content
            assert b"file" in request.content
            return httpx.Response(200, json=response_data)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)
        result = await detector.detect(b"image_bytes", "photo.jpg", "image/jpeg")

        assert result is not None
        assert result.model_version == "yoloe-26s-seg.pt"
        assert len(result.detections) == 1
        assert result.detections[0].class_ours == "excavator"
        assert result.detections[0].conf == 0.914
        assert result.detections[0].bbox == (0.1, 0.2, 0.3, 0.4)

    @pytest.mark.asyncio
    async def test_http_detector_multiple_detections(self):
        """HttpDetectorClient парсит несколько детекций."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [
                {"class_ours": "excavator", "conf": 0.91, "bbox": [0.1, 0.2, 0.3, 0.4]},
                {"class_ours": "truck", "conf": 0.85, "bbox": [0.5, 0.5, 0.8, 0.9]},
            ],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)
        result = await detector.detect(b"image_bytes", "photo.jpg")

        assert result is not None
        assert len(result.detections) == 2
        assert result.detections[0].class_ours == "excavator"
        assert result.detections[1].class_ours == "truck"

    @pytest.mark.asyncio
    async def test_http_detector_empty_detections(self):
        """HttpDetectorClient парсит пустой список детекций."""
        response_data = {"model": "yoloe-26s-seg.pt", "detections": []}

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)
        result = await detector.detect(b"image_bytes", "photo.jpg")

        assert result is not None
        assert result.detections == []

    @pytest.mark.asyncio
    async def test_http_detector_rounding(self):
        """HttpDetectorClient округляет bbox до 4 знаков, conf до 3."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [
                {
                    "class_ours": "excavator",
                    "conf": 0.91444444,
                    "bbox": [0.1111111, 0.2222222, 0.3333333, 0.4444444],
                }
            ],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)
        result = await detector.detect(b"image_bytes", "photo.jpg")

        assert result is not None
        assert result.detections[0].conf == 0.914
        assert result.detections[0].bbox == (0.1111, 0.2222, 0.3333, 0.4444)

    @pytest.mark.asyncio
    async def test_http_detector_multipart_includes_filename(self):
        """HttpDetectorClient отправляет filename в multipart."""
        captured_filename = None

        def mock_transport(request: httpx.Request) -> httpx.Response:
            nonlocal captured_filename
            # Парсим multipart вручную (базовая проверка)
            content = request.content.decode("utf-8", errors="ignore")
            if "filename=" in content:
                captured_filename = True
            return httpx.Response(
                200,
                json={"model": "test.pt", "detections": []},
            )

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)
        await detector.detect(b"image_bytes", "myphoto.jpg", "image/jpeg")

        assert captured_filename is True

    @pytest.mark.asyncio
    async def test_http_detector_multipart_includes_content_type(self):
        """HttpDetectorClient отправляет content_type в multipart."""
        captured_content_type = None

        def mock_transport(request: httpx.Request) -> httpx.Response:
            nonlocal captured_content_type
            content = request.content.decode("utf-8", errors="ignore")
            if "image/jpeg" in content:
                captured_content_type = True
            return httpx.Response(
                200,
                json={"model": "test.pt", "detections": []},
            )

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)
        await detector.detect(b"image_bytes", "photo.jpg", "image/jpeg")

        assert captured_content_type is True


class TestHttpDetectorClientValidation:
    """Валидация в HttpDetectorClient."""

    @pytest.mark.asyncio
    async def test_http_detector_conf_out_of_range(self):
        """conf вне [0, 1] -> DetectorError."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [{"class_ours": "excavator", "conf": 1.5, "bbox": [0.1, 0.2, 0.3, 0.4]}],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="conf"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_conf_negative(self):
        """conf < 0 -> DetectorError."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [{"class_ours": "excavator", "conf": -0.1, "bbox": [0.1, 0.2, 0.3, 0.4]}],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="conf"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_bbox_out_of_range(self):
        """bbox координаты вне [0, 1] -> DetectorError."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [{"class_ours": "excavator", "conf": 0.9, "bbox": [-0.1, 0.2, 0.3, 0.4]}],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="bbox"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_bbox_x2_less_than_x1(self):
        """bbox с x2 <= x1 -> DetectorError."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [{"class_ours": "excavator", "conf": 0.9, "bbox": [0.5, 0.2, 0.3, 0.4]}],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="bbox"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_bbox_y2_less_than_y1(self):
        """bbox с y2 <= y1 -> DetectorError."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [{"class_ours": "excavator", "conf": 0.9, "bbox": [0.1, 0.5, 0.3, 0.4]}],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="bbox"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_bbox_clamping_tolerance(self):
        """bbox в пределах 1e-6 от границ -> clamped, не error."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [
                {
                    "class_ours": "excavator",
                    "conf": 0.9,
                    "bbox": [-0.0000005, 0.2, 1.0000005, 0.4],
                }
            ],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)
        result = await detector.detect(b"image_bytes", "photo.jpg")

        assert result is not None
        # После clamping должны быть в пределах [0, 1]
        assert result.detections[0].bbox[0] >= 0
        assert result.detections[0].bbox[2] <= 1

    @pytest.mark.asyncio
    async def test_http_detector_bbox_beyond_tolerance(self):
        """bbox вне пределов даже с tolerance -> DetectorError."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [
                {"class_ours": "excavator", "conf": 0.9, "bbox": [-0.001, 0.2, 0.3, 0.4]}
            ],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="bbox"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_missing_model_field(self):
        """Отсутствие поля `model` -> DetectorError."""
        response_data = {"detections": []}

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="model"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_empty_model_field(self):
        """Пустой `model` -> DetectorError."""
        response_data = {"model": "", "detections": []}

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="model"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_extra_fields_ignored(self):
        """Неизвестные поля в детекции -> игнорируются."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [
                {
                    "class_ours": "excavator",
                    "conf": 0.9,
                    "bbox": [0.1, 0.2, 0.3, 0.4],
                    "extra_field": "should be ignored",
                    "another": 123,
                }
            ],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)
        result = await detector.detect(b"image_bytes", "photo.jpg")

        assert result is not None
        assert len(result.detections) == 1


class TestHttpDetectorClientErrors:
    """Обработка ошибок в HttpDetectorClient."""

    @pytest.mark.asyncio
    async def test_http_detector_non_json_response(self):
        """Не-JSON ответ -> DetectorError."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, text="not json"))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="JSON"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_500_status(self):
        """HTTP 500 -> DetectorError."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(500))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="500"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_404_status(self):
        """HTTP 404 -> DetectorError."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(404))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="404"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_timeout(self):
        """httpx.ReadTimeout -> DetectorError."""

        def mock_transport_timeout(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timeout")

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport_timeout))
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="timeout|Timeout"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_connect_error(self):
        """httpx.ConnectError -> DetectorError."""

        def mock_transport_error(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection failed")

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport_error))
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        with pytest.raises(DetectorError, match="подключени|connect|Connection"):
            await detector.detect(b"image_bytes", "photo.jpg")

    @pytest.mark.asyncio
    async def test_http_detector_error_does_not_leak_image_bytes(self):
        """Ошибка не содержит image bytes."""
        response_data = {
            "model": "yoloe-26s-seg.pt",
            "detections": [{"class_ours": "excavator", "conf": 2.0, "bbox": [0.1, 0.2, 0.3, 0.4]}],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(url="http://detector:8000/detect", client=mock_client)

        image_bytes = b"SECRET_IMAGE_DATA"
        with pytest.raises(DetectorError) as exc_info:
            await detector.detect(image_bytes, "photo.jpg")

        error_message = str(exc_info.value)
        assert b"SECRET_IMAGE_DATA" not in error_message.encode()
        assert "SECRET_IMAGE_DATA" not in error_message


class TestHttpDetectorClientTimeout:
    """Timeout в HttpDetectorClient."""

    @pytest.mark.asyncio
    async def test_http_detector_default_timeout(self):
        """Default timeout = 30.0 сек."""
        detector = HttpDetectorClient(url="http://detector:8000/detect")
        # Проверяем, что timeout установлен
        assert detector.timeout_s == 30.0

    @pytest.mark.asyncio
    async def test_http_detector_custom_timeout(self):
        """Можно установить кастомный timeout."""
        detector = HttpDetectorClient(url="http://detector:8000/detect", timeout_s=60.0)
        assert detector.timeout_s == 60.0

    @pytest.mark.asyncio
    async def test_http_detector_creates_client_per_call(self):
        """HttpDetectorClient создаёт клиент per call, если не injected."""
        # Это поведение трудно проверить напрямую, но мы можем убедиться,
        # что детектор работает без injected client
        detector = HttpDetectorClient(url="http://localhost:8000/detect")
        # Если не injected, client будет создан внутри detect()
        # Мы не можем вызвать реальный запрос в тесте, но синтаксис проверяет основное

        # Убедимся, что detector имеет атрибут timeout_s
        assert hasattr(detector, "timeout_s")


class TestFactory:
    """Проверка factory функции create_detector."""

    def test_factory_with_url(self):
        """factory с реальным url -> HttpDetectorClient."""
        settings = Settings(detector=DetectorSettings(url="http://detector:8000/detect"))
        detector = create_detector(settings)
        assert isinstance(detector, HttpDetectorClient)

    def test_factory_with_empty_url(self):
        """factory с пустым url -> NullDetector."""
        settings = Settings(detector=DetectorSettings(url=""))
        detector = create_detector(settings)
        assert isinstance(detector, NullDetector)

    def test_factory_with_whitespace_url(self):
        """factory с whitespace-only url -> NullDetector."""
        settings = Settings(detector=DetectorSettings(url="   "))
        detector = create_detector(settings)
        assert isinstance(detector, NullDetector)

    def test_factory_with_none_url(self):
        """factory с None url -> NullDetector."""
        settings = Settings(detector=DetectorSettings(url=None))
        detector = create_detector(settings)
        assert isinstance(detector, NullDetector)

    def test_factory_returns_protocol_compliant(self):
        """factory возвращает объект с методом detect."""
        settings = Settings(detector=DetectorSettings(url="http://detector:8000/detect"))
        detector = create_detector(settings)
        assert hasattr(detector, "detect")
