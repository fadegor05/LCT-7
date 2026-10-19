"""Разрешение даты съёмки фотографии из различных источников.

Поддерживаемые источники (в порядке приоритета):
1. Дата из канала (channel) — явно указана при загрузке
2. EXIF metadata — DateTimeOriginal, DateTime, DateTimeDigitized
3. Штамп на кадре (OCR) — распознавание текста на фотографии
4. Имя файла — мессенджеры вырезают EXIF, но оставляют дату в имени. Кроме кадров
   камеры известного разрешения с непрочитанным штампом: у выгрузок с камер имя —
   момент выгрузки, а не съёмки
5. Соседние фотографии — определяется сервисом позже
6. Ручной ввод — вводит инженер
"""

import asyncio
import os
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from typing import Protocol

from PIL import Image, ImageOps

from app.domains.photo.models import DateSource


class InvalidImageError(Exception):
    """Ошибка при чтении или декодировании изображения."""

    pass


class StampOcr(Protocol):
    """Протокол чтения даты со штампа на кадре (LCT-13: через ML-сервис)."""

    async def read_date(self, content: bytes) -> date | None:
        """Прочитать дату со штампа. Возвращает None, если штамп не найден
        или не прошёл проверку — это не ошибка."""
        ...


class StampReadingLike(Protocol):
    """Результат чтения штампа: дата и профиль камеры (кадр известного разрешения).

    Необязательные поля контракта clean-mvp (`found`, `captured_at`, `confidence`,
    `method`) читаются через getattr: фейки тестов знают только дату и профиль.
    """

    @property
    def date(self) -> date | None: ...

    @property
    def profile(self) -> str | None: ...


@dataclass(frozen=True)
class _Reading:
    date: date | None
    profile: str | None = None


class NullStampOcr:
    """Заглушка: штамп никогда не читается."""

    async def read_date(self, content: bytes) -> date | None:
        return None


@dataclass(frozen=True)
class ImageInfo:
    """Информация об изображении."""

    width: int
    height: int
    format: str | None = None


@dataclass(frozen=True)
class ResolvedDate:
    """Разрешённая дата съёмки фотографии.

    `captured_at` — местное время съёмки, если источник его знает (штамп, EXIF, имя
    файла со временем). `hint` — дата-подсказка для ручного ввода, когда дату поставить
    нельзя (неуверенный штамп, кадр камеры без штампа, имя без времени у такого кадра).
    `uncertain_at` — неуверенно прочитанное время штампа: его может подтвердить серия
    кадров камеры (clean-mvp, confirm_uncertain).
    """

    captured_on: date | None
    source: DateSource | None
    captured_at: datetime | None = None
    hint: date | None = None
    uncertain_at: datetime | None = None


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


# Раньше этого года снимков стройки у нас не бывает: такие «даты» в имени — шум
# (номера, хэши), а не момент съёмки.
_FILENAME_MIN_YEAR = 2015
# Стройки ДГП — в Москве (UTC+3, без перехода на летнее время с 2014 года). Нужен,
# чтобы перевести Unix-время из имени в местную дату съёмки.
_SITE_UTC_OFFSET = timedelta(hours=3)
# Кандидаты из одного имени, расходящиеся сильнее, — противоречие: дату не ставим.
_FILENAME_MAX_SPREAD = timedelta(days=1)

# YYYYMMDD, YYYY-MM-DD, YYYY_MM_DD, YYYY.MM.DD (разделитель один и тот же), дальше
# необязательное время hhmmss / hh-mm-ss / hh.mm.ss через «_», «-», «T» или пробел.
# Покрывает IMG_20260927_020037, PXL_20260927_020037123, 2026-09-27 02.00.37,
# 20260927020037… (префикс имён от мессенджеров).
_FILENAME_DATE_RE = re.compile(
    r"(?<!\d)(20\d{2})([-_.]?)(\d{2})\2(\d{2})"
    r"(?:[-_T ]?(\d{2})[-_.:]?(\d{2})[-_.:]?(\d{2}))?"
)
# Unix-время в миллисекундах: 13 цифр отдельным числом или хвостом после
# 14-значного YYYYMMDDhhmmss (так называют файлы мессенджеры при пересылке).
_UNIX_MS_LEN = 13
_COMPACT_DATETIME_LEN = 14


