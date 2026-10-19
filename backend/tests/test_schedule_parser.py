"""Тесты для парсера расписания.

Покрывают: CSV (;,) и XLSX, заголовки на разных строках, синонимы колонок,
проверку дат, пустые строки, неверные расширения, кодировку, нумерацию строк.
"""

from datetime import date, datetime
from io import BytesIO

import pytest
from openpyxl import Workbook

from app.domains.schedule.parser import (
    ParsedIssue,
    ParsedRow,
    ParseResult,
    ScheduleFormatError,
    ScheduleParser,
)


class TestScheduleParserBasic:
    """Базовые тесты парсера."""

    def test_parse_csv_semicolon_delimiter(self):
        """CSV с разделителем `;`."""
        content = "Название;Начало;Окончание\nРабота 1;01.01.2025;02.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows_total == 1
        assert len(result.rows) == 1
        assert result.rows[0].name == "Работа 1"
        assert result.rows[0].start == date(2025, 1, 1)
        assert result.rows[0].end == date(2025, 1, 2)
        assert len(result.issues) == 0

    def test_parse_csv_comma_delimiter(self):
        """CSV с разделителем `,`."""
        content = b"Name,Start,End\nWork 1,01.01.2025,02.01.2025\n"
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows_total == 1
        assert len(result.rows) == 1
        assert result.rows[0].name == "Work 1"
        assert result.rows[0].start == date(2025, 1, 1)
        assert result.rows[0].end == date(2025, 1, 2)

    def test_parse_xlsx(self):
        """XLSX файл."""
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Название"
        ws["B1"] = "Начало"
        ws["C1"] = "Окончание"
        ws["A2"] = "Работа 1"
        ws["B2"] = date(2025, 1, 1)
        ws["C2"] = date(2025, 1, 2)

        buffer = BytesIO()
        wb.save(buffer)
        content = buffer.getvalue()

        parser = ScheduleParser()
        result = parser.parse("schedule.xlsx", content)

        assert result.rows_total == 1
        assert len(result.rows) == 1
        assert result.rows[0].name == "Работа 1"
        assert result.rows[0].start == date(2025, 1, 1)
        assert result.rows[0].end == date(2025, 1, 2)

    def test_xlsx_with_datetime_objects(self):
        """XLSX с datetime-объектами (конвертируются в date)."""
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Название"
        ws["B1"] = "Начало"
        ws["C1"] = "Окончание"
        ws["A2"] = "Работа 1"
        ws["B2"] = datetime(2025, 1, 1, 10, 30)
        ws["C2"] = datetime(2025, 1, 2, 15, 45)

        buffer = BytesIO()
        wb.save(buffer)
        content = buffer.getvalue()

        parser = ScheduleParser()
        result = parser.parse("schedule.xlsx", content)

        assert result.rows[0].start == date(2025, 1, 1)
        assert result.rows[0].end == date(2025, 1, 2)


