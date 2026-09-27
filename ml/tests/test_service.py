"""Тесты ML-сервиса: detector.py и app.py.

Эти тесты не требуют torch/ultralytics/реальных весов.
Используются временные файлы с фальшивыми весами и monkeypatch для модели.
"""

import hashlib
import io
import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from service.app import app
from service.detector import CONTRACT, Detector


class FakeModel:
    """Имитация ultralytics YOLO с минимальным интерфейсом."""

    def __init__(self, names_dict: dict[int, str]):
        self.names = names_dict

    def predict(self, source, **kwargs):
        """Возвращает объект, похожий на ultralytics Result."""
        # Если источник — PIL Image, берём размер из неё
        if isinstance(source, Image.Image):
            width, height = source.size
        else:
            width, height = 640, 480

        result = MagicMock()
        result.orig_shape = (height, width)
        result.names = self.names
        result.speed = {"preprocess": 1.0, "inference": 5.0, "postprocess": 0.5}

        # Пустой результат по умолчанию
        result.boxes = MagicMock()
        result.boxes.cls = MagicMock()
        result.boxes.cls.tolist = MagicMock(return_value=[])
        result.boxes.conf = MagicMock()
        result.boxes.conf.tolist = MagicMock(return_value=[])
        result.boxes.xyxyn = MagicMock()
        result.boxes.xyxyn.tolist = MagicMock(return_value=[])

        return [result]


