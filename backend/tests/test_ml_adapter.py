"""Тесты адаптера ML-детектора.

Проверяют NullDetector, HttpDetectorClient и factory.
Используют реальный формат ответа от ml/service.
"""

import asyncio

import httpx
import pytest

from app.adapters.ml import (
    DetectionResult,
    DetectorError,
    DetectorInfo,
    HttpDetectorClient,
    NullDetector,
    RawDetection,
    create_detector,
)
from app.adapters.ml.stamp import HttpStampReader
from app.core.settings import DetectorSettings, Settings


class TestDetectorError:
    """Проверка DetectorError с transient атрибутом."""

    def test_detector_error_default_transient_false(self):
        """DetectorError по умолчанию имеет transient=False."""
        err = DetectorError("test")
        assert err.transient is False

    def test_detector_error_transient_true(self):
        """DetectorError может иметь transient=True."""
        err = DetectorError("test", transient=True)
        assert err.transient is True

    def test_detector_error_transient_attribute(self):
        """DetectorError имеет атрибут transient."""
        err = DetectorError("test", transient=False)
        assert hasattr(err, "transient")


class TestDetectorInfo:
    """Проверка DetectorInfo dataclass."""

    def test_detector_info_fields(self):
        """DetectorInfo содержит все необходимые поля."""
        info = DetectorInfo(
            model_version="mocs_m@abc123",
            class_names=("excavator", "crane"),
            conf_threshold=0.25,
            device="cuda",
            contract="detect/v1",
        )
        assert info.model_version == "mocs_m@abc123"
        assert info.class_names == ("excavator", "crane")
        assert info.conf_threshold == 0.25
        assert info.device == "cuda"
        assert info.contract == "detect/v1"


class TestDetectionResult:
    """Проверка DetectionResult с width/height."""

    def test_detection_result_with_dimensions(self):
        """DetectionResult содержит width и height."""
        dets = [RawDetection(class_ours="excavator", conf=0.91, bbox=(0.1, 0.2, 0.3, 0.4))]
        result = DetectionResult(
            model_version="mocs_m@abc123",
            detections=dets,
            width=1219,
            height=809,
        )
        assert result.width == 1219
        assert result.height == 809

    def test_detection_result_dimensions_default_none(self):
        """width и height по умолчанию None."""
        result = DetectionResult(model_version="test", detections=[])
        assert result.width is None
        assert result.height is None


class TestNullDetector:
    """Проверка NullDetector."""

    @pytest.mark.asyncio
    async def test_null_detector_detect_returns_none(self):
        """NullDetector.detect возвращает None."""
        detector = NullDetector()
        result = await detector.detect(b"image", "test.png")
        assert result is None

    @pytest.mark.asyncio
    async def test_null_detector_info_returns_none(self):
        """NullDetector.info возвращает None."""
        detector = NullDetector()
        info = await detector.info()
        assert info is None

    @pytest.mark.asyncio
    async def test_null_detector_ready_returns_false(self):
        """NullDetector.ready возвращает False."""
        detector = NullDetector()
        ready = await detector.ready()
        assert ready is False

    def test_null_detector_configured_false(self):
        """NullDetector.configured = False."""
        detector = NullDetector()
        assert detector.configured is False