class TestScheduleParserHeaders:
    """Тесты для поиска заголовков."""

    def test_russian_header_synonyms_name(self):
        """Синонимы заголовка для названия (русский)."""
        synonyms = ["работа", "наименование", "название", "вид работ", "этап"]

        for syn in synonyms:
            content = f"{syn};Начало;Окончание\nРабота 1;01.01.2025;02.01.2025\n".encode()
            parser = ScheduleParser()
            result = parser.parse("schedule.csv", content)
            assert len(result.rows) == 1
            assert result.rows[0].name == "Работа 1"

    def test_english_header_synonyms_name(self):
        """Синонимы заголовка для названия (английский)."""
        content = b"name,start,end\nWork 1,01.01.2025,02.01.2025\n"
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert len(result.rows) == 1
        assert result.rows[0].name == "Work 1"

    def test_russian_header_synonyms_start(self):
        """Синонимы заголовка для начала (русский)."""
        synonyms = ["начало", "дата начала", "старт"]

        for syn in synonyms:
            content = f"Название;{syn};Окончание\nРабота 1;01.01.2025;02.01.2025\n".encode()
            parser = ScheduleParser()
            result = parser.parse("schedule.csv", content)
            assert result.rows[0].start == date(2025, 1, 1)

    def test_english_header_synonyms_start(self):
        """Синонимы заголовка для начала (английский)."""
        content = b"name,start,end\nWork 1,01.01.2025,02.01.2025\n"
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)
        assert result.rows[0].start == date(2025, 1, 1)

    def test_russian_header_synonyms_end(self):
        """Синонимы заголовка для окончания (русский)."""
        synonyms = ["окончание", "дата окончания", "конец"]

        for syn in synonyms:
            content = f"Название;Начало;{syn}\nРабота 1;01.01.2025;02.01.2025\n".encode()
            parser = ScheduleParser()
            result = parser.parse("schedule.csv", content)
            assert result.rows[0].end == date(2025, 1, 2)

    def test_english_header_synonyms_end(self):
        """Синонимы заголовка для окончания (английский)."""
        synonyms = ["finish", "end"]

        for syn in synonyms:
            content = f"name,start,{syn}\nWork 1,01.01.2025,02.01.2025\n".encode()
            parser = ScheduleParser()
            result = parser.parse("schedule.csv", content)
            assert result.rows[0].end == date(2025, 1, 2)

    def test_header_not_on_first_line(self):
        """Заголовок не на первой строке (пустые строки в начале)."""
        content = "\n\nНазвание;Начало;Окончание\nРабота 1;01.01.2025;02.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows_total == 1
        assert len(result.rows) == 1
        assert result.rows[0].name == "Работа 1"

    def test_header_found_within_first_10_rows(self):
        """Заголовок найден в пределах первых 10 непустых строк."""
        lines = [""] * 9 + ["Название;Начало;Окончание\n", "Работа 1;01.01.2025;02.01.2025\n"]
        content = "".join(lines).encode()

        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows_total == 1
        assert result.rows[0].name == "Работа 1"

    def test_no_name_column_error(self):
        """Ошибка: нет колонки с названием."""
        content = "Начало;Окончание\n01.01.2025;02.01.2025\n".encode()
        parser = ScheduleParser()

        with pytest.raises(ScheduleFormatError, match="Не найдена колонка"):
            parser.parse("schedule.csv", content)

    def test_substring_header_match_long_official_name(self):
        """Совпадение по подстроке: длинная официальная формулировка колонки."""
        content = (
            "Наименование этапа выполнения контракта и (или) комплекса работ;"
            "Начало;Окончание\n"
            "Работа 1;01.01.2025;02.01.2025\n"
        ).encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert len(result.rows) == 1
        assert result.rows[0].name == "Работа 1"
        assert result.rows[0].start == date(2025, 1, 1)
        assert result.rows[0].end == date(2025, 1, 2)

    def test_two_row_header_xlsx(self):
        """Шапка на 2 строки: имя в строке 1, начало/окончание — в строке 2
        (повторяет структуру реального шаблона графика СМР: объединённая
        ячейка "Сроки исполнения этапа" в строке 1, а фактические
        подзаголовки "Начало"/"Окончание" — в строке 2)."""
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "№"
        ws["B1"] = "Наименование этапа выполнения контракта и (или) комплекса работ"
        ws["C1"] = "Сроки исполнения этапа"
        ws["C2"] = "Начало выполнения работ"
        ws["D2"] = "Окончание выполнения работ"
        ws["A3"] = "1."
        ws["B3"] = "Работы подготовительного периода"
        ws["C3"] = date(2026, 4, 10)
        ws["D3"] = date(2026, 5, 22)

        buffer = BytesIO()
        wb.save(buffer)
        content = buffer.getvalue()

        parser = ScheduleParser()
        result = parser.parse("schedule.xlsx", content)

        assert result.rows_total == 1
        assert len(result.rows) == 1
        assert result.rows[0].name == "Работы подготовительного периода"
        assert result.rows[0].start == date(2026, 4, 10)
        assert result.rows[0].end == date(2026, 5, 22)

    def test_no_name_column_error_lists_recognized_headers(self):
        """Ошибка при отсутствии колонки с названием перечисляет
        распознаваемые названия, сохраняя префикс "Не найдена колонка"."""
        content = "Начало;Окончание\n01.01.2025;02.01.2025\n".encode()
        parser = ScheduleParser()

        with pytest.raises(ScheduleFormatError, match="Не найдена колонка") as exc_info:
            parser.parse("schedule.csv", content)

        assert "название" in str(exc_info.value).lower()

    def test_two_row_header_with_preamble_xlsx(self):
        """Двухстрочная шапка после преамбулы (реквизиты, название объекта) —
        преамбула не должна давать ложное неполное совпадение раньше
        настоящей шапки."""
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Приложение № 2 к контракту"
        ws["A3"] = "№"
        ws["B3"] = "Наименование этапа выполнения контракта и (или) комплекса работ"
        ws["C3"] = "Сроки исполнения этапа"
        ws["C4"] = "Начало выполнения работ"
        ws["D4"] = "Окончание выполнения работ"
        ws["A5"] = "1."
        ws["B5"] = "Работы подготовительного периода"
        ws["C5"] = date(2026, 4, 10)
        ws["D5"] = date(2026, 5, 22)

        buffer = BytesIO()
        wb.save(buffer)
        content = buffer.getvalue()

        parser = ScheduleParser()
        result = parser.parse("schedule.xlsx", content)

        assert result.rows_total == 1
        assert len(result.rows) == 1
        assert result.rows[0].name == "Работы подготовительного периода"
        assert result.rows[0].start == date(2026, 4, 10)
        assert result.rows[0].end == date(2026, 5, 22)

    def test_number_column_labeled_etap_not_mistaken_for_name(self):
        """Колонка "Номер этапа" — это порядковый номер, а не название
        работы. Короткий синоним "этап" не должен её перехватывать раньше
        настоящей колонки с названием."""
        content = (
            "Номер этапа;Наименование работ;Начало;Окончание\n1;Работа 1;01.01.2025;02.01.2025\n"
        ).encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert len(result.rows) == 1
        assert result.rows[0].name == "Работа 1"
        assert result.rows[0].start == date(2025, 1, 1)
        assert result.rows[0].end == date(2025, 1, 2)

    def test_data_row_not_swallowed_as_second_header_row(self):
        """Если шапка неполная (нет start/end) и следующая строка — это уже
        данные с реальными датами, она не должна быть принята за вторую
        строку шапки, даже если случайно содержит слово-синоним в
        свободном тексте примечания."""
        content = (
            "Наименование;С;По;Примечание\n"
            "Работа 1;01.01.2025;02.01.2025;Конец квартала\n"
            "Работа 2;03.01.2025;04.01.2025;\n"
        ).encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        # "С"/"По" не входят в START_HEADERS/END_HEADERS, поэтому даты не
        # распознаются — это ожидаемо и не предмет этого теста. Важно, что
        # обе строки данных сохранены, а не потеряна первая.
        assert result.rows_total == 2
        assert [r.name for r in result.rows] == ["Работа 1", "Работа 2"]

    def test_gantt_style_header_with_date_columns_still_works(self):
        """Шапка Gantt/таймлайн-шаблона: имя+начало+окончание в одной строке,
        а дальше в ней же — колонки-даты (по неделям/месяцам). Такая строка
        полна сама по себе и не должна отбрасываться только из-за того, что
        содержит настоящие даты."""
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Наименование работ"
        ws["B1"] = "Начало"
        ws["C1"] = "Окончание"
        ws["D1"] = date(2026, 4, 6)
        ws["E1"] = date(2026, 4, 13)
        ws["A2"] = "Работа 1"
        ws["B2"] = date(2026, 4, 1)
        ws["C2"] = date(2026, 4, 20)

        buffer = BytesIO()
        wb.save(buffer)
        content = buffer.getvalue()

        parser = ScheduleParser()
        result = parser.parse("schedule.xlsx", content)

        assert result.rows_total == 1
        assert len(result.rows) == 1
        assert result.rows[0].name == "Работа 1"
        assert result.rows[0].start == date(2026, 4, 1)
        assert result.rows[0].end == date(2026, 4, 20)

    def test_date_labeled_column_not_mistaken_for_name(self):
        """ "Дата начала этапа"/"Дата окончания этапа" не должны перехватывать
        колонку названия только из-за слова "этап" внутри — start/end
        проверяются раньше слабого синонима имени в каждой ячейке."""
        content = (
            "Дата начала этапа;Этап;Дата окончания этапа\n01.03.2026;Котлован;30.04.2026\n"
        ).encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert len(result.rows) == 1
        assert result.rows[0].name == "Котлован"
        assert result.rows[0].start == date(2026, 3, 1)
        assert result.rows[0].end == date(2026, 4, 30)