class TestDetector:
    """Юнит-тесты для Detector."""

    def test_detector_weights_sha256_computed(self):
        """При инициализации вычисляется weights_sha256."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            fake_bytes = b"fake_weights_content"
            f.write(fake_bytes)
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)
            # Монкипатч _model после инициализации
            detector._model = FakeModel({0: "crane", 1: "excavator"})

            # Проверяем, что weights_sha256 вычислен
            assert hasattr(detector, "weights_sha256")
            expected_sha = hashlib.sha256(fake_bytes).hexdigest()
            assert detector.weights_sha256 == expected_sha
        finally:
            temp_path.unlink()

    def test_detector_model_id_format(self):
        """model_id имеет формат stem@sha12."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"test_weights")
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)
            detector._model = FakeModel({0: "crane"})

            model_id = detector.model_id
            # Формат: <stem>@<12 hex chars>
            parts = model_id.split("@")
            assert len(parts) == 2
            assert parts[0] == temp_path.stem
            assert len(parts[1]) == 12
            # Проверяем, что это hex
            int(parts[1], 16)
        finally:
            temp_path.unlink()

    def test_detector_class_names_ordered_by_id(self):
        """class_names возвращает список упорядоченный по id класса."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"test_weights")
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)
            # names — это dict id -> name
            detector._model = FakeModel({0: "crane", 1: "excavator", 2: "truck"})

            class_names = detector.class_names
            assert class_names == ["crane", "excavator", "truck"]
        finally:
            temp_path.unlink()

    def test_detector_exif_transpose(self):
        """predict_bytes: EXIF orientation 6 меняет ширину и высоту."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"test_weights")
            temp_path = Path(f.name)

        try:
            # Создаём JPEG с EXIF ориентацией 6
            # Ориентация 6 означает повернуть на 90 град против часовой (width <-> height)
            img_original = Image.new("RGB", (40, 20), color="red")
            exif = Image.Exif()
            exif[0x0112] = 6  # Orientation tag
            buf = io.BytesIO()
            img_original.save(buf, "JPEG", exif=exif)
            jpeg_bytes = buf.getvalue()

            # Создаём фальшивую модель, которая записывает размер
            class TrackerFakeModel(FakeModel):
                def __init__(self, names_dict):
                    super().__init__(names_dict)
                    self.last_image_size = None

                def predict(self, source, **kwargs):
                    if isinstance(source, Image.Image):
                        self.last_image_size = source.size
                        width, height = source.size
                    else:
                        width, height = 640, 480
                    result = MagicMock()
                    result.orig_shape = (height, width)
                    result.names = self.names
                    result.speed = {"preprocess": 1.0, "inference": 5.0, "postprocess": 0.5}
                    result.boxes = MagicMock()
                    result.boxes.cls = MagicMock()
                    result.boxes.cls.tolist = MagicMock(return_value=[])
                    result.boxes.conf = MagicMock()
                    result.boxes.conf.tolist = MagicMock(return_value=[])
                    result.boxes.xyxyn = MagicMock()
                    result.boxes.xyxyn.tolist = MagicMock(return_value=[])
                    return [result]

            detector = Detector(weights=temp_path)
            fake_model = TrackerFakeModel({0: "crane"})
            detector._model = fake_model

            result = detector.predict_bytes(jpeg_bytes)
            # После EXIF transpose, ширина и высота должны быть поменяны
            # (40, 20) -> после rotate на 90 -> (20, 40)
            assert result["width"] == 20, f"Expected width 20, got {result['width']}"
            assert result["height"] == 40, f"Expected height 40, got {result['height']}"
        finally:
            temp_path.unlink()

    def test_detector_meta_includes_required_fields(self):
        """meta() возвращает contract, weights_sha256, model, class_names."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"test_weights")
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)
            detector._model = FakeModel({0: "crane", 1: "excavator"})

            meta = detector.meta()
            assert meta["contract"] == "detect/v1"
            assert "weights_sha256" in meta
            assert "model" in meta
            assert "class_names" in meta
            assert meta["class_names"] == ["crane", "excavator"]
        finally:
            temp_path.unlink()

    def test_detector_predict_result_has_model_key(self):
        """_predict результат содержит ключ 'model' с model_id."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"test_weights")
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)
            detector._model = FakeModel({0: "crane"})

            # Создаём реальное PNG изображение
            img = Image.new("RGB", (100, 100))
            buf = io.BytesIO()
            img.save(buf, "PNG")
            png_bytes = buf.getvalue()

            result = detector.predict_bytes(png_bytes, name="test.jpg")
            # Проверяем, что 'model' есть в результате
            assert "model" in result
            assert result["model"] == detector.model_id
        finally:
            temp_path.unlink()

    def test_detector_detections_sorted_by_confidence_desc(self):
        """Детекции сортируются по conf в убывающем порядке."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"test_weights")
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)

            # Создаём модель с детекциями разной уверенности
            class DetectorFakeModel(FakeModel):
                def predict(self, source, **kwargs):
                    result = MagicMock()
                    result.orig_shape = (480, 640)
                    result.names = self.names
                    result.speed = {"preprocess": 1.0, "inference": 5.0, "postprocess": 0.5}
                    result.boxes = MagicMock()
                    # Порядок: низкая, высокая, средняя уверенность
                    result.boxes.cls = MagicMock()
                    result.boxes.cls.tolist = MagicMock(return_value=[0, 1, 0])
                    result.boxes.conf = MagicMock()
                    result.boxes.conf.tolist = MagicMock(return_value=[0.5, 0.9, 0.7])
                    result.boxes.xyxyn = MagicMock()
                    result.boxes.xyxyn.tolist = MagicMock(return_value=[
                        [0.1, 0.1, 0.3, 0.3],
                        [0.4, 0.4, 0.6, 0.6],
                        [0.2, 0.2, 0.4, 0.4],
                    ])
                    return [result]

            detector._model = DetectorFakeModel({0: "crane", 1: "excavator"})

            # Создаём реальное PNG изображение
            img = Image.new("RGB", (640, 480))
            buf = io.BytesIO()
            img.save(buf, "PNG")
            png_bytes = buf.getvalue()

            result = detector.predict_bytes(png_bytes)

            confs = [d["conf"] for d in result["detections"]]
            # Должны быть упорядочены по убыванию
            assert confs == sorted(confs, reverse=True)
            assert confs == [0.9, 0.7, 0.5]
        finally:
            temp_path.unlink()


class TestApp:
    """Тесты для app.py."""

    def create_test_client(self):
        """Создаёт TestClient без входа в lifespan."""
        return TestClient(app)

    def test_detect_endpoint_returns_model_field(self):
        """POST /detect возвращает поле 'model'."""
        client = self.create_test_client()

        # Создаём фальшивый детектор
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"fake_weights")
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)
            detector._model = FakeModel({0: "crane"})

            # Устанавливаем фальшивый детектор прямо в app
            import service.app
            service.app._detector = detector

            # Создаём простой PNG (1x1 пиксель)
            img = Image.new("RGB", (1, 1))
            buf = io.BytesIO()
            img.save(buf, "PNG")
            png_bytes = buf.getvalue()

            response = client.post("/detect", files={"file": ("test.png", png_bytes)})
            assert response.status_code == 200
            data = response.json()
            assert "model" in data
            assert data["width"] == 1
            assert data["height"] == 1
            assert "detections" in data
        finally:
            temp_path.unlink()
            service.app._detector = None

    def test_detect_empty_file_returns_400(self):
        """POST /detect с пустым файлом возвращает 400."""
        client = self.create_test_client()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"fake_weights")
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)
            detector._model = FakeModel({0: "crane"})

            import service.app
            service.app._detector = detector

            response = client.post("/detect", files={"file": ("empty.png", b"")})
            assert response.status_code == 400
        finally:
            temp_path.unlink()
            service.app._detector = None

    def test_detect_oversized_file_returns_413(self):
        """POST /detect с файлом больше MAX_BYTES возвращает 413."""
        client = self.create_test_client()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"fake_weights")
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)
            detector._model = FakeModel({0: "crane"})

            import service.app
            original_max = service.app.MAX_BYTES
            service.app._detector = detector
            service.app.MAX_BYTES = 100  # Очень маленький лимит

            # Файл больше лимита
            response = client.post("/detect", files={"file": ("big.png", b"x" * 200)})
            assert response.status_code == 413

            service.app.MAX_BYTES = original_max
        finally:
            temp_path.unlink()
            service.app._detector = None

    def test_detect_invalid_image_returns_422(self):
        """POST /detect с невалидным файлом возвращает 422."""
        client = self.create_test_client()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"fake_weights")
            temp_path = Path(f.name)

        try:
            # Используем модель, которая выбросит исключение при predict
            class FailingFakeModel(FakeModel):
                def predict(self, source, **kwargs):
                    raise ValueError("Битый файл")

            detector = Detector(weights=temp_path)
            detector._model = FailingFakeModel({0: "crane"})

            import service.app
            service.app._detector = detector

            response = client.post("/detect", files={"file": ("bad.jpg", b"not_a_real_image")})
            assert response.status_code == 422
        finally:
            temp_path.unlink()
            service.app._detector = None

    def test_detect_no_detector_returns_503(self):
        """POST /detect при _detector=None возвращает 503."""
        client = self.create_test_client()

        import service.app
        service.app._detector = None

        img = Image.new("RGB", (1, 1))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        png_bytes = buf.getvalue()

        response = client.post("/detect", files={"file": ("test.png", png_bytes)})
        assert response.status_code == 503

    def test_meta_endpoint_returns_required_fields(self):
        """GET /meta возвращает contract, class_names, model, weights_sha256."""
        client = self.create_test_client()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"fake_weights")
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)
            detector._model = FakeModel({0: "crane", 1: "excavator"})

            import service.app
            service.app._detector = detector

            response = client.get("/meta")
            assert response.status_code == 200
            data = response.json()

            assert "contract" in data
            assert data["contract"] == "detect/v1"
            assert "class_names" in data
            assert "model" in data
            assert "weights_sha256" in data
            assert data["class_names"] == ["crane", "excavator"]
        finally:
            temp_path.unlink()
            service.app._detector = None

    def test_health_endpoint(self):
        """GET /health возвращает статус."""
        client = self.create_test_client()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"fake_weights")
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)
            detector._model = FakeModel({0: "crane"})

            import service.app
            service.app._detector = detector

            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "model_loaded" in data
            assert data["model_loaded"] is True
        finally:
            temp_path.unlink()
            service.app._detector = None

    def test_meta_includes_stamp_flag(self):
        """GET /meta возвращает stamp: True."""
        client = self.create_test_client()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
            f.write(b"fake_weights")
            temp_path = Path(f.name)

        try:
            detector = Detector(weights=temp_path)
            detector._model = FakeModel({0: "crane"})

            import service.app
            service.app._detector = detector

            response = client.get("/meta")
            assert response.status_code == 200
            data = response.json()
            assert "stamp" in data
            assert data["stamp"] is True
        finally:
            temp_path.unlink()
            service.app._detector = None

    def test_stamp_empty_file_returns_400(self):
        """POST /stamp с пустым файлом возвращает 400."""
        client = self.create_test_client()

        response = client.post("/stamp", files={"file": ("empty.png", b"")})
        assert response.status_code == 400

    def test_stamp_oversized_file_returns_413(self):
        """POST /stamp с файлом больше MAX_BYTES возвращает 413."""
        client = self.create_test_client()

        import service.app
        original_max = service.app.MAX_BYTES
        service.app.MAX_BYTES = 100  # Очень маленький лимит

        # Файл больше лимита
        response = client.post("/stamp", files={"file": ("big.png", b"x" * 200)})
        assert response.status_code == 413

        service.app.MAX_BYTES = original_max

    def test_stamp_with_synthetic_image_returns_null_date(self):
        """POST /stamp с синтетическим кадром (без штампа) возвращает null date."""
        client = self.create_test_client()

        # Создаём простой PNG без штампа
        img = Image.new("RGB", (640, 480), color="blue")
        buf = io.BytesIO()
        img.save(buf, "PNG")
        png_bytes = buf.getvalue()

        response = client.post("/stamp", files={"file": ("test.png", png_bytes)})
        assert response.status_code == 200
        data = response.json()
        assert "date" in data
        assert "text" in data
        assert "roi" in data
        assert data["date"] is None


class TestContract:
    """Тест для констант контракта."""

    def test_contract_constant(self):
        """CONTRACT константа имеет правильное значение."""
        assert CONTRACT == "detect/v1"
