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

import pytest
from PIL import Image

from app.adapters.ml.stamp import StampReading
from app.domains.photo.date_resolver import (
    DateResolver,
    ImageInfo,
    InvalidImageError,
    NullStampOcr,
    ResolvedDate,
    parse_filename_date,
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

    @pytest.mark.asyncio
    async def test_null_stamp_ocr_returns_none(self) -> None:
        """NullStampOcr.read_date всегда возвращает None."""
        ocr = NullStampOcr()
        result = await ocr.read_date(b"image_bytes")
        assert result is None


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

    @pytest.mark.asyncio
    async def test_date_resolver_with_default_ocr(self) -> None:
        """DateResolver по умолчанию использует NullStampOcr."""
        resolver = DateResolver()
        # Создаём простое изображение (без EXIF, без channel_date)
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = await resolver.resolve(content)
        # Без channel_date и EXIF, NullStampOcr вернёт None
        assert result.captured_on is None
        assert result.source is None

    def test_date_resolver_with_custom_ocr(self) -> None:
        """DateResolver можно инициализировать с кастомным OCR."""

        # Создаём fake async OCR для проверки инициализации
        class FakeOcr:
            async def read_date(self, content: bytes) -> date | None:
                return date(2026, 3, 25)

        mock_ocr = FakeOcr()
        resolver = DateResolver(ocr=mock_ocr)
        assert resolver.ocr is mock_ocr

    # ========================================================================
    # Priority 1: channel_date
    # ========================================================================

    @pytest.mark.asyncio
    async def test_date_resolver_channel_date_priority(self) -> None:
        """channel_date имеет наивысший приоритет."""
        resolver = DateResolver()
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        channel_date = date(2026, 1, 1)
        result = await resolver.resolve(content, channel_date=channel_date)
        assert result.captured_on == channel_date
        assert result.source == DateSource.CHANNEL

    @pytest.mark.asyncio
    async def test_date_resolver_channel_date_ignores_exif(self) -> None:
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
        result = await resolver.resolve(content, channel_date=channel_date)
        assert result.captured_on == channel_date
        assert result.source == DateSource.CHANNEL

    # ========================================================================
    # Priority 2: EXIF metadata
    # ========================================================================

    @pytest.mark.asyncio
    async def test_date_resolver_exif_datetimeoriginal_tag_9003(self) -> None:
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

        result = await resolver.resolve(content)
        assert result.captured_on == date(2026, 3, 25)
        assert result.source == DateSource.METADATA

    @pytest.mark.asyncio
    async def test_date_resolver_exif_datetime_tag_0132_fallback(self) -> None:
        """EXIF DateTime (tag 0x0132) используется как fallback."""
        resolver = DateResolver()

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = "2026:05:10 09:15:00"  # DateTime tag
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = await resolver.resolve(content)
        assert result.captured_on == date(2026, 5, 10)
        assert result.source == DateSource.METADATA

    @pytest.mark.asyncio
    async def test_date_resolver_exif_datetimedigitized_tag_9004(self) -> None:
        """EXIF DateTimeDigitized (tag 0x9004) поддерживается."""
        resolver = DateResolver()

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif_ifd = exif.get_ifd(0x8769)
        exif_ifd[0x9004] = "2026:07:20 16:45:30"  # DateTimeDigitized
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = await resolver.resolve(content)
        assert result.captured_on == date(2026, 7, 20)
        assert result.source == DateSource.METADATA

    @pytest.mark.asyncio
    async def test_date_resolver_exif_garbage_value_ignored(self) -> None:
        """Мусор в EXIF (например, 0000:00:00) игнорируется."""
        resolver = DateResolver()

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = "0000:00:00 00:00:00"  # Garbage
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = await resolver.resolve(content)
        # Без других источников вернём (None, None)
        assert result.captured_on is None
        assert result.source is None

    @pytest.mark.asyncio
    async def test_date_resolver_exif_empty_value_ignored(self) -> None:
        """Пустое значение EXIF игнорируется."""
        resolver = DateResolver()

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = ""  # Empty
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = await resolver.resolve(content)
        assert result.captured_on is None
        assert result.source is None

    # ========================================================================
    # Priority 3: Stamp OCR (old sync interface — kept for backward compat check)
    # ========================================================================

    def test_date_resolver_null_ocr_has_async_interface(self) -> None:
        """NullStampOcr имеет async интерфейс read_date."""
        ocr = NullStampOcr()
        # Проверяем, что метод существует
        assert hasattr(ocr, "read_date")
        assert callable(ocr.read_date)

    @pytest.mark.asyncio
    async def test_date_resolver_stamp_ocr_exception_not_propagated(self) -> None:
        """Исключение в async OCR НЕ должно распространяться."""

        class FailingOcr:
            async def read_date(self, content: bytes) -> date | None:
                raise RuntimeError("OCR crashed")

        resolver = DateResolver(ocr=FailingOcr())

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        # Должно работать без исключений
        result = await resolver.resolve(content)
        assert result.captured_on is None
        assert result.source is None

    @pytest.mark.asyncio
    async def test_date_resolver_stamp_ocr_returns_no_date(self) -> None:
        """Async OCR может вернуть None, если дата не найдена."""

        class NoDateOcr:
            async def read_date(self, content: bytes) -> date | None:
                return None  # Никаких дат не найдено

        resolver = DateResolver(ocr=NoDateOcr())

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = await resolver.resolve(content)
        assert result.captured_on is None
        assert result.source is None

    # ========================================================================
    # No information
    # ========================================================================

    @pytest.mark.asyncio
    async def test_date_resolver_no_info_returns_none_none(self) -> None:
        """Без channel, EXIF, и stamp вернём (None, None)."""
        resolver = DateResolver()

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = await resolver.resolve(content)
        assert result.captured_on is None
        assert result.source is None

    # ========================================================================
    # Invalid image bytes
    # ========================================================================

    @pytest.mark.asyncio
    async def test_date_resolver_invalid_image_raises_error(self) -> None:
        """Нечитаемые байты изображения вызывают InvalidImageError."""
        resolver = DateResolver()
        content = b"Not a real image"

        with pytest.raises(InvalidImageError):
            await resolver.resolve(content)

    @pytest.mark.asyncio
    async def test_date_resolver_corrupt_image_raises_error(self) -> None:
        """Повреждённое изображение вызывает InvalidImageError."""
        resolver = DateResolver()
        content = b"\xff\xd8\xff\xe0" + b"corrupt data"

        with pytest.raises(InvalidImageError):
            await resolver.resolve(content)

    # ========================================================================
    # Integration tests: all priorities combined
    # ========================================================================

    @pytest.mark.asyncio
    async def test_date_resolver_full_chain_channel_beats_all(self) -> None:
        """Полная цепочка: channel > EXIF > stamp."""

        class FakeAsyncOcr:
            async def read_date(self, content: bytes) -> date | None:
                return date(2025, 6, 1)

        resolver = DateResolver(ocr=FakeAsyncOcr())

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = "2026:02:14 08:00:00"
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        channel_date = date(2026, 5, 10)
        result = await resolver.resolve(content, channel_date=channel_date)

        assert result.captured_on == channel_date
        assert result.source == DateSource.CHANNEL

    @pytest.mark.asyncio
    async def test_date_resolver_full_chain_exif_beats_stamp(self) -> None:
        """EXIF выигрывает у stamp."""

        class FakeAsyncOcr:
            async def read_date(self, content: bytes) -> date | None:
                return date(2025, 6, 1)

        resolver = DateResolver(ocr=FakeAsyncOcr())

        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = "2026:02:14 08:00:00"
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = await resolver.resolve(content)

        assert result.captured_on == date(2026, 2, 14)
        assert result.source == DateSource.METADATA

    @pytest.mark.asyncio
    async def test_date_resolver_full_chain_stamp_fallback(self) -> None:
        """Stamp используется когда нет channel и EXIF."""

        class FakeAsyncOcr:
            async def read_date(self, content: bytes) -> date | None:
                return date(2024, 7, 15)

        resolver = DateResolver(ocr=FakeAsyncOcr())

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = await resolver.resolve(content)

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


class TestDateResolverAsync:
    """Тестирование асинхронной работы DateResolver (LCT-13)."""

    @pytest.mark.asyncio
    async def test_date_resolver_async_stamp_reading(self) -> None:
        """DateResolver.resolve async работает со штампом через async OCR."""

        # Создаём fake async OCR
        class FakeAsyncOcr:
            async def read_date(self, content: bytes) -> date | None:
                return date(2026, 4, 15)

        resolver = DateResolver(ocr=FakeAsyncOcr())

        # Создаём простое изображение без EXIF
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        result = await resolver.resolve(content)
        assert result.captured_on == date(2026, 4, 15)
        assert result.source == DateSource.STAMP

    @pytest.mark.asyncio
    async def test_date_resolver_async_stamp_exception_swallowed(self) -> None:
        """DateResolver.resolve глотает исключения из async OCR."""

        class FailingAsyncOcr:
            async def read_date(self, content: bytes) -> date | None:
                raise RuntimeError("ML сервис недоступен")

        resolver = DateResolver(ocr=FailingAsyncOcr())

        # Создаём простое изображение без EXIF
        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        # Должно вернуться (None, None), а не выброситься исключение
        result = await resolver.resolve(content)
        assert result.captured_on is None
        assert result.source is None

    @pytest.mark.asyncio
    async def test_date_resolver_async_exif_priority_over_stamp(self) -> None:
        """EXIF имеет приоритет над async stamp OCR."""

        class FakeAsyncOcr:
            async def read_date(self, content: bytes) -> date | None:
                return date(2010, 1, 1)  # Старая дата со штампа

        resolver = DateResolver(ocr=FakeAsyncOcr())

        # Создаём JPEG с EXIF DateTime
        img = Image.new("RGB", (100, 100), color="white")
        exif = Image.Exif()
        exif[0x0132] = "2026:03:25 14:22:00"  # DateTime
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", exif=exif)
        content = buffer.getvalue()

        result = await resolver.resolve(content)
        # EXIF дата должна быть выбрана
        assert result.captured_on == date(2026, 3, 25)
        assert result.source == DateSource.METADATA

    @pytest.mark.asyncio
    async def test_date_resolver_async_channel_priority_over_stamp(self) -> None:
        """channel_date имеет приоритет над async stamp OCR."""

        class FakeAsyncOcr:
            async def read_date(self, content: bytes) -> date | None:
                return date(2010, 1, 1)

        resolver = DateResolver(ocr=FakeAsyncOcr())

        img = Image.new("RGB", (100, 100), color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        content = buffer.getvalue()

        channel_date = date(2026, 6, 1)
        result = await resolver.resolve(content, channel_date=channel_date)
        assert result.captured_on == channel_date
        assert result.source == DateSource.CHANNEL


# ============================================================================
# parse_filename_date: дата из имени файла (bug-reports/005)
# ============================================================================

TODAY = date(2026, 9, 27)


class TestParseFilenameDate:
    """Дата из имени файла, когда EXIF вырезан мессенджером."""

    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            # Префикс YYYYMMDDhhmmss (МСК) + Unix-время в мс: обе части сходятся.
            ("202609270200371790463637087.jpg", date(2026, 9, 27)),
            ("202609270200411790463641704.jpg", date(2026, 9, 27)),
            # Тот же префикс с обрезанным хвостом (как в bug-reports/001).
            ("20260927020037179046363708.jpg", date(2026, 9, 27)),
            ("IMG_20260915_143012.jpg", date(2026, 9, 15)),
            ("PXL_20260901_101500123.jpg", date(2026, 9, 1)),
            ("2026-08-24 10.15.00.jpg", date(2026, 8, 24)),
            ("photo_2026_07_03.png", date(2026, 7, 3)),
            ("sites/abc/IMG_20260915_143012.jpg", date(2026, 9, 15)),
            # Только Unix-время в мс: 1790463637087 = 26.09 23:00 UTC = 27.09 02:00 МСК.
            ("1790463637087.jpg", date(2026, 9, 27)),
        ],
    )
    def test_reads_common_patterns(self, name: str, expected: date) -> None:
        assert parse_filename_date(name, today=TODAY) == expected

    @pytest.mark.parametrize(
        "name",
        [
            "photo.jpg",
            "IMG_4567.jpg",
            "",
            None,
            # Невозможная календарная дата.
            "IMG_20261399_101010.jpg",
            # Раньше 2015 года — шум, а не момент съёмки.
            "IMG_20100101_101010.jpg",
            # Будущее.
            "IMG_20990101_101010.jpg",
        ],
    )
    def test_no_plausible_date(self, name: str | None) -> None:
        assert parse_filename_date(name, today=TODAY) is None

    def test_conflicting_candidates_are_rejected(self) -> None:
        """Префикс и Unix-время расходятся больше чем на сутки — дату не ставим."""
        # Префикс 2026-09-20, хвост 1790463637087 = 2026-09-27.
        assert parse_filename_date("202609200200371790463637087.jpg", today=TODAY) is None


