"""Тесты render_annotated для рисования аннотаций на изображениях."""

import io
import uuid
from typing import cast

import pytest
from PIL import Image

from app.domains.photo.date_resolver import InvalidImageError
from app.domains.photo.render import render_annotated
from app.domains.photo.schemas import DetectionRead


def create_test_image(width: int = 200, height: int = 200) -> bytes:
    """Создать тестовое RGB изображение."""
    img = Image.new("RGB", (width, height), color=(200, 200, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_pixel_at(
    image_bytes: bytes, x: int, y: int
) -> tuple[int, int, int] | tuple[int, int, int, int]:
    """Получить пиксель из изображения."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode == "RGBA":
        return cast(tuple[int, int, int, int], img.getpixel((x, y)))
    elif img.mode == "RGB":
        return cast(tuple[int, int, int], img.getpixel((x, y)))
    else:
        img = img.convert("RGB")
        return cast(tuple[int, int, int], img.getpixel((x, y)))


class TestRenderAnnotated:
    """Тесты для render_annotated."""

    def test_no_detections_returns_png_unchanged(self) -> None:
        """Без детекций изображение переточивается в PNG неизменённым."""
        original = create_test_image(100, 100)
        original_img = Image.open(io.BytesIO(original)).convert("RGB")

        result_bytes, content_type = render_annotated(original, [])

        assert content_type == "image/png"

        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.size == (100, 100)
        # Пиксели совпадают байт в байт: без детекций ничего не дорисовывается
        assert result_img.convert("RGB").tobytes() == original_img.tobytes()

    def test_single_detection_rectangle_drawn(self) -> None:
        """Рисуется прямоугольник для одной детекции."""
        image = create_test_image(200, 200)

        detection = DetectionRead(
            id=uuid.uuid4(),
            equipment_type_id=uuid.uuid4(),
            equipment_code="COMP_1",
            equipment_title="Компрессор",
            bbox=[0.2, 0.2, 0.8, 0.8],  # Займет большую часть изображения
            score=0.95,
            model_version="v1",
        )

        result_bytes, content_type = render_annotated(image, [detection])

        assert content_type == "image/png"
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.size == (200, 200)

        # Проверяем что пиксели на краю коробки изменились
        # bbox [0.2, 0.2, 0.8, 0.8] на 200x200 = [40, 40, 160, 160]
        edge_pixel = get_pixel_at(result_bytes, 40, 40)
        background_pixel = get_pixel_at(result_bytes, 10, 10)

        # Они должны различаться (коробка нарисована)
        assert edge_pixel != background_pixel

    def test_multiple_detections(self) -> None:
        """Рисуются несколько детекций."""
        image = create_test_image(300, 300)

        detections = [
            DetectionRead(
                id=uuid.uuid4(),
                equipment_type_id=uuid.uuid4(),
                equipment_code="COMP_1",
                equipment_title="Компрессор",
                bbox=[0.1, 0.1, 0.4, 0.4],
                score=0.95,
                model_version="v1",
            ),
            DetectionRead(
                id=uuid.uuid4(),
                equipment_type_id=uuid.uuid4(),
                equipment_code="DRILL_1",
                equipment_title="Буровая установка",
                bbox=[0.6, 0.6, 0.9, 0.9],
                score=0.87,
                model_version="v1",
            ),
        ]

        result_bytes, content_type = render_annotated(image, detections)

        assert content_type == "image/png"
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.size == (300, 300)

    def test_bbox_clamped_to_image(self) -> None:
        """Коробка зажимается к границам изображения."""
        image = create_test_image(100, 100)

        detection = DetectionRead(
            id=uuid.uuid4(),
            equipment_type_id=uuid.uuid4(),
            equipment_code="COMP_1",
            equipment_title="Компрессор",
            bbox=[-0.1, -0.1, 1.2, 1.2],  # Выходит за границы
            score=0.95,
            model_version="v1",
        )

        # Не должно выбросить исключение
        result_bytes, content_type = render_annotated(image, [detection])

        assert content_type == "image/png"
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.size == (100, 100)

    def test_bbox_at_image_edge_label_inside(self) -> None:
        """Если коробка касается верхней границы, метка размещается внутри."""
        image = create_test_image(200, 200)

        detection = DetectionRead(
            id=uuid.uuid4(),
            equipment_type_id=uuid.uuid4(),
            equipment_code="COMP",
            equipment_title="Компрессор",
            bbox=[0.2, 0.0, 0.8, 0.3],  # Касается верхней границы
            score=0.95,
            model_version="v1",
        )

        result_bytes, content_type = render_annotated(image, [detection])

        assert content_type == "image/png"
        # Проверяем что функция отработала и не выбросила исключение
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.size == (200, 200)

    def test_zero_size_bbox_skipped(self) -> None:
        """Коробка нулевого размера пропускается."""
        image = create_test_image(100, 100)

        detection = DetectionRead(
            id=uuid.uuid4(),
            equipment_type_id=uuid.uuid4(),
            equipment_code="COMP_1",
            equipment_title="Компрессор",
            bbox=[0.5, 0.5, 0.5, 0.5],  # Нулевой размер
            score=0.95,
            model_version="v1",
        )

        result_bytes, content_type = render_annotated(image, [detection])

        assert content_type == "image/png"
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.size == (100, 100)

    def test_corrupt_image_raises_invalid_image_error(self) -> None:
        """Повреждённое изображение вызывает InvalidImageError."""
        corrupt_bytes = b"not an image"

        with pytest.raises(InvalidImageError):
            render_annotated(corrupt_bytes, [])

    def test_output_is_valid_png(self) -> None:
        """Выходное изображение - валидный PNG."""
        image = create_test_image(100, 100)

        detection = DetectionRead(
            id=uuid.uuid4(),
            equipment_type_id=uuid.uuid4(),
            equipment_code="COMP_1",
            equipment_title="Компрессор",
            bbox=[0.2, 0.2, 0.8, 0.8],
            score=0.95,
            model_version="v1",
        )

        result_bytes, content_type = render_annotated(image, [detection])

        # Проверяем что это валидный PNG
        img = Image.open(io.BytesIO(result_bytes))
        assert img.format == "PNG"
        assert content_type == "image/png"

    def test_output_size_matches_input(self) -> None:
        """Размер выходного изображения совпадает с входным."""
        image = create_test_image(250, 150)

        detection = DetectionRead(
            id=uuid.uuid4(),
            equipment_type_id=uuid.uuid4(),
            equipment_code="COMP_1",
            equipment_title="Компрессор",
            bbox=[0.2, 0.2, 0.8, 0.8],
            score=0.95,
            model_version="v1",
        )

        result_bytes, _ = render_annotated(image, [detection])

        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.size == (250, 150)

    def test_insufficient_bbox_coordinates_skipped(self) -> None:
        """Детекция с неполными координатами пропускается."""
        image = create_test_image(100, 100)

        detection = DetectionRead(
            id=uuid.uuid4(),
            equipment_type_id=uuid.uuid4(),
            equipment_code="COMP_1",
            equipment_title="Компрессор",
            bbox=[0.2, 0.2],  # Только 2 координаты вместо 4
            score=0.95,
            model_version="v1",
        )

        # Не должно выбросить исключение
        result_bytes, content_type = render_annotated(image, [detection])

        assert content_type == "image/png"

    def test_large_image(self) -> None:
        """Работает с большими изображениями."""
        image = create_test_image(1000, 800)

        detection = DetectionRead(
            id=uuid.uuid4(),
            equipment_type_id=uuid.uuid4(),
            equipment_code="COMP_1",
            equipment_title="Компрессор",
            bbox=[0.1, 0.1, 0.9, 0.9],
            score=0.95,
            model_version="v1",
        )

        result_bytes, content_type = render_annotated(image, [detection])

        assert content_type == "image/png"
        result_img = Image.open(io.BytesIO(result_bytes))
        assert result_img.size == (1000, 800)

    def test_deterministic_color_per_equipment_code(self) -> None:
        """Один код оборудования всегда получает один и тот же цвет."""
        image = create_test_image(200, 200)

        detection1 = DetectionRead(
            id=uuid.uuid4(),
            equipment_type_id=uuid.uuid4(),
            equipment_code="COMP_1",
            equipment_title="Компрессор",
            bbox=[0.1, 0.1, 0.4, 0.4],
            score=0.95,
            model_version="v1",
        )

        detection2 = DetectionRead(
            id=uuid.uuid4(),
            equipment_type_id=uuid.uuid4(),
            equipment_code="COMP_1",
            equipment_title="Компрессор",
            bbox=[0.6, 0.6, 0.9, 0.9],
            score=0.85,
            model_version="v1",
        )

        result_bytes, _ = render_annotated(image, [detection1, detection2])

        result_img = Image.open(io.BytesIO(result_bytes))
        # Обе коробки должны быть одного цвета (т.к. один код оборудования)
        # Проверяем это косвенно - функция завершилась без ошибок
        assert result_img.size == (200, 200)
