"""Разрешение даты съёмки фотографии из различных источников.

Поддерживаемые источники (в порядке приоритета):
1. Дата из канала (channel) — явно указана при загрузке
2. EXIF metadata — DateTimeOriginal, DateTime, DateTimeDigitized
3. Штамп на кадре (OCR) — распознавание текста на фотографии
4. Соседние фотографии — определяется сервисом позже
5. Ручной ввод — вводит инженер
"""

import io
from datetime import date
from unittest.mock import Mock

import pytest
from PIL import Image

from app.domains.photo.date_resolver import (
    DateResolver,
    ImageInfo,
    InvalidImageError,
    NullStampOcr,
    ResolvedDate,
    parse_stamp_date,
    read_image_info,
)
from app.domains.photo.models import DateSource

# ============================================================================
# parse_stamp_date: парсинг дат из OCR-текста
# ============================================================================


class TestParseStampDate:
    """Тестирование парсинга дат из OCR-текста."""

    def test_parse_stamp_date_dd_mm_yyyy_dot(self) -> None:
        """Формат dd.mm.yyyy с точками."""
        result = parse_stamp_date("25.03.2026")
        assert result == date(2026, 3, 25)

    def test_parse_stamp_date_dd_mm_yyyy_slash(self) -> None:
        """Формат dd/mm/yyyy с наклонными чертами."""
        result = parse_stamp_date("25/03/2026")
        assert result == date(2026, 3, 25)

    def test_parse_stamp_date_dd_mm_yyyy_dash(self) -> None:
        """Формат dd-mm-yyyy с дефисами."""
        result = parse_stamp_date("25-03-2026")
        assert result == date(2026, 3, 25)

    def test_parse_stamp_date_yyyy_mm_dd_dash(self) -> None:
        """Формат yyyy-mm-dd с дефисами (ISO)."""
        result = parse_stamp_date("2026-03-25")
        assert result == date(2026, 3, 25)

    def test_parse_stamp_date_yyyy_mm_dd_dot(self) -> None:
        """Формат yyyy.mm.dd с точками."""
        result = parse_stamp_date("2026.03.25")
        assert result == date(2026, 3, 25)

    def test_parse_stamp_date_yyyy_mm_dd_slash(self) -> None:
        """Формат yyyy/mm/dd с наклонными чертами."""
        result = parse_stamp_date("2026/03/25")
        assert result == date(2026, 3, 25)

    def test_parse_stamp_date_with_surrounding_text(self) -> None:
        """Дата может быть окружена текстом."""
        result = parse_stamp_date("Фото от 25.03.2026 10:30")
        assert result == date(2026, 3, 25)

    def test_parse_stamp_date_with_time(self) -> None:
        """Дата с временем в формате ISO (yyyy-mm-dd HH:MM:SS)."""
        result = parse_stamp_date("2026-03-25 14:22:10")
        assert result == date(2026, 3, 25)

    def test_parse_stamp_date_multiline(self) -> None:
        """Дата может быть на разных строках."""
        text = "Фотография\n25.03.2026\nВремя: 14:30"
        result = parse_stamp_date(text)
        assert result == date(2026, 3, 25)

    def test_parse_stamp_date_two_digit_year_not_supported(self) -> None:
        """2-значный год НЕ поддерживается (возвращает None)."""
        result = parse_stamp_date("25.03.26")
        assert result is None

    def test_parse_stamp_date_invalid_calendar_date_31_feb(self) -> None:
        """Невалидная дата календаря (31.02.2026) пропускается, продолжаем поиск."""
        text = "Ошибка: 31.02.2026\nПравильно: 25.03.2026"
        result = parse_stamp_date(text)
        assert result == date(2026, 3, 25)

    def test_parse_stamp_date_invalid_calendar_date_then_valid(self) -> None:
        """После невалидной даты ищем валидную."""
        text = "30.02.2026 тут неправильно, а тут 01.01.2026 правильно"
        result = parse_stamp_date(text)
        assert result == date(2026, 1, 1)

    def test_parse_stamp_date_year_too_old(self) -> None:
        """Год 1999 отклоняется как шум (< 2000)."""
        result = parse_stamp_date("25.03.1999")
        assert result is None

    def test_parse_stamp_date_year_too_new(self) -> None:
        """Год после текущего года + 1 отклоняется как шум."""
        # Текущий год 2026, поэтому 2028 отклоняется
        result = parse_stamp_date("25.03.2028")
        assert result is None

    def test_parse_stamp_date_year_current_plus_one_accepted(self) -> None:
        """Год текущий + 1 принимается."""
        # Текущий год 2026, поэтому 2027 принимается
        result = parse_stamp_date("25.03.2027")
        assert result == date(2027, 3, 25)

    def test_parse_stamp_date_year_2000_accepted(self) -> None:
        """Год 2000 принимается (нижняя граница)."""
        result = parse_stamp_date("01.01.2000")
        assert result == date(2000, 1, 1)

    def test_parse_stamp_date_empty_text(self) -> None:
        """Пустой текст возвращает None."""
        result = parse_stamp_date("")
        assert result is None

    def test_parse_stamp_date_no_date_in_text(self) -> None:
        """Текст без даты возвращает None."""
        result = parse_stamp_date("Просто текст без дат")
        assert result is None

    def test_parse_stamp_date_multiple_candidates_returns_first(self) -> None:
        """При нескольких датах возвращаем первую валидную."""
        text = "Первая: 01.01.2020 Вторая: 25.03.2026"
        result = parse_stamp_date(text)
        assert result == date(2020, 1, 1)