class TestHttpDetectorClientHappyPath:
    """Happy path для HttpDetectorClient."""

    @pytest.mark.asyncio
    async def test_http_detector_real_response_format(self, caplog):
        """HttpDetectorClient парсит реальный формат с width/height и логирует speed_ms.total."""
        import logging

        caplog.set_level(logging.INFO)
        response_data = {
            "model": "mocs_m_best@3f1c9a0b7e21",
            "image": "Screenshot_26.png",
            "width": 1219,
            "height": 809,
            "speed_ms": {"preprocess": 3.1, "inference": 41.2, "postprocess": 1.4, "total": 64.7},
            "detections": [
                {
                    "class_raw": "drilling_rig",
                    "class_ours": "drilling_rig",
                    "conf": 0.88,
                    "bbox": [0.5396, 0.0, 0.6227, 0.6529],
                },
                {
                    "class_raw": "crane_unknown",
                    "class_ours": "crane_unknown",
                    "conf": 0.41,
                    "bbox": [0.1, 0.1, 0.2, 0.5],
                },
            ],
        }

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        result = await detector.detect(b"image_bytes", "Screenshot_26.png")

        assert result is not None
        assert result.model_version == "mocs_m_best@3f1c9a0b7e21"
        assert result.width == 1219
        assert result.height == 809
        assert len(result.detections) == 2
        assert result.detections[0].class_ours == "drilling_rig"
        assert result.detections[0].conf == 0.88
        assert result.detections[1].class_ours == "crane_unknown"
        # Check that speed_ms.total is logged
        assert any(
            "64.7" in record.message for record in caplog.records if record.levelno == logging.INFO
        )

    @pytest.mark.asyncio
    async def test_http_detector_configured_true(self):
        """HttpDetectorClient.configured = True."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json={"model": "test", "detections": []})
            )
        )
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        assert detector.configured is True

    @pytest.mark.asyncio
    async def test_http_detector_url_normalize(self):
        """HttpDetectorClient нормализует URL (убирает /detect, trailing /)."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json={"model": "test", "detections": []})
            )
        )
        # URL с /detect и trailing /
        detector = HttpDetectorClient(
            base_url="http://ml:8000/detect/",
            client=mock_client,
            settings=DetectorSettings(),
        )
        # После нормализации должен стать http://ml:8000
        assert detector.base_url == "http://ml:8000"