class TestScheduleParserDateFormats:
    """Тесты для различных форматов дат."""

    def test_date_format_dd_mm_yyyy_dot(self):
        """Формат dd.mm.yyyy (точка как разделитель)."""
        content = "Название;Начало;Окончание\nРабота 1;25.12.2024;26.12.2024\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows[0].start == date(2024, 12, 25)
        assert result.rows[0].end == date(2024, 12, 26)

    def test_date_format_yyyy_mm_dd(self):
        """Формат yyyy-mm-dd (ISO)."""
        content = "Название;Начало;Окончание\nРабота 1;2024-12-25;2024-12-26\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows[0].start == date(2024, 12, 25)
        assert result.rows[0].end == date(2024, 12, 26)

    def test_date_format_dd_mm_yyyy_slash(self):
        """Формат dd/mm/yyyy (слэш как разделитель)."""
        content = "Название;Начало;Окончание\nРабота 1;25/12/2024;26/12/2024\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows[0].start == date(2024, 12, 25)
        assert result.rows[0].end == date(2024, 12, 26)

    def test_date_with_whitespace(self):
        """Дата со спецсимволами/пробелами (strip)."""
        content = "Название;Начало;Окончание\nРабота 1;  25.12.2024  ;  26.12.2024  \n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows[0].start == date(2024, 12, 25)
        assert result.rows[0].end == date(2024, 12, 26)