def _filename_candidates(stem: str) -> list[datetime]:
    """Все моменты съёмки, которые удаётся прочитать из имени (время — местное)."""
    candidates: list[datetime] = []
    for match in _FILENAME_DATE_RE.finditer(stem):
        year, _, month, day, hh, mm, ss = match.groups()
        try:
            if hh is None:
                candidates.append(datetime(int(year), int(month), int(day)))
            else:
                candidates.append(
                    datetime(int(year), int(month), int(day), int(hh), int(mm), int(ss))
                )
        except ValueError:
            # 20261399…, 25:61:00 — не дата; хвост без времени пробуем отдельно.
            try:
                candidates.append(datetime(int(year), int(month), int(day)))
            except ValueError:
                continue

    for run in re.findall(r"\d+", stem):
        if len(run) == _UNIX_MS_LEN:
            ms = run
        elif len(run) == _COMPACT_DATETIME_LEN + _UNIX_MS_LEN:
            ms = run[_COMPACT_DATETIME_LEN:]
        else:
            continue
        try:
            moment = datetime.fromtimestamp(int(ms) / 1000, tz=UTC) + _SITE_UTC_OFFSET
        except (OverflowError, OSError, ValueError):
            continue
        candidates.append(moment.replace(tzinfo=None))
    return candidates


def parse_filename_date(filename: str | None, today: date | None = None) -> date | None:
    """Дата съёмки из имени файла.

    Мессенджеры и некоторые камеры при пересылке вырезают EXIF, но оставляют дату
    в имени: ``IMG_20260927_020037.jpg``, ``PXL_20260927_…``, ``2026-09-27 …``,
    ``202609270200371790463637087.jpg`` (префикс YYYYMMDDhhmmss + Unix-время в мс).

    Санити-проверки: дата не раньше 2015 года и не позже сегодняшней. Если в имени
    несколько кандидатов и они расходятся больше чем на сутки, дату не ставим —
    лучше отправить снимок в «Без даты», чем угадать неверно.

    Args:
        filename: Имя файла (путь допустим, берётся basename).
        today: Опорная дата для проверки «не в будущем» (по умолчанию — сегодня).

    Returns:
        Дата съёмки или None, если в имени нет правдоподобной даты.
    """
    if not filename:
        return None
    today = today or date.today()
    stem = os.path.splitext(os.path.basename(filename))[0]
    candidates = [
        c for c in _filename_candidates(stem) if _FILENAME_MIN_YEAR <= c.year and c.date() <= today
    ]
    if not candidates:
        return None
    if max(candidates) - min(candidates) > _FILENAME_MAX_SPREAD:
        return None
    # Первый кандидат — дата из начала имени в местном времени; Unix-время только
    # подтверждает её (и выручает, если кроме него в имени ничего нет).
    return candidates[0].date()