class TestDateResolverFilename:
    """Имя файла — последний источник в цепочке DateResolver."""

    @staticmethod
    def _plain_png() -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", (10, 10), color="white").save(buffer, format="PNG")
        return buffer.getvalue()

    @pytest.mark.asyncio
    async def test_filename_used_when_no_exif_and_no_stamp(self) -> None:
        result = await DateResolver().resolve(self._plain_png(), filename="IMG_20260915_143012.jpg")
        assert result == ResolvedDate(captured_on=date(2026, 9, 15), source=DateSource.FILENAME)

    @pytest.mark.asyncio
    async def test_stamp_wins_over_filename(self) -> None:
        class FakeOcr:
            async def read_date(self, content: bytes) -> date | None:
                return date(2026, 3, 25)

        result = await DateResolver(ocr=FakeOcr()).resolve(
            self._plain_png(), filename="IMG_20260915_143012.jpg"
        )
        assert result == ResolvedDate(captured_on=date(2026, 3, 25), source=DateSource.STAMP)

    @pytest.mark.asyncio
    async def test_filename_without_date_leaves_photo_undated(self) -> None:
        result = await DateResolver().resolve(self._plain_png(), filename="photo.jpg")
        assert result == ResolvedDate(captured_on=None, source=None)


class TestCameraFrameFilename:
    """Кадр камеры известного разрешения: имя файла — момент выгрузки, а не съёмки."""

    @staticmethod
    def _png() -> bytes:
        buffer = io.BytesIO()
        Image.new("RGB", (100, 100), color="white").save(buffer, format="PNG")
        return buffer.getvalue()

    @pytest.mark.asyncio
    async def test_unread_camera_stamp_ignores_filename(self) -> None:
        class CameraOcr:
            async def read(self, content: bytes) -> StampReading:
                return StampReading(None, "2592x1944")

        result = await DateResolver(ocr=CameraOcr()).resolve(
            self._png(), filename="202609272307241790539644116.jpg"
        )
        assert result.captured_on is None
        assert result.source is None

    @pytest.mark.asyncio
    async def test_read_camera_stamp_wins(self) -> None:
        class CameraOcr:
            async def read(self, content: bytes) -> StampReading:
                return StampReading(date(2026, 8, 13), "2592x1944")

        result = await DateResolver(ocr=CameraOcr()).resolve(
            self._png(), filename="202609272307241790539644116.jpg"
        )
        assert result.captured_on == date(2026, 8, 13)
        assert result.source == DateSource.STAMP

    @pytest.mark.asyncio
    async def test_frame_of_unknown_camera_keeps_filename(self) -> None:
        class PlainOcr:
            async def read(self, content: bytes) -> StampReading:
                return StampReading(None, None)

        result = await DateResolver(ocr=PlainOcr()).resolve(
            self._png(), filename="IMG_20260927_020037.jpg"
        )
        assert result.captured_on == date(2026, 9, 27)
        assert result.source == DateSource.FILENAME