# ============================================================================
# StampOcr Protocol и NullStampOcr
# ============================================================================


class TestNullStampOcr:
    """Тестирование NullStampOcr (заглушка)."""

    def test_null_stamp_ocr_returns_empty_string(self) -> None:
        """NullStampOcr всегда возвращает пустую строку."""
        ocr = NullStampOcr()
        # Создаём простое изображение для теста
        img = Image.new("RGB", (100, 100), color="white")
        result = ocr.read_text(img)
        assert result == ""


# ============================================================================
# ImageInfo и read_image_info
# ============================================================================


class TestImageInfo:
    """Тестирование класса ImageInfo."""

    def test_image_info_is_frozen(self) -> None:
        """ImageInfo это frozen dataclass (неизменяемый)."""
        info = ImageInfo(width=640, height=480)
        with pytest.raises(AttributeError):
            info.width = 800  # type: ignore

    def test_image_info_equality(self) -> None:
        """ImageInfo поддерживает сравнение."""
        info1 = ImageInfo(width=640, height=480)
        info2 = ImageInfo(width=640, height=480)
        info3 = ImageInfo(width=800, height=600)
        assert info1 == info2
        assert info1 != info3


class TestReadImageInfo:
    """Тестирование функции read_image_info."""

    def test_read_image_info_png(self) -> None:
        """read_image_info работает с PNG."""
        img = Image.new("RGB", (640, 480), color="red")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = read_image_info(content)
        assert result.width == 640
        assert result.height == 480

    def test_read_image_info_jpeg(self) -> None:
        """read_image_info работает с JPEG."""
        img = Image.new("RGB", (800, 600), color="blue")
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        content = buffer.getvalue()

        result = read_image_info(content)
        assert result.width == 800
        assert result.height == 600

    def test_read_image_info_with_exif_orientation_6_rotated_90_deg(self) -> None:
        """EXIF orientation 6 (rotated 90° clockwise) меняет местами width и height.

        Orientation 6 означает, что изображение повёрнуто на 90° по часовой стрелке.
        После применения ImageOps.exif_transpose физические размеры:
        - исходное 800x600 становится 600x800 (ширина и высота меняются местами).
        """
        # Создаём изображение 800x600
        img = Image.new("RGB", (800, 600), color="green")

        # Добавляем EXIF с ориентацией 6 (повёрнуто на 90°)
        exif = Image.Exif()
        exif[0x0112] = 6  # Orientation tag = 6 (rotated 90° CW)
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        # read_image_info применяет ImageOps.exif_transpose, поэтому размеры должны быть
        # свопнуты (ширина становится высотой и наоборот)
        result = read_image_info(content)
        assert result.width == 600
        assert result.height == 800

    def test_read_image_info_corrupt_file_raises_invalid_image_error(self) -> None:
        """Повреждённый файл изображения вызывает InvalidImageError."""
        content = b"Not a real image file\x00\xff\xfe"

        with pytest.raises(InvalidImageError):
            read_image_info(content)

    def test_read_image_info_non_image_bytes_raises_invalid_image_error(self) -> None:
        """Не-изображение вызывает InvalidImageError."""
        content = b"This is just plain text, not an image"

        with pytest.raises(InvalidImageError):
            read_image_info(content)

    def test_read_image_info_empty_bytes_raises_invalid_image_error(self) -> None:
        """Пустой буфер вызывает InvalidImageError."""
        content = b""

        with pytest.raises(InvalidImageError):
            read_image_info(content)


