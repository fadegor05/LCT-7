"""Парсер расписания из CSV/XLSX файлов.

Чистая функция, без зависимостей от БД и DI.
"""

import csv
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from io import BytesIO, StringIO
from pathlib import Path

from openpyxl import load_workbook


class ScheduleFormatError(Exception):
    """Ошибка формата файла расписания."""

    pass


@dataclass(frozen=True)
class ParsedRow:
    """Распарсенная строка расписания."""

    name: str
    start: date | None
    end: date | None


@dataclass(frozen=True)
class ParsedIssue:
    """Ошибка при распарсивании строки."""

    row_number: int
    raw_row: str
    reason: str


@dataclass(frozen=True)
class ParseResult:
    """Результат парсирования расписания."""

    rows: list[ParsedRow]
    issues: list[ParsedIssue]
    rows_total: int


class ScheduleParser:
    """Парсер расписания из CSV/XLSX."""

    # Синонимы заголовков для колонок (нижний регистр, обрезанные)
    NAME_HEADERS = {"работа", "наименование", "название", "вид работ", "этап", "name"}
    START_HEADERS = {"начало", "дата начала", "старт", "start"}
    END_HEADERS = {"окончание", "дата окончания", "конец", "finish", "end"}

    def parse(self, filename: str, content: bytes) -> ParseResult:
        """Распарсить расписание из файла.

        Args:
            filename: имя файла (для определения формата)
            content: содержимое файла в байтах

        Returns:
            ParseResult с успешно распарсенными строками и ошибками

        Raises:
            ScheduleFormatError: если формат файла не поддерживается или файл пуст
        """
        ext = Path(filename).suffix.lower()

        if ext == ".xlsx":
            return self._parse_xlsx(content)
        elif ext == ".csv":
            return self._parse_csv(content)
        else:
            raise ScheduleFormatError(f"Неподдерживаемый формат: {ext}")

    def _parse_xlsx(self, content: bytes) -> ParseResult:
        """Распарсить XLSX файл."""
        buffer = BytesIO(content)
        wb = load_workbook(buffer, read_only=True, data_only=True)
        ws = wb.active
        if ws is None:
            raise ScheduleFormatError("Файл пуст")

        # Собрать все строки и их значения
        all_rows = []
        for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
            if row is None:
                continue
            # Проверить, содержит ли строка хотя бы одно непустое значение
            if any(cell is not None and str(cell).strip() for cell in row):
                all_rows.append((row_idx, row))

        if not all_rows:
            raise ScheduleFormatError("Файл пуст")

        # Найти заголовок в первых 10 непустых строк
        header = None
        header_row_idx = 0
        for idx, (_row_num, row) in enumerate(all_rows[:10]):
            candidate = self._find_header(row)
            if candidate:
                header = candidate
                header_row_idx = idx
                break

        if header is None:
            raise ScheduleFormatError("Не найдена колонка с названием работы")

        # Распарсить строки данных (все строки после заголовка)
        data_rows = all_rows[header_row_idx + 1 :]

        return self._parse_data_rows(data_rows, header)

    def _parse_csv(self, content: bytes) -> ParseResult:
        """Распарсить CSV файл."""
        # Попробовать различные кодировки
        text = None
        for encoding in ["utf-8-sig", "utf-8", "cp1251"]:
            try:
                text = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue

        if text is None:
            raise ScheduleFormatError("Не удалось декодировать CSV файл")

        # Разделить на строки
        lines = text.strip().split("\n")
        if not lines or not any(line.strip() for line in lines):
            raise ScheduleFormatError("Файл пуст")

        # Определить разделитель через csv.Sniffer
        delimiter = self._detect_delimiter(text)

        # Распарсить CSV
        reader = csv.reader(StringIO(text), delimiter=delimiter)

        # Собрать все строки
        all_rows = []
        for row_num, row in enumerate(reader, start=1):
            if row and any(cell.strip() for cell in row):
                all_rows.append((row_num, row))

        if not all_rows:
            raise ScheduleFormatError("Файл пуст")

        # Найти заголовок в первых 10 непустых строк
        header = None
        header_row_idx = 0
        for idx, (_row_num, row) in enumerate(all_rows[:10]):
            candidate = self._find_header(row)
            if candidate:
                header = candidate
                header_row_idx = idx
                break

        if header is None:
            raise ScheduleFormatError("Не найдена колонка с названием работы")

        # Распарсить строки данных
        data_rows = all_rows[header_row_idx + 1 :]

        return self._parse_data_rows(data_rows, header)

    def _detect_delimiter(self, text: str) -> str:
        """Определить разделитель CSV файла."""
        # Взять первые две строки как образец
        lines = text.split("\n")
        sample = "\n".join(lines[:2])

        try:
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample, delimiters=",;\t").delimiter
            return delimiter
        except csv.Error:
            # Fallback на точку с запятой
            return ";"

    def _find_header(self, row: list | tuple) -> dict[str, int] | None:
        """Найти индексы колонок имени, начала и окончания в строке.

        Returns:
            dict с ключами 'name', 'start', 'end' и индексами колонок,
            или None если не найдена колонка с названием
        """
        result = {}

        for idx, cell in enumerate(row):
            if cell is None:
                continue
            cell_str = str(cell).lower().strip()
            if cell_str in self.NAME_HEADERS:
                result["name"] = idx
            elif cell_str in self.START_HEADERS:
                result["start"] = idx
            elif cell_str in self.END_HEADERS:
                result["end"] = idx

        # Проверить, что найдена колонка с названием
        if "name" not in result:
            return None

        return result

    def _parse_data_rows(
        self, data_rows: Sequence[tuple[int, Sequence[object]]], header: dict[str, int]
    ) -> ParseResult:
        """Распарсить строки данных.

        Args:
            data_rows: список (row_number, row_data) кортежей
            header: словарь индексов колонок

        Returns:
            ParseResult с распарсенными строками и ошибками
        """
        rows = []
        issues = []
        rows_total = 0

        for row_num, row_data in data_rows:
            # Проверить, пуста ли строка
            if not any(str(cell).strip() for cell in row_data if cell is not None):
                # Пустая строка пропускается, но не считается в rows_total
                continue

            rows_total += 1

            # Получить значения колонок
            name = self._get_cell(row_data, header.get("name"))
            start_str = self._get_cell(row_data, header.get("start"))
            end_str = self._get_cell(row_data, header.get("end"))

            # Обрезать название и привести к строке
            if isinstance(name, str):
                name = name.strip()
            elif isinstance(name, (datetime, date)):
                # Если это дата/время, преобразуем в строку
                name = str(name)
            else:
                name = str(name) if name is not None else ""

            # Проверить пустое название
            if not name:
                raw_row = " | ".join(str(cell) if cell is not None else "" for cell in row_data)
                issues.append(
                    ParsedIssue(row_number=row_num, raw_row=raw_row, reason="Пустое название")
                )
                continue

            # Распарсить даты
            start = None
            end = None
            error_reason = None

            if start_str:
                start, parse_error = self._parse_date(start_str)
                if parse_error:
                    error_reason = parse_error

            if end_str and not error_reason:
                end, parse_error = self._parse_date(end_str)
                if parse_error:
                    error_reason = parse_error

            # Проверить, что окончание >= начало
            if not error_reason and start is not None and end is not None and end < start:
                error_reason = "Дата окончания раньше даты начала"

            if error_reason:
                raw_row = " | ".join(str(cell) if cell is not None else "" for cell in row_data)
                issues.append(ParsedIssue(row_number=row_num, raw_row=raw_row, reason=error_reason))
                continue

            # Успешно распарсена строка
            rows.append(ParsedRow(name=name, start=start, end=end))

        return ParseResult(rows=rows, issues=issues, rows_total=rows_total)

    def _get_cell(self, row: Sequence[object], idx: int | None) -> str | datetime | date | None:
        """Получить значение ячейки по индексу."""
        if idx is None or idx >= len(row):
            return None
        cell = row[idx]
        if cell is None:
            return None
        # Возвращать datetime/date объекты как есть, чтобы _parse_date мог их обработать
        if isinstance(cell, (datetime, date)):
            return cell
        return str(cell).strip() if str(cell).strip() else None

    def _parse_date(self, date_input: str | datetime | date) -> tuple[date | None, str | None]:
        """Распарсить дату из строки или datetime объекта.

        Returns:
            (date, None) если успешно, (None, error_reason) если ошибка
        """
        # Если это datetime объект, преобразовать в date
        if isinstance(date_input, datetime):
            return date_input.date(), None
        elif isinstance(date_input, date):
            return date_input, None

        # Работать со строкой
        date_str = date_input.strip() if isinstance(date_input, str) else str(date_input).strip()

        # Попробовать различные форматы
        formats = [
            ("%d.%m.%Y", "dd.mm.yyyy"),
            ("%Y-%m-%d", "yyyy-mm-dd"),
            ("%d/%m/%Y", "dd/mm/yyyy"),
        ]

        for fmt, _fmt_name in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                return parsed_date, None
            except ValueError:
                continue

        # Ошибка: не удалось распарсить
        return None, f"Не удалось разобрать дату: {date_str}"