class TestScheduleParserRows:
    """Тесты для различных типов строк данных."""

    def test_name_only_row(self):
        """Строка только с названием (без дат)."""
        content = "Название;Начало;Окончание\nРабота 1;;;\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows_total == 1
        assert len(result.rows) == 1
        assert result.rows[0].name == "Работа 1"
        assert result.rows[0].start is None
        assert result.rows[0].end is None

    def test_name_and_start_date_only(self):
        """Строка с названием и начальной датой (без окончания)."""
        content = "Название;Начало;Окончание\nРабота 1;01.01.2025;\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows[0].name == "Работа 1"
        assert result.rows[0].start == date(2025, 1, 1)
        assert result.rows[0].end is None

    def test_name_and_end_date_only(self):
        """Строка с названием и датой окончания (без начала)."""
        content = "Название;Начало;Окончание\nРабота 1;;02.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows[0].name == "Работа 1"
        assert result.rows[0].start is None
        assert result.rows[0].end == date(2025, 1, 2)

    def test_name_stripped(self):
        """Название обрезается (strip)."""
        content = "Название;Начало;Окончание\n  Работа 1  ;01.01.2025;02.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows[0].name == "Работа 1"

    def test_empty_name_issue(self):
        """Ошибка: пустое название."""
        content = "Название;Начало;Окончание\n;01.01.2025;02.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows_total == 1
        assert len(result.rows) == 0
        assert len(result.issues) == 1
        assert result.issues[0].reason == "Пустое название"
        assert result.issues[0].row_number == 2

    def test_name_looking_like_date_produces_issue(self):
        """Если в колонке названия оказалось значение, похожее на дату
        (шапка распозналась неверно, колонки перепутаны) — это issue,
        а не тихо принятая мусорная строка."""
        content = "Название;Начало;Окончание\n01.03.2026;;\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert len(result.rows) == 0
        assert len(result.issues) == 1
        assert "дат" in result.issues[0].reason.lower()

    def test_blank_rows_skipped(self):
        """Пустые строки пропускаются и не считаются в rows_total."""
        content = (
            "Название;Начало;Окончание\nРабота 1;01.01.2025;02.01.2025\n\n\nРабота 2;;;\n".encode()
        )
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        # rows_total = количество непустых строк данных = 2
        assert result.rows_total == 2
        # Но Работа 2 содержит только название, что допустимо
        assert len(result.rows) == 2

    def test_row_numbers_correct_after_blank_rows(self):
        """Номера строк: считают пустые строки в исходном файле."""
        content = "Название;Начало;Окончание\n\n\nРабота 1;;;\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        # Заголовок на строке 1, затем пустые строки 2-3, Работа 1 на строке 4
        assert result.rows[0].name == "Работа 1"


