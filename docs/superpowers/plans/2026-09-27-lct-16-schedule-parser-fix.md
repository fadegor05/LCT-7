# LCT-16: Парсер графика — подстрочное совпадение шапки Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Сделать так, чтобы реальные официальные шаблоны графиков СМР (длинные формулировки колонок, шапка на 2 строки) успешно импортировались через `ScheduleParser`, без ручной правки файла пользователем.

**Architecture:** Точечное изменение внутренней логики `ScheduleParser._find_header` (точное совпадение → подстрока) плюс новый общий метод поиска шапки, который умеет объединять две соседние строки для двухстрочной/составной шапки. Публичный контракт `parse()` не меняется. Отдельно — обновление текста подсказки на фронтенде.

**Tech Stack:** Python 3.11, openpyxl, pytest (backend); React + Vitest + Testing Library (frontend).

**Spec:** `docs/superpowers/plans/2026-09-27-lct-16-schedule-parser-spec.md`

## Global Constraints

- Публичная сигнатура `ScheduleParser.parse(filename: str, content: bytes) -> ParseResult` не меняется.
- Сообщение об ошибке при отсутствии колонки с названием обязано продолжать начинаться с `"Не найдена колонка"` (существующие тесты матчатся по этому префиксу через `pytest.raises(..., match="Не найдена колонка")`).
- Весь существующий набор `backend/tests/test_schedule_parser.py` обязан проходить без изменений — это единственная регрессионная гарантия того, что подстрочное совпадение не сломало точные синонимы.
- Никаких изменений в БД, моделях, роутере или API-контракте `schedule` — только `parser.py` и его тесты, плюс текст подсказки на фронтенде.

## Review Focus

- Совпадение по подстроке не должно давать ложных срабатываний на уже существующих точных синонимах (например, «начало» не должно случайно матчиться как «name»-колонка).
- Двухстрочное объединение шапки не должно ломать однострочный случай (весь текущий набор тестов — гарантия).
- `header_row_idx`, возвращаемый `_locate_header`, должен указывать на **последнюю** строку шапки, чтобы данные не начинались preждевременно (с середины шапки).
- Пустые/`None`-ячейки при объединении двух строк не должны затирать непустое значение из другой строки.
- Обновлённый текст ошибки не должен сломать `test_no_name_column_error`, который матчится по `match="Не найдена колонка"` (это substring-match, не точное равенство — расширение текста безопасно).

---

## Task 1: Подстрочное совпадение шапки + поддержка двухстрочной шапки в парсере

**Files:**
- Modify: `backend/app/domains/schedule/parser.py`
- Test: `backend/tests/test_schedule_parser.py`

**Interfaces:**
- Consumes: ничего нового — работает с уже существующими `NAME_HEADERS`, `START_HEADERS`, `END_HEADERS` (не менять содержимое этих множеств).
- Produces: то же самое поведение `parse()` для клиентов (`schedule/service.py` этот файл не трогает и не должен трогаться).

- [ ] **Step 1: Написать падающие тесты на новое поведение**

Добавь в `backend/tests/test_schedule_parser.py`, в класс `TestScheduleParserHeaders`, три новых теста:

```python
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
```

Run: `cd backend && uv run pytest tests/test_schedule_parser.py -v`
Expected: FAIL — `test_substring_header_match_long_official_name` и
`test_two_row_header_xlsx` терпят неудачу с `ScheduleFormatError: Не найдена
колонка с названием работы` (текущий код требует точного совпадения и
однострочной шапки). `test_no_name_column_error_lists_recognized_headers`
падает на `assert "название" in ...` (текущий текст ошибки не перечисляет
названия).

- [ ] **Step 2: Заменить точное совпадение в `_find_header` на подстрочное**

В `backend/app/domains/schedule/parser.py` замени метод `_find_header` целиком:

> **Примечание (после итогового ревью всей ветки):** Первая версия
> `_find_header` ниже совпадала по подстроке в один проход, что позволяло
> короткому синониму «этап» перехватывать служебные колонки вроде
> «№ этапа»/«Номер этапа» (это номер, а не название работы). Финальная
> реализация в `parser.py` — двухпроходная: сначала пробуются «сильные»
> синонимы (`NAME_HEADERS - WEAK_NAME_SYNONYMS`), и только если имя не
> нашлось — разрешается и «этап» (через новый `WEAK_NAME_SYNONYMS = {"этап"}`
> и приватный хелпер `_match_header_row(row, allow_weak_name)`). См. итоговый
> код в `backend/app/domains/schedule/parser.py` — он то, что реально
> задеплоено.

