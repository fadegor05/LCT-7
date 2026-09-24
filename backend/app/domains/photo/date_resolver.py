"""Разрешение даты съёмки фотографии из различных источников.

Поддерживаемые источники (в порядке приоритета):
1. Дата из канала (channel) — явно указана при загрузке
2. EXIF metadata — DateTimeOriginal, DateTime, DateTimeDigitized
3. Штамп на кадре (OCR) — распознавание текста на фотографии
4. Соседние фотографии — определяется сервисом позже
5. Ручной ввод — вводит инженер
"""

import re
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO
from typing import Protocol

from PIL import Image, ImageOps

from app.domains.photo.models import DateSource


class InvalidImageError(Exception):
    """Ошибка при чтении или декодировании изображения."""

    pass


class StampOcr(Protocol):
    """Протокол для OCR чтения текста со штампа на кадре.

    Синхронный интерфейс; вызывающая сторона будет выполнять в потоке.
    """

    def read_text(self, image: Image.Image) -> str:
        """Прочитать текст с изображения.

        Args:
            image: PIL Image object.

        Returns:
            Распознанный текст (может быть пустой строкой).
        """
        ...


class NullStampOcr:
    """Заглушка OCR, всегда возвращающая пустую строку."""

    def read_text(self, image: Image.Image) -> str:
        """Возвращает пустую строку (нет результата OCR)."""
        return ""


@dataclass(frozen=True)
class ImageInfo:
    """Информация об изображении."""

    width: int
    height: int
    format: str | None = None


@dataclass(frozen=True)
class ResolvedDate:
    """Разрешённая дата съёмки фотографии."""

    captured_on: date | None
    source: DateSource | None


def parse_stamp_date(text: str) -> date | None:
    """Парсинг даты из OCR-текста штампа.

    Поддерживаемые форматы:
    - dd.mm.yyyy, dd/mm/yyyy, dd-mm-yyyy
    - yyyy-mm-dd, yyyy.mm.dd, yyyy/mm/dd
    - с окружающим текстом и временем

    2-значный год (dd.mm.yy) НЕ поддерживается (возвращает None).
    Невалидные календарные даты пропускаются.
    Годы вне диапазона [2000, текущий_год + 1] отклоняются как шум.

    Args:
        text: Текст, содержащий потенциальные даты.

    Returns:
        date если найдена первая плausible дата, иначе None.
    """
    if not text:
        return None

    # Текущий год для проверки границ
    current_year = datetime.now().year

    # Регулярные выражения для разных форматов
    # Три части через разделитель: может быть dd.mm.yyyy или yyyy.mm.dd
    patterns = [
        r"(\d{4})[-/.]\s*(\d{1,2})[-/.]\s*(\d{1,2})",  # yyyy-mm-dd
        r"(\d{1,2})[-/.]\s*(\d{1,2})[-/.]\s*(\d{4})",  # dd-mm-yyyy
    ]

    for pattern in patterns:
        for match in re.finditer(pattern, text):
            parts = match.groups()

            # Определяем порядок компонентов
            if int(parts[0]) > 31:
                # Первое число > 31, значит это год (yyyy-mm-dd)
                year_str, month_str, day_str = parts
            else:
                # Иначе это dd-mm-yyyy
                day_str, month_str, year_str = parts

            try:
                year = int(year_str)
                month = int(month_str)
                day = int(day_str)

                # Проверка границ года
                if year < 2000 or year > current_year + 1:
                    continue

                # Попытка создать дату (проверяет валидность календаря)
                candidate_date = date(year, month, day)
                return candidate_date

            except ValueError:
                # Невалидная дата (31.02 и т.д.), продолжаем поиск
                continue

    return None


def read_image_info(content: bytes) -> ImageInfo:
    """Прочитать размеры изображения из байтов.

    Применяет EXIF-ориентацию через ImageOps.exif_transpose,
    чтобы размеры соответствовали тому, как их видит пользователь.

    Args:
        content: Байты изображения (PNG, JPEG и т.д.).

    Returns:
        ImageInfo с шириной, высотой после применения EXIF-ориентации,
        и форматом (в верхнем регистре, например "JPEG", "PNG", "WEBP").

    Raises:
        InvalidImageError: Если байты не являются валидным изображением
                          или файл повреждён.
    """
    try:
        image = Image.open(BytesIO(content))
        # verify() проверяет целостность, но некоторые форматы её не требуют
        # Просойдём load() чтобы убедиться, что файл декодируется
        image.load()

        # Применяем EXIF-ориентацию
        transposed = ImageOps.exif_transpose(image)
        if transposed is None:
            raise InvalidImageError("Failed to transpose EXIF orientation")

        # Получаем формат из исходного изображения (до транспонирования)
        fmt = image.format.upper() if image.format else None

        return ImageInfo(width=transposed.width, height=transposed.height, format=fmt)

    except (OSError, Image.UnidentifiedImageError) as e:
        raise InvalidImageError(f"Failed to read image: {e}") from e
    except Exception as e:
        # Ловим другие ошибки (например, decompression bomb warnings -> errors)
        raise InvalidImageError(f"Invalid or corrupt image: {e}") from e