def parse_filename_datetime(filename: str | None, today: date | None = None) -> datetime | None:
    """Момент съёмки из имени файла, если в имени есть время (иначе None).

    Те же санити-проверки, что у `parse_filename_date`. Время нужно наблюдениям (светлое
    время суток) и подписям кадров; одной даты для этого мало.
    """
    if not filename or parse_filename_date(filename, today) is None:
        return None
    stem = os.path.splitext(os.path.basename(filename))[0]
    for match in _FILENAME_DATE_RE.finditer(stem):
        year, _, month, day, hh, mm, ss = match.groups()
        if hh is None:
            continue
        try:
            return datetime(int(year), int(month), int(day), int(hh), int(mm), int(ss))
        except ValueError:
            continue
    timed = [c for c in _filename_candidates(stem) if c.time() != datetime.min.time()]
    return timed[0] if timed else None


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
    4. Имя файла (parse_filename_date)
    """

    def __init__(self, ocr: StampOcr | None = None) -> None:
        """Инициализация DateResolver.

        Args:
            ocr: Объект с интерфейсом StampOcr для чтения даты со штампа.
                 Если None, используется NullStampOcr.
        """
        self.ocr = ocr if ocr is not None else NullStampOcr()

    async def resolve(
        self,
        content: bytes,
        channel_date: date | None = None,
        filename: str | None = None,
    ) -> ResolvedDate:
        """Разрешить дату съёмки из различных источников.

        Проходит цепочку источников в порядке приоритета:
        1. channel_date (если передан)
        2. EXIF DateTimeOriginal / DateTime / DateTimeDigitized
        3. Stamp OCR (читает дату и парсит)
        4. Имя файла (если передано)

        Исключения при чтении изображения распространяются.
        Исключения в OCR НЕ распространяются (результат: нет даты).

        Args:
            content: Байты JPEG/PNG изображения.
            channel_date: Дата из канала (если известна).
            filename: Исходное имя файла — последний источник перед соседними снимками.

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
            image = await asyncio.to_thread(self._open_image, content)
        except (OSError, Image.UnidentifiedImageError) as e:
            raise InvalidImageError(f"Failed to read image: {e}") from e
        except InvalidImageError:
            raise
        except Exception as e:
            raise InvalidImageError(f"Invalid or corrupt image: {e}") from e

        # 2. Уверенный штамп важнее EXIF (clean-mvp, R9): это время, которое человек
        # видит на кадре, а EXIF переписывается при пересохранении файла
        stamp = await self._read_stamp(content)
        stamp_at: datetime | None = getattr(stamp, "captured_at", None)
        method = getattr(stamp, "method", None)
        # OCR без эталонов уверенным не бывает: его дата — только подсказка
        if stamp.date is not None and method != "ocr":
            return ResolvedDate(
                captured_on=stamp.date, source=DateSource.STAMP, captured_at=stamp_at
            )

        # 3. EXIF metadata
        exif_at = self._extract_exif_datetime(image)
        if exif_at is not None:
            return ResolvedDate(
                captured_on=exif_at.date(), source=DateSource.METADATA, captured_at=exif_at
            )

        # 4. Штамп есть, но не прочитан уверенно: даты нет, время — подсказка; его может
        # подтвердить серия кадров камеры. Имя файла такому кадру не свидетель
        if getattr(stamp, "found", False) or (stamp.date is not None and method == "ocr"):
            hint = stamp_at.date() if stamp_at else stamp.date
            uncertain = stamp_at if method == "templates" else None
            return ResolvedDate(None, None, hint=hint, uncertain_at=uncertain)
        filename_at = parse_filename_datetime(filename)
        filename_date = parse_filename_date(filename)
        if stamp.profile is not None:
            # Кадр камеры, а строки штампа не нашлось: имя файла у выгрузок с камер —
            # момент выгрузки (49 кадров Березников «за 27.09» при съёмке в августе),
            # поэтому оно только подсказка для ручного ввода
            return ResolvedDate(None, None, hint=filename_date)

        # 5. Имя файла
        if filename_date is not None:
            return ResolvedDate(
                captured_on=filename_date, source=DateSource.FILENAME, captured_at=filename_at
            )

        # 6. Ничего не найдено
        return ResolvedDate(captured_on=None, source=None)

    @staticmethod
    def _open_image(content: bytes) -> Image.Image:
        image = Image.open(BytesIO(content))
        image.load()
        return image

    def _extract_exif_datetime(self, image: Image.Image) -> datetime | None:
        """Момент съёмки из EXIF (дата и время); без времени — полночь даты."""
        exif_data = image.getexif()
        if not exif_data:
            return None
        exif_ifd = exif_data.get_ifd(0x8769)
        for raw in (exif_ifd.get(0x9003), exif_data.get(0x0132), exif_ifd.get(0x9004)):
            if not raw:
                continue
            day = self._parse_exif_datetime(raw)
            if day is None:
                continue
            text = raw.decode("utf-8", "ignore") if isinstance(raw, bytes) else str(raw)
            try:
                return datetime.strptime(text.strip()[:19], "%Y:%m:%d %H:%M:%S")
            except ValueError:
                return datetime(day.year, day.month, day.day)
        return None

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

    async def _read_stamp(self, content: bytes) -> StampReadingLike:
        """Прочитать штамп через OCR-адаптер. Исключения НЕ распространяются —
        сеть/ML-сервис недоступен -> просто нет даты со штампа. Адаптер без `read`
        (только `read_date`) профиля камеры не знает."""
        try:
            read = getattr(self.ocr, "read", None)
            if read is not None:
                return await read(content)
            return _Reading(await self.ocr.read_date(content))
        except Exception:
            return _Reading(None)