```python
    def _find_header(self, row: list | tuple) -> dict[str, int] | None:
        """Найти индексы колонок имени, начала и окончания в строке.

        Совпадение — по подстроке, а не по точному равенству: реальные
        шаблоны используют длинные официальные формулировки («Наименование
        этапа выполнения контракта и (или) комплекса работ и (или)...»),
        которые не совпадают целиком ни с одним коротким синонимом, хотя
        явно его содержат. При нескольких ячейках одной категории побеждает
        первая найденная — детерминированно и безопасно для двухстрочного
        случая, где могут встретиться и короткая, и длинная формулировки.

        Returns:
            dict с ключами 'name', 'start', 'end' и индексами колонок,
            или None если не найдена колонка с названием
        """
        result: dict[str, int] = {}

        for idx, cell in enumerate(row):
            if cell is None:
                continue
            cell_str = str(cell).lower().strip()
            if not cell_str:
                continue
            if "name" not in result and any(syn in cell_str for syn in self.NAME_HEADERS):
                result["name"] = idx
            elif "start" not in result and any(syn in cell_str for syn in self.START_HEADERS):
                result["start"] = idx
            elif "end" not in result and any(syn in cell_str for syn in self.END_HEADERS):
                result["end"] = idx

        # Проверить, что найдена колонка с названием
        if "name" not in result:
            return None

        return result
```

(Этот единопроходный вариант — то, что было применено в рамках Task 1 этого
плана. Итоговая, двухпроходная версия описана в примечании выше.)

- [ ] **Step 3: Добавить `_merge_header_rows` и `_locate_header`**

Сразу после метода `_find_header` (перед `_parse_data_rows`) добавь два новых приватных метода:

```python
    def _merge_header_rows(
        self, row: Sequence[object], next_row: Sequence[object]
    ) -> list[object]:
        """Объединить шапку из двух соседних строк в одну для матчинга.

        Официальные шаблоны часто разносят подзаголовки по двум строкам
        (например, объединённая ячейка "Сроки исполнения этапа" в строке N,
        а фактические "Начало"/"Окончание" — в строке N+1). Берём непустую
        ячейку из первой строки, иначе — из второй.
        """
        length = max(len(row), len(next_row))
        merged: list[object] = []
        for i in range(length):
            first = row[i] if i < len(row) else None
            second = next_row[i] if i < len(next_row) else None
            merged.append(first if (first is not None and str(first).strip()) else second)
        return merged

    def _locate_header(
        self, all_rows: Sequence[tuple[int, Sequence[object]]]
    ) -> tuple[dict[str, int], int] | None:
        """Найти шапку в первых 10 непустых строках.

        Пробует сначала текущую строку как есть, затем — объединение
        текущей и следующей строки (для шапки, разбитой на 2 строки).

        Returns:
            (header, header_row_idx), где header_row_idx — индекс в
            all_rows последней строки шапки (данные начинаются со
            следующей записи), либо None, если шапка не найдена.
        """
        limit = min(10, len(all_rows))
        for idx in range(limit):
            row = all_rows[idx][1]
            candidate = self._find_header(row)
            if candidate:
                return candidate, idx

            if idx + 1 < limit:
                next_row = all_rows[idx + 1][1]
                merged = self._merge_header_rows(row, next_row)
                candidate = self._find_header(merged)
                if candidate:
                    return candidate, idx + 1

        return None
```

`Sequence` уже импортирован в файле (`from collections.abc import Sequence`) — новый импорт не нужен.

