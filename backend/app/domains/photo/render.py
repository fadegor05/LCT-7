"""Отрисовка аннотированных изображений с детекциями оборудования."""

import zlib
from collections.abc import Sequence
from functools import lru_cache
from io import BytesIO
from typing import cast

from PIL import Image, ImageDraw, ImageFont, ImageOps

from app.domains.photo.date_resolver import InvalidImageError
from app.domains.photo.schemas import DetectionRead

# Версия формата отрисовки: входит в ключ кэша и ETag, поэтому при смене
# рендера (цвета, размер, формат) старые закэшированные картинки не отдаются.
RENDER_VERSION = "3"

# Длинная сторона результата: снимок показывается в карточке, полный
# размер камеры (4000+ px) только раздувает ответ и время кодирования.
MAX_SIDE = 1920
# Миниатюра ленты: карточка шириной ~240 px, с запасом на плотные экраны
THUMB_SIDE = 640
JPEG_QUALITY = 85

# Шрифты с кириллицей: Debian-образ бэкенда (пакет fonts-dejavu-core), macOS разработчика.
FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)


@lru_cache(maxsize=16)
def label_font(size: int) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, bool]:
    """Шрифт подписи и признак «рисует кириллицу».

    Перебирает FONT_CANDIDATES; если ни один не найден, возвращает встроенный шрифт
    Pillow и False: тогда подпись строится по коду класса (встроенный шрифт кириллицу
    не рисует). Кэш нужен, чтобы не читать файл шрифта на каждый кадр.
    """
    for path in FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size), True
        except OSError:
            continue
    return ImageFont.load_default(size), False


def annotation_label(title: str, code: str, score: float, *, cyrillic: bool) -> str:
    """Текст подписи: русское название техники и уверенность в процентах.

    Без шрифта с кириллицей название не нарисовать, поэтому берётся код класса.
    """
    name = title if cyrillic else code
    return f"{name} {round(score * 100)}%"


def render_annotated(
    image_bytes: bytes,
    detections: Sequence[DetectionRead],
    max_side: int = MAX_SIDE,
    *,
    labels: bool = True,
) -> tuple[bytes, str]:
    """Отрисовать изображение с аннотациями детекций.

    Открывает изображение, применяет EXIF транспозицию, конвертирует в RGB,
    уменьшает до max_side по длинной стороне, рисует для каждой детекции
    прямоугольник по координатам bbox (как доли [0..1]) и метку с кодом
    и confidence над коробкой. В метке — русское название техники (если есть
    шрифт с кириллицей), иначе код. Возвращает JPEG байты: PNG фотографии весит
    в разы больше и кодируется в разы дольше.

    Цвет детекции детерминирован по equipment_code (crc32).
    Толщина линии зависит от размера изображения (макс 2, мин w,h // 200).

    Args:
        image_bytes: Байты изображения
        detections: Список DetectionRead с bbox в формате [x1, y1, x2, y2] как доли [0..1]
        max_side: Максимальная длина большей стороны результата в пикселях

    Returns:
        Tuple (jpeg_bytes, "image/jpeg")

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

    # Уменьшаем до рабочего размера (bbox в долях, поэтому масштаб не важен)
    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    width, height = img.size

    # Если нет детекций, просто перекодируем изображение
    if not detections:
        return _encode(img)

    # Рисуем детекции
    draw = ImageDraw.Draw(img)

    # Вычисляем толщину линии
    line_width = max(2, min(width, height) // 200)

    # Шрифт с кириллицей (если в среде есть), иначе встроенный шрифт Pillow
    font, cyrillic = label_font(max(12, min(width, height) // 40))

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
        # На миниатюре подпись не читается и закрывает машину — только рамка
        if not labels:
            continue

        label_text = annotation_label(
            detection.equipment_title,
            detection.equipment_code,
            detection.score,
            cyrillic=cyrillic,
        )

        # Размер подписи по реальным метрикам шрифта, а не по приблизительной ширине
        left, top, right, bottom = draw.textbbox((0, 0), label_text, font=font)
        text_width = int(right - left) + 4
        text_height = int(bottom - top) + 4

        # Над коробкой; у верхнего края кадра — внутри коробки
        label_y = y1 - text_height if y1 >= text_height else y1
        # У левого края коробки, но не за правым краем кадра
        label_x = max(0, min(x1, width - text_width))

        # Белый фон с рамкой цвета детекции и чёрный текст поверх
        draw.rectangle(
            [label_x, label_y, label_x + text_width, label_y + text_height],
            fill="white",
            outline=color,
            width=1,
        )
        draw.text((label_x + 2, label_y + 2 - top), label_text, fill="black", font=font)

    return _encode(img)


def _encode(img: Image.Image) -> tuple[bytes, str]:
    """Закодировать изображение в JPEG."""
    output = BytesIO()
    img.save(output, format="JPEG", quality=JPEG_QUALITY, optimize=True)
    return output.getvalue(), "image/jpeg"


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

    # Хешируем code в индекс: crc32, а не hash() — hash() строк рандомизирован
    # между процессами, и цвет в закэшированной картинке не совпадал бы с новой
    index = zlib.crc32(equipment_code.encode()) % len(palette)
    return palette[index]