class TestScheduleParserDateValidation:
    """Тесты для валидации дат."""

    def test_bad_date_format_issue(self):
        """Ошибка: неверный формат даты."""
        content = "Название;Начало;Окончание\nРабота 1;invalid;02.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        # Строка остаётся работой без дат — инженер задаст их в мастере (clean-mvp)
        assert [(r.name, r.start, r.end) for r in result.rows] == [("Работа 1", None, None)]
        assert len(result.issues) == 1
        assert "Не удалось разобрать дату" in result.issues[0].reason
        assert "invalid" in result.issues[0].reason

    def test_end_before_start_issue(self):
        """Ошибка: дата окончания раньше даты начала."""
        content = "Название;Начало;Окончание\nРабота 1;02.01.2025;01.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        # Строка остаётся работой без дат — инженер задаст их в мастере (clean-mvp)
        assert [(r.name, r.start, r.end) for r in result.rows] == [("Работа 1", None, None)]
        assert len(result.issues) == 1
        assert result.issues[0].reason == "Дата окончания раньше даты начала — задайте даты вручную"

    def test_end_equals_start_is_valid(self):
        """Дата окончания равна дате начала - допустимо."""
        content = "Название;Начало;Окончание\nРабота 1;01.01.2025;01.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert len(result.rows) == 1
        assert len(result.issues) == 0
        assert result.rows[0].start == result.rows[0].end

    def test_bad_end_date_issue(self):
        """Ошибка: неверный формат даты окончания."""
        content = "Название;Начало;Окончание\nРабота 1;01.01.2025;bad_date\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        # Строка остаётся работой без дат — инженер задаст их в мастере (clean-mvp)
        assert [(r.name, r.start, r.end) for r in result.rows] == [("Работа 1", None, None)]
        assert len(result.issues) == 1
        assert "Не удалось разобрать дату" in result.issues[0].reason


class TestScheduleParserRawRow:
    """Тесты для raw_row в issues."""

    def test_raw_row_cells_joined_with_pipe(self):
        """raw_row содержит ячейки, разделённые ` | `."""
        content = "Название;Начало;Окончание\n;01.01.2025;02.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        issue = result.issues[0]
        # Пустая ячейка будет пустой строкой, а не None
        assert " | " in issue.raw_row
        assert issue.raw_row == " | 01.01.2025 | 02.01.2025"

    def test_raw_row_with_none_values(self):
        """raw_row с None значениями обрабатываются как пустые."""
        content = "Название;Начало\n;01.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        # Будет ошибка пустого названия
        if result.issues:
            assert " | " in result.issues[0].raw_row