> **Примечание (после итогового ревью всей ветки):** эта первая версия
> `_merge_header_rows`/`_locate_header` содержала 2 реальных бага, найденных
> и исправленных отдельным финальным фиксом (см. коммит "fix(schedule): fix
> header detection on preamble, №-этапа, and data-row edge cases"):
>
> 1. `_merge_header_rows` предпочитала непустую ячейку из **первой** строки,
>    а не из второй. В реальном шаблоне заголовок-категория (например,
>    "Сроки исполнения этапа") "оседает" в верхней строке объединённого
>    Excel-диапазона, а конкретные подписи колонок ("Начало"/"Окончание") —
>    в строке под ней; предпочтение первой строки в некоторых раскладках
>    затирало нужные подзаголовки. Финальная версия предпочитает **вторую**
>    строку, иначе — первую.
> 2. `_locate_header` возвращалась на первом же частичном совпадении (даже
>    только с `name`, без `start`/`end`) вместо того, чтобы просмотреть всё
>    окно и выбрать самый полный кандидат. Преамбула перед реальной шапкой
>    (реквизиты подрядчика, название объекта), случайно содержащая
>    «наименование», из-за этого перехватывала поиск раньше настоящей
>    шапки. Финальная версия сканирует всё окно из 10 строк, пропускает
>    строки, похожие на данные (новый метод `_row_has_date_value` — строка с
>    настоящей датой не может быть шапкой, ни сама, ни как вторая строка
>    объединения), и выбирает самый полный найденный кандидат, останавливаясь
>    сразу только при полном совпадении всех трёх колонок.
>
> Актуальный код — в `backend/app/domains/schedule/parser.py`.

- [ ] **Step 4: Использовать `_locate_header` в `_parse_xlsx` и `_parse_csv`**

В `_parse_xlsx` замени блок:

```python
        # Найти заголовок в первых 10 непустых строках
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
```

на:

```python
        located = self._locate_header(all_rows)
        if located is None:
            raise ScheduleFormatError(
                "Не найдена колонка с названием работы. Распознаваемые названия: "
                + ", ".join(sorted(self.NAME_HEADERS))
            )
        header, header_row_idx = located

        # Распарсить строки данных (все строки после заголовка)
        data_rows = all_rows[header_row_idx + 1 :]

        return self._parse_data_rows(data_rows, header)
```

Сделай ровно ту же замену в `_parse_csv` (там идентичный блок с тем же
комментарием и той же структурой цикла).

- [ ] **Step 5: Прогнать тесты и убедиться, что новые проходят, а старые не сломались**

Run: `cd backend && uv run pytest tests/test_schedule_parser.py -v`
Expected: PASS — все тесты файла (старые и три новых) зелёные.

Затем прогони весь backend-набор, чтобы убедиться, что изменение не задело ничего смежного (например, `test_schedule_service.py`, `test_schedule_router.py`):

Run: `cd backend && uv run pytest -q`
Expected: PASS — весь набор зелёный, без новых failures.

Также прогони линтер:

Run: `cd backend && uv run ruff check . && uv run ruff format --check .`
Expected: без ошибок (не забудь `uv run ruff format .`, если формат не совпал, и перезапустить check).

- [ ] **Step 6: Commit**

```bash
git add backend/app/domains/schedule/parser.py backend/tests/test_schedule_parser.py
git commit -m "fix(schedule): match header columns by substring, support 2-row header

Real official СМР schedule templates use long formal column phrasing
and split start/end sub-headers onto the next row (merged-cell style).
_find_header now matches by substring instead of exact equality, and a
new _locate_header helper tries the current row, then a merge of the
current and next row, before giving up."
```

---

## Task 2: Обновить подсказку загрузки графика на фронтенде

**Files:**
- Modify: `frontend/src/pages/NewSitePage.tsx`
- Test: `frontend/src/pages/NewSitePage.test.tsx`

**Interfaces:**
- Consumes: ничего из Task 1 — независимая правка текста, не зависит от бэкенда.
- Produces: ничего, потребляется только пользователем интерфейса.

- [ ] **Step 1: Написать падающий тест на новый текст подсказки**

В `frontend/src/pages/NewSitePage.test.tsx` добавь новый тест (в `describe('creating a site', ...)`, рядом с существующим `it('walks through both steps', ...)`):

```typescript
  it('shows recognized column names in the upload hint', () => {
    renderRoute('/sites/new')
    expect(
      screen.getByText(
        'CSV или XLSX до 5 МБ: колонки «Название» (или «Наименование»/«Этап»), «Начало», «Окончание». Техника в файле не нужна.',
      ),
    ).toBeInTheDocument()
  })
```

Run: `cd frontend && pnpm vitest run src/pages/NewSitePage.test.tsx`
Expected: FAIL — новый текст подсказки ещё не существует в компоненте (текущий текст короче и не перечисляет колонки).

- [ ] **Step 2: Обновить текст подсказки в `NewSitePage.tsx`**

В `frontend/src/pages/NewSitePage.tsx` найди:

```typescript
          <FileDrop
            title="Перетащите файл графика"
            hint="CSV или XLSX до 5 МБ: этапы работ и плановые даты. Техника в файле не нужна."
```

Замени `hint` на:

```typescript
          <FileDrop
            title="Перетащите файл графика"
            hint="CSV или XLSX до 5 МБ: колонки «Название» (или «Наименование»/«Этап»), «Начало», «Окончание». Техника в файле не нужна."
```

(Остальные пропсы `FileDrop` — `accept`, `disabled`, `onFiles` — не трогать.)

- [ ] **Step 3: Прогнать тесты**

Run: `cd frontend && pnpm vitest run src/pages/NewSitePage.test.tsx`
Expected: PASS — оба теста файла (существующий `walks through both steps` и новый) зелёные.

Затем прогони полный фронтенд-чек:

Run: `cd frontend && pnpm check`
Expected: PASS — tsc, eslint, stylelint, prettier, vitest с покрытием — без новых failures. Если `prettier`/`eslint --fix` перекроят форматирование строки — это ожидаемо, прогони `pnpm front-pretty` при необходимости и повтори `pnpm check`.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/NewSitePage.tsx frontend/src/pages/NewSitePage.test.tsx
git commit -m "fix(schedule-upload): list recognized column names in upload hint

The old hint didn't say which column names the parser recognizes,
so users hit a confusing 'column not found' error with no way to
guess the fix."
```
