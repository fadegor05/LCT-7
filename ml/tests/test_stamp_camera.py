"""Время знакогенератора камеры (ml/stamp) на синтетических кадрах.

Эталоны строятся тут же из синтетических кадров, как в эталонном тесте ветки
clean-mvp: настоящие кадры организаторов в git не попадают.
"""

import io
from datetime import datetime

import numpy as np
import pytest
from PIL import Image

import service.detector as detector
from service.detector import StampReader
from stamp.build import add_labeled
from stamp.layout import PROFILES, profile_for
from stamp.reader import read_gray
from stamp.templates import Templates
from tests.stamp_synth import frame

P = PROFILES[(2592, 1944)]
TRAIN = [
    "01-01-2026 00:00:00", "12-12-2025 12:34:56", "23-09-2026 19:48:37", "30-05-2027 23:59:59",
    "14-06-2028 05:16:27", "27-10-2029 08:29:46", "09-07-2026 17:08:19", "18-11-2026 21:57:38",
]


@pytest.fixture(scope="module")
def store() -> dict[str, Templates]:
    built: dict[str, Templates] = {}
    for n, text in enumerate(TRAIN):
        for kind in ("sky", "dark", "noise"):
            assert add_labeled(built, frame(P, text, kind, seed=n), text)
    return built


def _png(gray: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.clip(gray, 0, 255).astype(np.uint8), "L").convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def test_reads_a_new_time_on_any_background(store) -> None:
    for kind in ("sky", "dark", "noise"):
        read, profile = read_gray(frame(P, "13-08-2026 08:00:13", kind, seed=99), store)
        assert profile is P and read.found
        assert read.captured_at == datetime(2026, 8, 13, 8, 0, 13)
        assert read.confidence >= detector.CAMERA_MIN_CONFIDENCE


def test_camera_read_returns_date_and_profile(store) -> None:
    reader = StampReader()
    reader._camera = store
    out = reader.read_camera(Image.fromarray(np.clip(frame(P, "13-08-2026 08:00:13", "sky", 4), 0, 255)
                                             .astype(np.uint8), "L"))
    confidence = out.pop("confidence")
    assert out == {"date": "2026-08-13", "text": "13-08-2026 08:00:13",
                   "roi": "camera", "profile": "2592x1944", "found": True,
                   "captured_at": "2026-08-13T08:00:13", "method": "templates"}
    assert confidence >= detector.CAMERA_MIN_CONFIDENCE


def test_unknown_resolution_is_left_to_ocr(store) -> None:
    assert profile_for(1280, 720) is None
    reader = StampReader()
    reader._camera = store
    assert reader.read_camera(Image.new("L", (1280, 720))) is None


def test_camera_frame_skips_ocr(store, monkeypatch) -> None:
    monkeypatch.setenv("STAMP_CAMERA_READER", "1")

    class NoOcr:
        def __call__(self, *_):
            raise AssertionError("OCR не должен вызываться для кадра с временем камеры")

    reader = StampReader()
    reader._camera = store
    reader._ocr = NoOcr()
    out = reader.read_bytes(_png(frame(P, "13-08-2026 08:00:13", "dark", seed=12)))
    assert out["date"] == "2026-08-13" and out["profile"] == "2592x1944"


def test_unsure_camera_read_is_a_hint_not_ocr(store, monkeypatch) -> None:
    """Кадр камеры известного разрешения — только эталоны (clean-mvp): неуверенное время
    приходит подсказкой (captured_at без date), OCR его не перебивает."""
    from tools import read_date_stamp

    calls = []
    monkeypatch.setattr(
        read_date_stamp, "read_stamp_for_service", lambda image, ocr: calls.append(1) or {}
    )
    monkeypatch.setenv("STAMP_CAMERA_READER", "1")
    monkeypatch.setattr(detector, "CAMERA_MIN_CONFIDENCE", 1.01)  # ни одно чтение не уверенно
    reader = StampReader()
    reader._camera = store
    reader._ocr = object()
    out = reader.read_bytes(_png(frame(P, "13-08-2026 08:00:13", "sky", seed=3)))
    assert out["date"] is None and out["profile"] == "2592x1944"
    assert out["found"] is True and out["method"] == "templates"
    assert out["captured_at"] == "2026-08-13T08:00:13"
    assert out["confidence"] < 1.01
    assert calls == [], "кадр камеры известного разрешения OCR не читает"


def test_ocr_time_is_capped_and_never_a_date() -> None:
    """OCR без эталонов: время в подсказку с уверенностью не выше 0.5."""
    out = detector.ocr_time({"date": "2024-04-24", "text": "24.04.2024 10:15:02", "roi": "right"})
    assert out == {
        "found": True,
        "captured_at": "2024-04-24T10:15:02",
        "confidence": 0.5,
        "method": "ocr",
    }
    assert detector.ocr_time({"date": "2024-04-24", "text": "24.04.2024"})["captured_at"] is None
    assert detector.ocr_time({"date": None, "text": None})["found"] is False


@pytest.mark.parametrize("value", ["0", "false", "NO"])
def test_flag_off_uses_ocr_and_never_calls_camera_reader(store, monkeypatch, value) -> None:
    from tools import read_date_stamp

    monkeypatch.setenv("STAMP_CAMERA_READER", value)
    camera_calls = []
    monkeypatch.setattr(StampReader, "read_camera",
                        lambda self, img: camera_calls.append(img) or {"date": "x"})
    ocr_calls = []

    def fake_ocr_read(image, ocr):
        ocr_calls.append(image.shape)
        return {"date": None, "text": None, "roi": None}

    monkeypatch.setattr(read_date_stamp, "read_stamp_for_service", fake_ocr_read)
    reader = StampReader()
    reader._camera = store
    reader._ocr = object()
    out = reader.read_bytes(_png(frame(P, "13-08-2026 08:00:13", "sky", seed=8)))
    assert out == {
        "date": None,
        "text": None,
        "roi": None,
        "found": False,
        "captured_at": None,
        "confidence": 0.0,
        "method": "ocr",
    }
    assert ocr_calls, "с выключенным флагом кадр идёт через OCR"
    assert camera_calls == [], "с выключенным флагом read_camera не вызывается"


@pytest.mark.parametrize("value", [None, "1", "true", "YES", " True "])
def test_flag_set_uses_camera_reader(store, monkeypatch, value) -> None:
    # Без переменной чтение камеры включено
    if value is None:
        monkeypatch.delenv("STAMP_CAMERA_READER", raising=False)
    else:
        monkeypatch.setenv("STAMP_CAMERA_READER", value)
    reader = StampReader()
    reader._camera = store
    reader._ocr = object()
    out = reader.read_bytes(_png(frame(P, "13-08-2026 08:00:13", "sky", seed=9)))
    assert out["date"] == "2026-08-13" and out["profile"] == "2592x1944"


def test_no_stamp_is_not_read(store) -> None:
    read, _ = read_gray(frame(P, None, "noise", seed=5), store)
    assert (read.found, read.captured_at) == (False, None)