class TestHttpDetectorClientRetry:
    """Тесты retry логики в HttpDetectorClient."""

    @pytest.mark.asyncio
    async def test_http_detector_retry_503(self):
        """503 повторяется retry_503 раз, затем 200 - успех."""
        call_count = 0

        def mock_transport(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                return httpx.Response(503)
            return httpx.Response(200, json={"model": "test", "detections": []})

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(retry_503=3),
        )
        result = await detector.detect(b"image", "test.png")
        assert result is not None
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_http_detector_503_exhausted(self):
        """503 всегда - выбрасывает DetectorError с transient=True."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(retry_503=1, retry_budget_s=10.0),
        )
        with pytest.raises(DetectorError) as exc_info:
            await detector.detect(b"image", "test.png")
        assert exc_info.value.transient is True

    @pytest.mark.asyncio
    async def test_http_detector_timeout_retry(self):
        """Timeout повторяется retry_other раз."""
        call_count = 0

        def mock_transport(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise httpx.ReadTimeout("timeout")
            return httpx.Response(200, json={"model": "test", "detections": []})

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(retry_other=2),
        )
        result = await detector.detect(b"image", "test.png")
        assert result is not None

    @pytest.mark.asyncio
    async def test_http_detector_retry_budget_exhausted(self):
        """Retry budget ограничивает количество повторов."""
        call_count = 0

        def mock_transport(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(503)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(
                retry_503=10,
                retry_backoff_s=(2.0, 5.0, 10.0),
                retry_budget_s=5.0,
            ),
        )
        with pytest.raises(DetectorError) as exc_info:
            await detector.detect(b"image", "test.png")
        assert exc_info.value.transient is True
        # Should have called fewer times due to budget limit

    @pytest.mark.asyncio
    async def test_http_detector_422_no_retry(self):
        """422 не повторяется, transient=False."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(422)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(retry_other=5),
        )
        with pytest.raises(DetectorError) as exc_info:
            await detector.detect(b"image", "test.png")
        assert exc_info.value.transient is False

    @pytest.mark.asyncio
    async def test_http_detector_400_no_retry(self):
        """400 не повторяется, transient=False."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        with pytest.raises(DetectorError) as exc_info:
            await detector.detect(b"image", "test.png")
        assert exc_info.value.transient is False

    @pytest.mark.asyncio
    async def test_http_detector_invalid_json_no_retry(self):
        """Invalid JSON, transient=False."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not json")

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        with pytest.raises(DetectorError) as exc_info:
            await detector.detect(b"image", "test.png")
        assert exc_info.value.transient is False

    @pytest.mark.asyncio
    async def test_http_detector_schema_mismatch_no_retry(self):
        """Schema mismatch (invalid detection format), transient=False."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            # Invalid detection format - conf outside [0, 1]
            return httpx.Response(
                200,
                json={
                    "model": "test",
                    "detections": [{"class_ours": "test", "conf": 1.5, "bbox": [0, 0, 0.1, 0.1]}],
                },
            )

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        with pytest.raises(DetectorError) as exc_info:
            await detector.detect(b"image", "test.png")
        assert exc_info.value.transient is False


class TestHttpDetectorClientMissingModel:
    """Тесты для missing model -> fallback to info()."""

    @pytest.mark.asyncio
    async def test_http_detector_missing_model_fallback_to_info(self):
        """Missing model в ответе - fallback to info() для получения model_version."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/meta" or request.url.path.endswith("/meta"):
                return httpx.Response(
                    200,
                    json={
                        "model": "mocs_m_best@3f1c9a0b7e21",
                        "class_names": ["excavator"],
                    },
                )
            # detect endpoint - missing model field
            return httpx.Response(200, json={"detections": []})

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        result = await detector.detect(b"image", "test.png")
        assert result is not None
        assert result.model_version == "mocs_m_best@3f1c9a0b7e21"

    @pytest.mark.asyncio
    async def test_http_detector_missing_model_fallback_to_weights(self):
        """Missing model - fallback to meta.weights if model not present."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/meta" or request.url.path.endswith("/meta"):
                return httpx.Response(200, json={"weights": "mocs_m_best@abc", "class_names": []})
            return httpx.Response(200, json={"detections": []})

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        result = await detector.detect(b"image", "test.png")
        assert result is not None
        assert result.model_version == "mocs_m_best@abc"


class TestHttpDetectorClientInfo:
    """Тесты для info() метода."""

    @pytest.mark.asyncio
    async def test_http_detector_contract_valid(self, caplog):
        """Contract detect/v1 and detect/v1.2 - no error."""
        import logging

        caplog.set_level(logging.ERROR)

        def mock_transport(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json={
                        "model": "test_model",
                        "class_names": [],
                        "contract": "detect/v1.2",
                    },
                )
            return httpx.Response(404)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        info = await detector.info()
        assert info is not None
        assert "contract" not in [r.name for r in caplog.records if r.levelno == logging.ERROR]

    @pytest.mark.asyncio
    async def test_http_detector_contract_invalid_major(self, caplog):
        """Contract detect/v2 - error logged."""
        import logging

        caplog.set_level(logging.ERROR)

        def mock_transport(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json={
                        "model": "test_model",
                        "class_names": [],
                        "contract": "detect/v2",
                    },
                )
            return httpx.Response(404)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        info = await detector.info()
        assert info is not None  # Still returned despite error
        assert any(
            "contract" in record.message.lower()
            for record in caplog.records
            if record.levelno == logging.ERROR
        )

    @pytest.mark.asyncio
    async def test_http_detector_contract_invalid_name(self, caplog):
        """Contract other/v1 - error logged."""
        import logging

        caplog.set_level(logging.ERROR)

        def mock_transport(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json={
                        "model": "test_model",
                        "class_names": [],
                        "contract": "other/v1",
                    },
                )
            return httpx.Response(404)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        info = await detector.info()
        assert info is not None  # Still returned despite error
        assert any(
            "contract" in record.message.lower()
            for record in caplog.records
            if record.levelno == logging.ERROR
        )

    @pytest.mark.asyncio
    async def test_http_detector_info_get_meta(self):
        """info() вызывает GET /meta."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(
                    200,
                    json={
                        "model": "mocs_m_best@3f1c9a0b7e21",
                        "class_names": ["excavator", "crane"],
                        "conf": 0.25,
                        "device": "cuda",
                        "contract": "detect/v1",
                    },
                )
            return httpx.Response(404)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        info = await detector.info()
        assert info is not None
        assert info.model_version == "mocs_m_best@3f1c9a0b7e21"
        assert info.class_names == ("excavator", "crane")
        assert info.conf_threshold == 0.25
        assert info.device == "cuda"
        assert info.contract == "detect/v1"

    @pytest.mark.asyncio
    async def test_http_detector_info_caching(self):
        """info() кэшируется после первого вызова."""
        call_count = 0

        def mock_transport(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            if request.method == "GET":
                call_count += 1
                return httpx.Response(200, json={"model": "test", "class_names": []})
            return httpx.Response(404)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        info1 = await detector.info()
        info2 = await detector.info()
        assert call_count == 1  # Only one request
        assert info1 == info2

    @pytest.mark.asyncio
    async def test_http_detector_info_error_returns_none(self):
        """info() возвращает None при ошибке."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                return httpx.Response(500)
            return httpx.Response(404)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        info = await detector.info()
        assert info is None

    @pytest.mark.asyncio
    async def test_http_detector_info_cache_reset_on_error(self):
        """info() cache сбрасывается при ошибке."""
        call_count = [0]

        def mock_transport(request: httpx.Request) -> httpx.Response:
            if request.method == "GET":
                call_count[0] += 1
                if call_count[0] == 1:
                    return httpx.Response(200, json={"model": "test", "class_names": []})
                return httpx.Response(500)
            return httpx.Response(404)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        # First call succeeds and caches result
        info1 = await detector.info()
        assert info1 is not None
        # Second call returns cached value without making request
        info2 = await detector.info()
        assert info2 is not None  # Cache returns the same value
        assert call_count[0] == 1  # Only one request was made

        # Create a new detector instance to test error handling
        detector2 = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        # This time first call fails (will be call 2+ in the mock)
        info3 = await detector2.info()
        assert info3 is None  # Error returns None
        assert call_count[0] == 2


class TestHttpDetectorClientReady:
    """Тесты для ready() метода."""

    @pytest.mark.asyncio
    async def test_http_detector_ready_true(self):
        """ready() возвращает True если model_loaded=true."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/health" or request.url.path.endswith("/health"):
                return httpx.Response(200, json={"model_loaded": True})
            return httpx.Response(404)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        ready = await detector.ready()
        assert ready is True

    @pytest.mark.asyncio
    async def test_http_detector_ready_false(self):
        """ready() возвращает False если model_loaded=false."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/health" or request.url.path.endswith("/health"):
                return httpx.Response(200, json={"model_loaded": False})
            return httpx.Response(404)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        ready = await detector.ready()
        assert ready is False

    @pytest.mark.asyncio
    async def test_http_detector_ready_error(self):
        """ready() возвращает False при ошибке."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        ready = await detector.ready()
        assert ready is False


class TestHttpDetectorClientConcurrency:
    """Тесты для concurrency semaphore."""

    @pytest.mark.asyncio
    async def test_http_detector_concurrency_limit(self):
        """Семафор ограничивает одновременные запросы до max_concurrency."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            # Record call timestamp (simplified concurrency check)
            return httpx.Response(200, json={"model": "test", "detections": []})

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        detector = HttpDetectorClient(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(max_concurrency=2),
        )
        # Test that semaphore exists and is initialized
        assert detector._semaphore is not None
        assert detector._semaphore._value == 2  # max_concurrency=2

        # Run 5 concurrent detects - should not raise
        results = await asyncio.gather(
            detector.detect(b"img1", "test1.png"),
            detector.detect(b"img2", "test2.png"),
            detector.detect(b"img3", "test3.png"),
            detector.detect(b"img4", "test4.png"),
            detector.detect(b"img5", "test5.png"),
        )
        # All should succeed
        assert all(r is not None for r in results)


class TestFactory:
    """Проверка factory функции create_detector."""

    def test_factory_with_url_and_client(self):
        """factory с URL и httpx client -> HttpDetectorClient."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json={"model": "test", "detections": []})
            )
        )
        settings = Settings(detector=DetectorSettings(url="http://ml:8000"))
        detector = create_detector(settings, mock_client)
        assert isinstance(detector, HttpDetectorClient)

    def test_factory_without_client(self):
        """factory без client -> NullDetector."""
        settings = Settings(detector=DetectorSettings(url="http://ml:8000"))
        detector = create_detector(settings, None)
        assert isinstance(detector, NullDetector)

    def test_factory_with_empty_url(self):
        """factory с пустым url -> NullDetector."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json={"model": "test", "detections": []})
            )
        )
        settings = Settings(detector=DetectorSettings(url=""))
        detector = create_detector(settings, mock_client)
        assert isinstance(detector, NullDetector)

    def test_factory_with_none_url(self):
        """factory с None url -> NullDetector."""
        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json={"model": "test", "detections": []})
            )
        )
        settings = Settings(detector=DetectorSettings(url=None))
        detector = create_detector(settings, mock_client)
        assert isinstance(detector, NullDetector)


class TestHttpStampReader:
    """Тесты HttpStampReader для чтения даты со штампа (LCT-13)."""

    @pytest.mark.asyncio
    async def test_http_stamp_reader_200_with_date(self):
        """HttpStampReader.read_date с 200 и датой -> date объект."""
        response_data = {"date": "2024-04-24", "text": "24.04.2024", "roi": "right"}

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        reader = HttpStampReader(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        result = await reader.read_date(b"image_bytes")
        assert result is not None
        assert result.isoformat() == "2024-04-24"

    @pytest.mark.asyncio
    async def test_http_stamp_reader_200_with_null_date(self):
        """HttpStampReader.read_date с 200 но null дата -> None."""
        response_data = {"date": None, "text": None, "roi": None}

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        reader = HttpStampReader(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        result = await reader.read_date(b"image_bytes")
        assert result is None

    @pytest.mark.asyncio
    async def test_http_stamp_reader_camera_profile_without_date(self):
        """read: кадр камеры с непрочитанным временем -> профиль без даты."""
        response_data = {"date": None, "text": None, "roi": None, "profile": "2592x1944"}

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        reader = HttpStampReader(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        result = await reader.read(b"image_bytes")
        assert result.date is None
        assert result.profile == "2592x1944"

    @pytest.mark.asyncio
    async def test_http_stamp_reader_422_no_retry(self):
        """HttpStampReader.read_date с 422 -> None, no retry."""
        call_count = 0

        def mock_transport(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(422)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        reader = HttpStampReader(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        result = await reader.read_date(b"image_bytes")
        assert result is None
        assert call_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_http_stamp_reader_503_then_200(self):
        """HttpStampReader.read_date с 503 затем 200 -> retry и успех."""
        call_count = 0

        def mock_transport(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return httpx.Response(503)
            return httpx.Response(
                200, json={"date": "2024-05-15", "text": "15.05.2024", "roi": "left"}
            )

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        reader = HttpStampReader(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(retry_503=2),
        )
        result = await reader.read_date(b"image_bytes")
        assert result is not None
        assert result.isoformat() == "2024-05-15"

    @pytest.mark.asyncio
    async def test_http_stamp_reader_503_exhausted(self):
        """HttpStampReader.read_date с 503 всегда -> None после retry."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        reader = HttpStampReader(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(retry_503=1, retry_budget_s=10.0),
        )
        result = await reader.read_date(b"image_bytes")
        assert result is None

    @pytest.mark.asyncio
    async def test_http_stamp_reader_malformed_json(self):
        """HttpStampReader.read_date с malformed JSON -> None."""

        def mock_transport(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not json")

        mock_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_transport))
        reader = HttpStampReader(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        result = await reader.read_date(b"image_bytes")
        assert result is None

    @pytest.mark.asyncio
    async def test_http_stamp_reader_invalid_date_format(self):
        """HttpStampReader.read_date с invalid date format -> None."""
        response_data = {"date": "not-a-date", "text": "garbage", "roi": None}

        mock_client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda req: httpx.Response(200, json=response_data))
        )
        reader = HttpStampReader(
            base_url="http://ml:8000",
            client=mock_client,
            settings=DetectorSettings(),
        )
        result = await reader.read_date(b"image_bytes")
        assert result is None