class DateResolver:
    """Разрешитель даты съёмки фотографии.

    Использует цепочку источников с приоритетом:
    1. channel_date (явно переданная дата)
    2. EXIF metadata (DateTimeOriginal, DateTime, DateTimeDigitized)
    3. Stamp OCR (распознавание текста со штампа)
    """

    def __init__(self, ocr: StampOcr | None = None) -> None:
        """Инициализация DateResolver.

        Args:
            ocr: Объект с интерфейсом StampOcr для чтения текста с изображения.
                 Если None, используется NullStampOcr (всегда пустая строка).
        """
        self.ocr = ocr if ocr is not None else NullStampOcr()

    def resolve(self, content: bytes, channel_date: date | None = None) -> ResolvedDate:
        """Разрешить дату съёмки из различных источников.

        Проходит цепочку источников в порядке приоритета:
        1. channel_date (если передан)
        2. EXIF DateTimeOriginal / DateTime / DateTimeDigitized
        3. Stamp OCR (читает текст и парсит дату)

        Исключения при чтении изображения распространяются.
        Исключения в OCR НЕ распространяются (результат: нет даты).

        Args:
            content: Байты JPEG/PNG изображения.
            channel_date: Дата из канала (если известна).

        Returns:
            ResolvedDate с датой и источником.

        Raises:
            InvalidImageError: Если байты не являются валидным изображением.
        """
        # 1. channel_date
        if channel_date is not None:
            return ResolvedDate(captured_on=channel_date, source=DateSource.CHANNEL)

        # Открываем изображение для последующих проверок (EXIF, OCR)
        try:
            image = Image.open(BytesIO(content))
            image.load()
        except (OSError, Image.UnidentifiedImageError) as e:
            raise InvalidImageError(f"Failed to read image: {e}") from e
        except Exception as e:
            raise InvalidImageError(f"Invalid or corrupt image: {e}") from e

        # 2. EXIF metadata
        exif_date = self._extract_exif_date(image)
        if exif_date is not None:
            return ResolvedDate(captured_on=exif_date, source=DateSource.METADATA)

        # 3. Stamp OCR
        stamp_date = self._extract_stamp_date(image)
        if stamp_date is not None:
            return ResolvedDate(captured_on=stamp_date, source=DateSource.STAMP)

        # 4. Ничего не найдено
        return ResolvedDate(captured_on=None, source=None)

    def _extract_exif_date(self, image: Image.Image) -> date | None:
        """Извлечь дату из EXIF-метаданных изображения.

        Проверяет в порядке приоритета:
        1. DateTimeOriginal (tag 0x9003) в Exif IFD
        2. DateTime (tag 0x0132) в основном IFD
        3. DateTimeDigitized (tag 0x9004) в Exif IFD

        Args:
            image: PIL Image object.

        Returns:
            date если валидная дата найдена, иначе None.
        """
        exif_data = image.getexif()
        if not exif_data:
            return None

        # Получаем Exif IFD (подсписок тегов)
        exif_ifd = exif_data.get_ifd(0x8769)

        # Проверяем DateTimeOriginal (tag 0x9003)
        datetime_original = exif_ifd.get(0x9003)
        if datetime_original:
            parsed = self._parse_exif_datetime(datetime_original)
            if parsed is not None:
                return parsed

        # Проверяем DateTime (tag 0x0132)
        datetime_tag = exif_data.get(0x0132)
        if datetime_tag:
            parsed = self._parse_exif_datetime(datetime_tag)
            if parsed is not None:
                return parsed

        # Проверяем DateTimeDigitized (tag 0x9004)
        datetime_digitized = exif_ifd.get(0x9004)
        if datetime_digitized:
            parsed = self._parse_exif_datetime(datetime_digitized)
            if parsed is not None:
                return parsed

        return None

    @staticmethod
    def _parse_exif_datetime(datetime_str: str | bytes) -> date | None:
        """Парсить EXIF datetime в формате 'YYYY:MM:DD HH:MM:SS'.

        Args:
            datetime_str: Строка или байты из EXIF.

        Returns:
            date если парсинг успешен, иначе None.
        """
        if isinstance(datetime_str, bytes):
            try:
                datetime_str = datetime_str.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                return None

        if not datetime_str or not isinstance(datetime_str, str):
            return None

        # Проверяем, не мусор ли это (например, "0000:00:00")
        if datetime_str.startswith("0000:00:00"):
            return None

        try:
            # Ожидаем формат YYYY:MM:DD HH:MM:SS
            # Берём только дату (первые 10 символов: YYYY:MM:DD)
            date_part = datetime_str[:10]
            year_str, month_str, day_str = date_part.split(":")
            year = int(year_str)
            month = int(month_str)
            day = int(day_str)

            return date(year, month, day)
        except (ValueError, IndexError, AttributeError):
            return None

    def _extract_stamp_date(self, image: Image.Image) -> date | None:
        """Извлечь дату из распознавания штампа через OCR.

        Исключения в OCR НЕ распространяются.

        Args:
            image: PIL Image object.

        Returns:
            date если парсинг текста OCR успешен, иначе None.
        """
        try:
            text = self.ocr.read_text(image)
        except Exception:
            # OCR ошибка — игнорируем и возвращаем None
            return None

        if not text:
            return None

        return parse_stamp_date(text)
