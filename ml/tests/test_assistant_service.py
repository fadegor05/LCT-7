"""Тесты для провайдера LLM и статуса ассистента в /meta."""

import io
import json
import socket
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest
from fastapi.testclient import TestClient

from service.app import app
from service.detector import Detector


class FakeModel:
    """Имитация ultralytics YOLO с минимальным интерфейсом."""

    def __init__(self, names_dict: dict[int, str]):
        self.names = names_dict

    def predict(self, source, **kwargs):
        """Возвращает объект, похожий на ultralytics Result."""
        from PIL import Image
        if isinstance(source, Image.Image):
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


@pytest.fixture
def ready_detector(tmp_path):
    """Детектор с FakeModel, готовый для endpoint-тестов."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pt") as f:
        f.write(b"fake_weights")
        temp_path = Path(f.name)

    try:
        detector = Detector(weights=temp_path)
        detector._model = FakeModel({0: "crane"})

        import service.app
        service.app._detector = detector

        yield detector
    finally:
        temp_path.unlink()
        service.app._detector = None


class TestLLMConfig:
    """Тесты для llm_config()."""

    def test_llm_config_none_если_ничего_не_задано(self, llm_env):
        """llm_config() возвращает None при отсутствии переменных."""
        import ask_report
        config = ask_report.llm_config()
        assert config is None

    def test_llm_config_все_три_заданы(self, llm_env):
        """llm_config() возвращает LLMConfig при заданных трёх переменных."""
        llm_env(base_url="https://x/v1", api_key="k", model="m")
        import ask_report
        config = ask_report.llm_config()
        assert config is not None
        assert config.base_url == "https://x/v1"
        assert config.api_key == "k"
        assert config.model == "m"

    def test_llm_config_пробелы_и_пусто_считаются_незаданными(self, llm_env):
        """llm_config() возвращает None при пробелах или пустых значениях."""
        import ask_report

        # api_key с пробелами
        llm_env(base_url="https://x/v1", api_key="   ", model="m")
        config = ask_report.llm_config()
        assert config is None

        # api_key пусто
        llm_env(base_url="https://x/v1", api_key="", model="m")
        config = ask_report.llm_config()
        assert config is None

    def test_llm_config_читает_ml_env_файл(self, llm_env, tmp_path):
        """llm_config() читает значения из ml/.env."""
        # Пишем .env файл
        env_file = tmp_path / ".env"
        env_file.write_text(
            "LLM_BASE_URL=https://env/v1\n"
            "LLM_API_KEY=key-from-env\n"
            "LLM_MODEL=model-from-env\n"
        )

        # Не устанавливаем переменные окружения
        llm_env()

        import ask_report
        config = ask_report.llm_config()
        assert config is not None
        assert config.base_url == "https://env/v1"
        assert config.api_key == "key-from-env"
        assert config.model == "model-from-env"


class TestDescribeLLMError:
    """Тесты для describe_llm_error()."""

    def test_http_error_401(self):
        """describe_llm_error(HTTPError) возвращает HTTP код."""
        import ask_report
        exc = HTTPError("url", 401, "msg", {}, None)
        result = ask_report.describe_llm_error(exc)
        assert result == "HTTP 401"

    def test_timeout_error(self):
        """describe_llm_error(TimeoutError) возвращает 'тайм-аут'."""
        import ask_report
        exc = TimeoutError("timeout")
        result = ask_report.describe_llm_error(exc)
        assert result == "тайм-аут"

    def test_url_error_with_timeout(self):
        """describe_llm_error(URLError с timeout) возвращает 'тайм-аут'."""
        import ask_report
        exc = URLError(TimeoutError("timeout"))
        result = ask_report.describe_llm_error(exc)
        assert result == "тайм-аут"

    def test_url_error_no_connection(self):
        """describe_llm_error(URLError без timeout) возвращает 'нет соединения...'."""
        import ask_report
        exc = URLError("Name or service not known: secret-host.example")
        result = ask_report.describe_llm_error(exc)
        assert result == "нет соединения с провайдером"
        assert "secret-host" not in result

    def test_key_error(self):
        """describe_llm_error(KeyError) возвращает 'неожиданный ответ...'."""
        import ask_report
        exc = KeyError("choices")
        result = ask_report.describe_llm_error(exc)
        assert result == "неожиданный ответ провайдера"

    def test_runtime_error_with_secret(self):
        """describe_llm_error(RuntimeError) возвращает 'ошибка запроса' без ключа."""
        import ask_report
        exc = RuntimeError("Bearer sk-123")
        result = ask_report.describe_llm_error(exc)
        assert result == "ошибка запроса"
        assert "sk-123" not in result


class TestMetaEndpoint:
    """Тесты для /meta endpoint."""

    def test_meta_assistant_false_без_настройки(self, llm_env, ready_detector):
        """GET /meta возвращает assistant: false без LLM_*."""
        llm_env()  # Не устанавливаем переменные
        client = TestClient(app)
        response = client.get("/meta")
        assert response.status_code == 200
        data = response.json()
        assert data["assistant"] is False

    def test_meta_assistant_true_и_без_секретов(self, llm_env, ready_detector):
        """GET /meta возвращает assistant: true и не показывает ключ/хост."""
        llm_env(base_url="https://x/v1", api_key="sk-SECRET", model="m")
        client = TestClient(app)
        response = client.get("/meta")
        assert response.status_code == 200
        data = response.json()
        assert data["assistant"] is True
        assert "sk-SECRET" not in response.text
        assert "https://x/v1" not in response.text


class TestAskEndpoint:
    """Тесты для /ask endpoint."""

    def test_ask_503_без_настройки(self, llm_env):
        """POST /ask возвращает 503 без LLM_*."""
        llm_env()  # Не устанавливаем переменные
        client = TestClient(app)
        response = client.post("/ask", json={
            "question": "что-то",
            "report": {"sites": [{"site_id": "p03", "stages": []}], "meta": {}},
        })
        assert response.status_code == 503
        assert "LLM_BASE_URL" in response.json()["detail"]

    def test_ask_400_нет_площадки(self, llm_env):
        """POST /ask возвращает 400 если площадки нет в отчёте."""
        llm_env(base_url="https://x/v1", api_key="k", model="m")
        client = TestClient(app)
        response = client.post("/ask", json={
            "question": "что-то",
            "report": {"sites": [{"site_id": "p03", "stages": []}], "meta": {}},
            "site_id": "p99",  # Площадки нет в отчёте
        })
        assert response.status_code == 400

    def test_ask_504_сообщение_без_секретов(self, llm_env, monkeypatch):
        """POST /ask возвращает 504 с санитизированной ошибкой."""
        llm_env(base_url="https://x/v1", api_key="sk-SECRET", model="m")

        # Monkeypatch ask_report.ask
        import ask_report
        def failing_ask(*args, **kwargs):
            raise RuntimeError("401 Bearer sk-SECRET host llm.secret.example")

        monkeypatch.setattr(ask_report, "ask", failing_ask)

        client = TestClient(app)
        response = client.post("/ask", json={
            "question": "что-то",
            "report": {
                "sites": [{"site_id": "p03", "stages": []}],
                "meta": {}
            },
        })
        assert response.status_code == 504
        assert "sk-SECRET" not in response.text
        assert "llm.secret.example" not in response.text
        assert "ошибка запроса" in response.json()["detail"]

    def test_ask_успех_возвращает_limits_и_verified(self, llm_env, monkeypatch):
        """POST /ask возвращает 200 с ответом, limits и verified."""
        llm_env(base_url="https://x/v1", api_key="k", model="m")

        # Monkeypatch ask_report.ask
        import ask_report
        def successful_ask(*args, **kwargs):
            return "Площадка p03, этап 12.3.2 отстаёт на 14 дней."

        monkeypatch.setattr(ask_report, "ask", successful_ask)

        # ОТЧЁТ из test_pipeline.py
        ОТЧЁТ = {
            "meta": {"sites": 2, "frames_in": 47},
            "sites": [
                {"site_id": "p03", "as_of": "2023-10-13",
                 "stages": [{"stage_code": "12.3.2", "delay_days": 14,
                             "delay_days_min": 14, "delay_days_max": 43}],
                 "alerts": [], "forecast": {"shift_days": 108}},
                {"site_id": "p08", "as_of": "2024-04-24",
                 "stages": [{"stage_code": "12.3.2", "delay_days": 24,
                             "delay_days_min": 24, "delay_days_max": 55}],
                 "alerts": [], "forecast": {"shift_days": 24}},
            ],
        }

        client = TestClient(app)
        response = client.post("/ask", json={
            "question": "что-то",
            "report": ОТЧЁТ,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert "Проверяются числа" in data["limits"]