# ============================================================================
# ResolvedDate
# ============================================================================


class TestResolvedDate:
    """Тестирование класса ResolvedDate."""

    def test_resolved_date_with_both_set(self) -> None:
        """ResolvedDate с обеими полями установленными."""
        resolved = ResolvedDate(captured_on=date(2026, 3, 25), source=DateSource.METADATA)
        assert resolved.captured_on == date(2026, 3, 25)
        assert resolved.source == DateSource.METADATA

    def test_resolved_date_with_both_none(self) -> None:
        """ResolvedDate с обеими полями None."""
        resolved = ResolvedDate(captured_on=None, source=None)
        assert resolved.captured_on is None
        assert resolved.source is None

    def test_resolved_date_is_frozen(self) -> None:
        """ResolvedDate это frozen dataclass."""
        resolved = ResolvedDate(captured_on=date(2026, 3, 25), source=DateSource.METADATA)
        with pytest.raises(AttributeError):
            resolved.captured_on = date(2026, 1, 1)  # type: ignore


# ============================================================================
# InvalidImageError
# ============================================================================


class TestInvalidImageError:
    """Тестирование класса InvalidImageError."""

    def test_invalid_image_error_is_exception(self) -> None:
        """InvalidImageError это Exception."""
        error = InvalidImageError("test message")
        assert isinstance(error, Exception)
        assert str(error) == "test message"


# ============================================================================
# DateResolver: основной тест разрешения дат
# ============================================================================


