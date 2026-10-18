"""Подписи аннотаций: кириллический шрифт и русские названия техники."""

import io
import os
import uuid

import pytest
from PIL import Image, ImageFont

from app.domains.photo import render
from app.domains.photo.render import annotation_label, label_font, render_annotated
from app.domains.photo.schemas import DetectionRead


def _detection(title: str, code: str, score: float = 0.85) -> DetectionRead:
    return DetectionRead(
        id=uuid.uuid4(),
        equipment_type_id=uuid.uuid4(),
        equipment_code=code,
        equipment_title=title,
        bbox=[0.2, 0.2, 0.8, 0.8],
        score=score,
        model_version="v1",
    )


def _image() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (300, 300), color=(200, 200, 200)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def fresh_font_cache() -> None:
    """Сбрасываем кэш label_font, чтобы подмена кандидатов подействовала."""
    label_font.cache_clear()
    yield
    label_font.cache_clear()


class TestLabelFont:
    def test_falls_back_to_default_font_without_candidates(
        self, monkeypatch: pytest.MonkeyPatch, fresh_font_cache: None
    ) -> None:
        monkeypatch.setattr(render, "FONT_CANDIDATES", ("/nonexistent/none.ttf",))

        font, cyrillic = label_font(20)

        assert cyrillic is False
        assert font is not None

    def test_picks_truetype_font_with_cyrillic_when_available(self, fresh_font_cache: None) -> None:
        available = [p for p in render.FONT_CANDIDATES if os.path.exists(p)]
        if not available:
            pytest.skip("Шрифт с кириллицей не найден в этой среде")

        font, cyrillic = label_font(20)

        assert cyrillic is True
        assert isinstance(font, ImageFont.FreeTypeFont)


class TestAnnotationLabel:
    def test_uses_russian_title_and_percent_score(self) -> None:
        assert annotation_label("Компрессор", "COMP_1", 0.853, cyrillic=True) == ("Компрессор 85%")

    def test_falls_back_to_code_without_cyrillic_font(self) -> None:
        assert annotation_label("Компрессор", "COMP_1", 0.853, cyrillic=False) == ("COMP_1 85%")


class TestRenderLabels:
    def test_label_uses_russian_title(self, monkeypatch: pytest.MonkeyPatch) -> None:
        labels: list[str] = []
        original = render.annotation_label

        def spy(title: str, code: str, score: float, *, cyrillic: bool) -> str:
            label = original(title, code, score, cyrillic=cyrillic)
            labels.append(label)
            return label

        monkeypatch.setattr(render, "annotation_label", spy)
        monkeypatch.setattr(render, "label_font", lambda size: (ImageFont.load_default(size), True))

        render_annotated(_image(), [_detection("Самосвал", "DUMP_1", 0.9)])

        assert labels == ["Самосвал 90%"]

    def test_label_falls_back_to_code_without_cyrillic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        labels: list[str] = []
        original = render.annotation_label

        def spy(title: str, code: str, score: float, *, cyrillic: bool) -> str:
            label = original(title, code, score, cyrillic=cyrillic)
            labels.append(label)
            return label

        monkeypatch.setattr(render, "annotation_label", spy)
        monkeypatch.setattr(
            render, "label_font", lambda size: (ImageFont.load_default(size), False)
        )

        render_annotated(_image(), [_detection("Самосвал", "DUMP_1", 0.9)])

        assert labels == ["DUMP_1 90%"]