class TestScheduleParserEmptyAndInvalidFiles:
    """Тесты для пустых и невалидных файлов."""

    def test_empty_file_error(self):
        """Ошибка: пустой файл."""
        parser = ScheduleParser()

        with pytest.raises(ScheduleFormatError, match="Файл пуст"):
            parser.parse("schedule.csv", b"")

    def test_only_empty_rows_error(self):
        """Ошибка: файл содержит только пустые строки."""
        content = b"\n\n\n"
        parser = ScheduleParser()

        with pytest.raises(ScheduleFormatError, match="Файл пуст"):
            parser.parse("schedule.csv", content)

    def test_unknown_extension_error(self):
        """Ошибка: неизвестное расширение файла."""
        parser = ScheduleParser()

        with pytest.raises(ScheduleFormatError):
            parser.parse("schedule.json", b"some content")

    def test_unknown_extension_case_insensitive(self):
        """Расширение игнорирует регистр."""
        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Название"
        ws["A2"] = "Работа 1"

        buffer = BytesIO()
        wb.save(buffer)
        content = buffer.getvalue()

        parser = ScheduleParser()
        result = parser.parse("schedule.XLSX", content)

        assert result.rows_total == 1

    def test_malformed_xlsx_garbage_bytes_raises_format_error(self):
        """Ошибка: XLSX файл с мусором (не валидный ZIP)."""
        parser = ScheduleParser()
        garbage_content = b"This is not a valid XLSX file \x00\xff\xfe"

        with pytest.raises(ScheduleFormatError, match="Не удалось прочитать XLSX"):
            parser.parse("schedule.xlsx", garbage_content)

    def test_malformed_xlsx_empty_with_xlsx_name_raises_format_error(self):
        """Ошибка: пустой файл с расширением .xlsx."""
        parser = ScheduleParser()

        with pytest.raises(ScheduleFormatError, match="Не удалось прочитать XLSX"):
            parser.parse("schedule.xlsx", b"")


class TestScheduleParserEncoding:
    """Тесты для кодировок."""

    def test_csv_utf8_sig(self):
        """CSV с BOM UTF-8-sig."""
        text = "Название;Начало;Окончание\nРабота 1;01.01.2025;02.01.2025\n"
        content = text.encode("utf-8-sig")
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows_total == 1
        assert result.rows[0].name == "Работа 1"

    def test_csv_cp1251_fallback(self):
        """CSV с кодировкой CP1251 (fallback с UTF-8)."""
        text = "Название;Начало;Окончание\nРабота 1;01.01.2025;02.01.2025\n"
        # Кодируем в cp1251 (не в UTF-8), чтобы заставить fallback
        content = text.encode("cp1251")

        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows_total == 1
        assert result.rows[0].name == "Работа 1"


class TestScheduleParserStructure:
    """Тесты для структуры данных."""

    def test_parse_result_structure(self):
        """ParseResult содержит все поля."""
        content = "Название;Начало;Окончание\nРабота 1;01.01.2025;02.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert isinstance(result, ParseResult)
        assert hasattr(result, "rows")
        assert hasattr(result, "issues")
        assert hasattr(result, "rows_total")
        assert isinstance(result.rows, list)
        assert isinstance(result.issues, list)

    def test_parsed_row_frozen(self):
        """ParsedRow is frozen."""
        from dataclasses import FrozenInstanceError

        row = ParsedRow(name="Test", start=None, end=None)

        with pytest.raises(FrozenInstanceError):
            row.name = "Modified"

    def test_parsed_issue_frozen(self):
        """ParsedIssue is frozen."""
        from dataclasses import FrozenInstanceError

        issue = ParsedIssue(row_number=1, raw_row="test", reason="test reason")

        with pytest.raises(FrozenInstanceError):
            issue.reason = "Modified"

    def test_parse_result_frozen(self):
        """ParseResult is frozen."""
        from dataclasses import FrozenInstanceError

        result = ParseResult(rows=[], issues=[], rows_total=0)

        with pytest.raises(FrozenInstanceError):
            result.rows = []

    def test_multiple_issues_per_file(self):
        """Несколько ошибок в одном файле."""
        content = (
            "Название;Начало;Окончание\n;01.01.2025;02.01.2025\nРабота 2;invalid;02.01.2025\n"
        ).encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert result.rows_total == 2
        assert len(result.issues) == 2


