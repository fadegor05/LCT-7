"""Отрисовка аннотированных изображений с детекциями оборудования."""

from collections.abc import Sequence
from io import BytesIO
from typing import cast

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.domains.photo.date_resolver import InvalidImageError
from app.domains.photo.schemas import DetectionRead


def render_annotated(image_bytes: bytes, detections: Sequence[DetectionRead]) -> tuple[bytes, str]:
    """Отрисовать изображение с аннотациями детекций.

    Открывает изображение, применяет EXIF транспозицию, конвертирует в RGB,
    рисует для каждой детекции прямоугольник по координатам bbox (как доли [0..1])
    и метку с кодом и confidence над коробкой. Возвращает PNG байты.

    Цвет детекции детерминирован по equipment_code (hash).
    Толщина линии зависит от размера изображения (макс 2, мин w,h // 200).

    Args:
        image_bytes: Байты изображения
        detections: Список DetectionRead с bbox в формате [x1, y1, x2, y2] как доли [0..1]

    Returns:
        Tuple (png_bytes, "image/png")

    Raises:
        InvalidImageError: Если image_bytes - поврежденное или неподдерживаемое изображение
    """
    # Открываем изображение
    try:
        img_obj = cast(Image.Image, Image.open(BytesIO(image_bytes)))
    except Exception as e:
        raise InvalidImageError(f"Failed to open image: {e}") from e

    # Применяем EXIF транспозицию
    try:
        transposed = ImageOps.exif_transpose(img_obj)
        if transposed is not None:
            img_obj = cast(Image.Image, transposed)
    except Exception:
        # Если EXIF отсутствует или поврежден, продолжаем без него
        pass

    # Конвертируем в RGB
    if img_obj.mode != "RGB":
        img_obj = cast(Image.Image, img_obj.convert("RGB"))

    img = img_obj

    width, height = img.size

    # Если нет детекций, просто переточиваем изображение в PNG и возвращаем
    if not detections:
        output = BytesIO()
        img.save(output, format="PNG")
        return output.getvalue(), "image/png"

    # Рисуем детекции
    draw = ImageDraw.Draw(img)

    # Вычисляем толщину линии
    line_width = max(2, min(width, height) // 200)

    # Используем дефолтный шрифт
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for detection in detections:
        # Извлекаем bbox как доли [x1, y1, x2, y2]
        if len(detection.bbox) < 4:
            continue

        x1_frac = max(0.0, min(1.0, detection.bbox[0]))
        y1_frac = max(0.0, min(1.0, detection.bbox[1]))
        x2_frac = max(0.0, min(1.0, detection.bbox[2]))
        y2_frac = max(0.0, min(1.0, detection.bbox[3]))

        # Конвертируем в пиксели
        x1 = int(x1_frac * width)
        y1 = int(y1_frac * height)
        x2 = int(x2_frac * width)
        y2 = int(y2_frac * height)

        # Кламп координаты к границам изображения
        x1 = max(0, min(x1, width - 1))
        y1 = max(0, min(y1, height - 1))
        x2 = max(0, min(x2, width - 1))
        y2 = max(0, min(y2, height - 1))

        # Пропускаем если коробка невалидна или слишком мала
        if x1 >= x2 or y1 >= y2:
            continue

        # Детерминированный цвет по equipment_code (хеш)
        color = _get_color_for_equipment(detection.equipment_code)

        # Рисуем прямоугольник
        draw.rectangle([x1, y1, x2, y2], outline=color, width=line_width)

        # Рисуем метку с кодом и score
        label_text = f"{detection.equipment_code} {detection.score:.2f}"

        # Измеряем размер текста
        if font:
            # Рисуем чёрный текст на белом фоне
            # bbox = draw.textbbox((0, 0), label_text, font=font)
            # text_width = bbox[2] - bbox[0]
            # text_height = bbox[3] - bbox[1]
            # Используем приблизительный размер для дефолтного шрифта
            text_width = len(label_text) * 6
            text_height = 11

            # Пытаемся разместить метку над коробкой
            label_x = x1
            label_y = max(0, y1 - text_height - 2)

            # Если коробка касается верхней границы, размещаем метку внутри
            if label_y == 0 and y1 == 0:
                label_y = y1 + 2

            # Обрезаем метку если она выходит за границы
            label_x2 = min(label_x + text_width, width)
            label_y2 = min(label_y + text_height, height)

            # Рисуем белый фон для текста
            draw.rectangle(
                [label_x, label_y, label_x2, label_y2], fill="white", outline=color, width=1
            )

            # Рисуем сам текст
            draw.text((label_x + 1, label_y + 1), label_text, fill="black", font=font)

    # Сохраняем в PNG
    output = BytesIO()
    img.save(output, format="PNG")
    return output.getvalue(), "image/png"


def _get_color_for_equipment(equipment_code: str) -> tuple[int, int, int]:
    """Получить детерминированный цвет для кода оборудования.

    Args:
        equipment_code: Код оборудования (например, "COMP_1")

    Returns:
        RGB кортеж (r, g, b) значения 0-255
    """
    # Маленькая палитра ярких цветов
    palette = [
        (255, 0, 0),  # Красный
        (0, 255, 0),  # Зелёный
        (0, 0, 255),  # Синий
        (255, 255, 0),  # Жёлтый
        (255, 0, 255),  # Магента
        (0, 255, 255),  # Cyan
        (255, 165, 0),  # Orange
        (128, 0, 128),  # Purple
        (0, 128, 128),  # Teal
        (255, 192, 203),  # Pink
    ]

    # Хешируем code в индекс
    hash_value = hash(equipment_code)
    index = abs(hash_value) % len(palette)
    return palette[index]