class TestDateResolver:
    """Тестирование основного класса DateResolver."""

    def test_date_resolver_with_default_ocr(self) -> None:
        """DateResolver по умолчанию использует NullStampOcr."""
        resolver = DateResolver()
        # Создаём простое изображение (без EXIF, без channel_date)
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = resolver.resolve(content)
        # Без channel_date и EXIF, NullStampOcr вернёт пустую строку
        # parse_stamp_date("") вернёт None
        assert result.captured_on is None
        assert result.source is None

    def test_date_resolver_with_custom_ocr(self) -> None:
        """DateResolver можно инициализировать с кастомным OCR."""
        mock_ocr = Mock()
        mock_ocr.read_text.return_value = "25.03.2026"

        resolver = DateResolver(ocr=mock_ocr)
        assert resolver.ocr is mock_ocr

    # ========================================================================
    # Priority 1: channel_date
    # ========================================================================

    def test_date_resolver_channel_date_priority(self) -> None:
        """channel_date имеет наивысший приоритет."""
        resolver = DateResolver()
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        channel_date = date(2026, 1, 1)
        result = resolver.resolve(content, channel_date=channel_date)
        assert result.captured_on == channel_date
        assert result.source == DateSource.CHANNEL

    def test_date_resolver_channel_date_ignores_exif(self) -> None:
        """channel_date имеет приоритет над EXIF."""
        resolver = DateResolver()

        # Создаём JPEG с EXIF DateTime
        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = "2026:02:15 10:30:00"  # DateTime tag
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        channel_date = date(2026, 1, 1)
        result = resolver.resolve(content, channel_date=channel_date)
        assert result.captured_on == channel_date
        assert result.source == DateSource.CHANNEL

    # ========================================================================
    # Priority 2: EXIF metadata
    # ========================================================================

    def test_date_resolver_exif_datetimeoriginal_tag_9003(self) -> None:
        """EXIF DateTimeOriginal (tag 0x9003) читается из Exif IFD."""
        resolver = DateResolver()

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()

        # Устанавливаем Exif IFD и добавляем DateTimeOriginal (0x9003)
        exif_ifd = exif.get_ifd(0x8769)  # Exif IFD
        exif_ifd[0x9003] = "2026:03:25 14:22:10"  # DateTimeOriginal

        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = resolver.resolve(content)
        assert result.captured_on == date(2026, 3, 25)
        assert result.source == DateSource.METADATA

    def test_date_resolver_exif_datetime_tag_0132_fallback(self) -> None:
        """EXIF DateTime (tag 0x0132) используется как fallback."""
        resolver = DateResolver()

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = "2026:05:10 09:15:00"  # DateTime tag
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = resolver.resolve(content)
        assert result.captured_on == date(2026, 5, 10)
        assert result.source == DateSource.METADATA

    def test_date_resolver_exif_datetimedigitized_tag_9004(self) -> None:
        """EXIF DateTimeDigitized (tag 0x9004) поддерживается."""
        resolver = DateResolver()

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif_ifd = exif.get_ifd(0x8769)
        exif_ifd[0x9004] = "2026:07:20 16:45:30"  # DateTimeDigitized
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = resolver.resolve(content)
        assert result.captured_on == date(2026, 7, 20)
        assert result.source == DateSource.METADATA

    def test_date_resolver_exif_garbage_value_ignored(self) -> None:
        """Мусор в EXIF (например, 0000:00:00) игнорируется."""
        resolver = DateResolver()

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = "0000:00:00 00:00:00"  # Garbage
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = resolver.resolve(content)
        # Без других источников вернём (None, None)
        assert result.captured_on is None
        assert result.source is None

    def test_date_resolver_exif_empty_value_ignored(self) -> None:
        """Пустое значение EXIF игнорируется."""
        resolver = DateResolver()

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = ""  # Empty
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = resolver.resolve(content)
        assert result.captured_on is None
        assert result.source is None

    # ========================================================================
    # Priority 3: Stamp OCR
    # ========================================================================

    def test_date_resolver_stamp_ocr_parsing(self) -> None:
        """Штамп на кадре читается через OCR и парсится."""
        mock_ocr = Mock()
        mock_ocr.read_text.return_value = "Дата: 25.03.2026"

        resolver = DateResolver(ocr=mock_ocr)

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = resolver.resolve(content)
        assert result.captured_on == date(2026, 3, 25)
        assert result.source == DateSource.STAMP

    def test_date_resolver_stamp_ocr_priority_over_nothing(self) -> None:
        """Stamp имеет приоритет над отсутствием информации."""
        mock_ocr = Mock()
        mock_ocr.read_text.return_value = "2026-03-25"

        resolver = DateResolver(ocr=mock_ocr)

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = resolver.resolve(content)
        assert result.captured_on == date(2026, 3, 25)
        assert result.source == DateSource.STAMP

    def test_date_resolver_exif_priority_over_stamp(self) -> None:
        """EXIF имеет приоритет над stamp OCR."""
        mock_ocr = Mock()
        mock_ocr.read_text.return_value = "10.01.2020"

        resolver = DateResolver(ocr=mock_ocr)

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = "2026:03:25 14:22:00"
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = resolver.resolve(content)
        # EXIF дата должна быть выбрана, а не stamp
        assert result.captured_on == date(2026, 3, 25)
        assert result.source == DateSource.METADATA

    def test_date_resolver_stamp_ocr_exception_not_propagated(self) -> None:
        """Исключение в OCR НЕ должно распространяться, метод продолжает работу."""
        mock_ocr = Mock()
        mock_ocr.read_text.side_effect = RuntimeError("OCR crashed")

        resolver = DateResolver(ocr=mock_ocr)

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        # Должно работать без исключений
        result = resolver.resolve(content)
        assert result.captured_on is None
        assert result.source is None

    def test_date_resolver_stamp_ocr_returns_no_date(self) -> None:
        """OCR может вернуть текст, в котором нет даты."""
        mock_ocr = Mock()
        mock_ocr.read_text.return_value = "Просто текст без даты"

        resolver = DateResolver(ocr=mock_ocr)

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = resolver.resolve(content)
        assert result.captured_on is None
        assert result.source is None

    # ========================================================================
    # No information
    # ========================================================================

    def test_date_resolver_no_info_returns_none_none(self) -> None:
        """Без channel, EXIF, и stamp вернём (None, None)."""
        resolver = DateResolver()

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = resolver.resolve(content)
        assert result.captured_on is None
        assert result.source is None

    # ========================================================================
    # Invalid image bytes
    # ========================================================================

    def test_date_resolver_invalid_image_raises_error(self) -> None:
        """Нечитаемые байты изображения вызывают InvalidImageError."""
        resolver = DateResolver()
        content = b"Not a real image"

        with pytest.raises(InvalidImageError):
            resolver.resolve(content)

    def test_date_resolver_corrupt_image_raises_error(self) -> None:
        """Повреждённое изображение вызывает InvalidImageError."""
        resolver = DateResolver()
        content = b"\xff\xd8\xff\xe0" + b"corrupt data"

        with pytest.raises(InvalidImageError):
            resolver.resolve(content)

    # ========================================================================
    # Integration tests: all priorities combined
    # ========================================================================

    def test_date_resolver_full_chain_channel_beats_all(self) -> None:
        """Полная цепочка: channel > EXIF > stamp."""
        mock_ocr = Mock()
        mock_ocr.read_text.return_value = "01.06.2025"

        resolver = DateResolver(ocr=mock_ocr)

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = "2026:02:14 08:00:00"
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        channel_date = date(2026, 5, 10)
        result = resolver.resolve(content, channel_date=channel_date)

        assert result.captured_on == channel_date
        assert result.source == DateSource.CHANNEL

    def test_date_resolver_full_chain_exif_beats_stamp(self) -> None:
        """EXIF выигрывает у stamp."""
        mock_ocr = Mock()
        mock_ocr.read_text.return_value = "01.06.2025"

        resolver = DateResolver(ocr=mock_ocr)

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = "2026:02:14 08:00:00"
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = resolver.resolve(content)

        assert result.captured_on == date(2026, 2, 14)
        assert result.source == DateSource.METADATA

    def test_date_resolver_full_chain_stamp_fallback(self) -> None:
        """Stamp используется когда нет channel и EXIF."""
        mock_ocr = Mock()
        mock_ocr.read_text.return_value = "15.07.2024"

        resolver = DateResolver(ocr=mock_ocr)

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = resolver.resolve(content)

        assert result.captured_on == date(2024, 7, 15)
        assert result.source == DateSource.STAMP


# ============================================================================
# Edge cases and integration
# ============================================================================


class TestEdgeCases:
    """Тестирование граничных случаев."""

    def test_large_image_dimensions_read_correctly(self) -> None:
        """Большие размеры изображения читаются корректно."""
        img = Image.new("RGB", (4000, 3000), color="yellow")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = read_image_info(content)
        assert result.width == 4000
        assert result.height == 3000

    def test_small_image_dimensions_read_correctly(self) -> None:
        """Маленькие размеры изображения читаются корректно."""
        img = Image.new("RGB", (10, 10), color="gray")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = read_image_info(content)
        assert result.width == 10
        assert result.height == 10

    def test_parse_stamp_date_with_noise_around_numbers(self) -> None:
        """Дата с окружающим шумом парсится."""
        text = "Снято: !!!25.03.2026??? в городе"
        result = parse_stamp_date(text)
        assert result == date(2026, 3, 25)