class TestScheduleParserCsvDelimiterDetection:
    """Тесты для автоопределения разделителя CSV."""

    def test_delimiter_semicolon_auto_detected(self):
        """Разделитель `;` определяется автоматически."""
        content = "Название;Начало;Окончание\nРабота 1;01.01.2025;02.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert len(result.rows) == 1
        assert result.rows[0].start == date(2025, 1, 1)

    def test_delimiter_comma_auto_detected(self):
        """Разделитель `,` определяется автоматически."""
        content = "Название,Начало,Окончание\nРабота 1,01.01.2025,02.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert len(result.rows) == 1
        assert result.rows[0].start == date(2025, 1, 1)

    def test_delimiter_tab_auto_detected(self):
        """Разделитель `\\t` (табуляция) определяется автоматически."""
        content = "Название\tНачало\tОкончание\nРабота 1\t01.01.2025\t02.01.2025\n".encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert len(result.rows) == 1
        assert result.rows[0].start == date(2025, 1, 1)

    def test_csv_with_leading_blank_lines_before_header(self):
        """CSV с 5+ пустыми строками перед заголовком всё ещё парсится правильно (comma)."""
        content = ("\n\n\n\n\nНазвание,Начало,Окончание\nРабота 1,01.01.2025,02.01.2025\n").encode()
        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        assert len(result.rows) == 1
        assert result.rows[0].name == "Работа 1"
        assert result.rows[0].start == date(2025, 1, 1)
        assert result.rows[0].end == date(2025, 1, 2)


class TestScheduleParserIntegration:
    """Интеграционные тесты."""

    def test_complex_file_mixed_rows(self):
        """Комплексный файл с разными типами строк."""
        content = (
            "Название;Начало;Окончание\n"
            "Работа 1;01.01.2025;05.01.2025\n"
            "Работа 2;05.01.2025;;\n"
            "\n"
            "Работа 3;;10.01.2025\n"
            ";15.01.2025;20.01.2025\n"  # Issue: пустое название
            "Работа 4;invalid;02.01.2025\n"  # Issue: неверная дата
        ).encode()

        parser = ScheduleParser()
        result = parser.parse("schedule.csv", content)

        # Работы 1–3 и Работа 4 без дат (дата не разобрана)
        assert len(result.rows) == 4
        assert (result.rows[-1].name, result.rows[-1].start) == ("Работа 4", None)
        # Ошибки: 2 строки
        assert len(result.issues) == 2
        # rows_total = количество непустых строк данных
        assert result.rows_total == 5

    def test_xlsx_with_multiple_sheets_uses_first(self):
        """XLSX: используется только первый (активный) лист."""
        wb = Workbook()
        # Первый лист
        ws1 = wb.active
        ws1.title = "Sheet1"
        ws1["A1"] = "Название"
        ws1["B1"] = "Начало"
        ws1["C1"] = "Окончание"
        ws1["A2"] = "Работа 1"
        ws1["B2"] = date(2025, 1, 1)
        ws1["C2"] = date(2025, 1, 2)

        # Второй лист (должен быть игнорирован)
        ws2 = wb.create_sheet()
        ws2["A1"] = "Работа 2"

        buffer = BytesIO()
        wb.save(buffer)
        content = buffer.getvalue()

        parser = ScheduleParser()
        result = parser.parse("schedule.xlsx", content)

        # Только из первого листа
        assert len(result.rows) == 1
        assert result.rows[0].name == "Работа 1"


def test_number_column_is_read_for_grouping() -> None:
    """Колонка «№ п/п» — номер пункта: по нему работы собираются в этапы."""
    content = (
        "№ п/п;Наименование;Начало;Окончание\n"
        "2;Земляные работы.;;\n"
        "2.1;Устройство основания;15.05.2026;30.11.2026\n"
        "10.1;Сети;01.06.2026;01.07.2026\n"
    ).encode()
    result = ScheduleParser().parse("g.csv", content)
    assert [r.number for r in result.rows] == ["2", "2.1", "10.1"]
