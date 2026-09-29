"""Произвольная таблица плана стройки → строки графика, через языковую модель.

Зачем. Встроенный разбор (бэкенд, `ScheduleParser`) узнаёт файл по названиям
колонок. Плану, где шапка названа иначе, разнесена на несколько строк или
спрятана под реквизитами, он отказывает. Здесь таблицу читает модель.

Границы (как у ассистента, D-020): модель **ничего не считает и не придумывает**,
она только раскладывает уже написанное по полям. Поэтому:

* формат ответа — одна строка на работу, поля через «|», а не JSON: слабая
  модель (qwen) чаще ломает скобки и кавычки, чем разделитель;
* каждая строка ответа проверяется по исходной: номер строки должен существовать,
  название — содержаться в ней, а дата — быть среди дат этой строки. Что не
  прошло, отбрасывается и попадает в `issues`, а не молча в график.

    python tools/schedule_llm.py plan.csv          # CLI: разобрать файл моделью
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

from suggest_stage_mapping import EmptyAnswer, ask  # noqa: E402

# Сколько строк таблицы отдаём модели за один вызов. Слабая модель на длинном
# списке теряет строки и путает номера; 25 строк — то, где она держится и где
# рассуждения reasoning-модели не съедают весь бюджет токенов.
CHUNK_ROWS = 25
# Первые строки файла (шапка, реквизиты) приклеиваются к каждому следующему куску
# как контекст: без них на втором куске модель не знает, что за колонки.
CONTEXT_ROWS = 6
# Верхняя граница: больше — это не график работ, а выгрузка чего-то другого.
MAX_ROWS = 400
MAX_CELL_CHARS = 200
# Рассуждения и ответ делят один бюджет (см. ask_report.ASK_MAX_TOKENS). На
# реальном плане (28.09.2026) при 4000 бюджет кончался до первого символа ответа
# (finish_reason=length), поэтому запас большой; если и его не хватило — кусок
# делится пополам (см. _ask_part).
MAX_TOKENS = 12000
CALL_TIMEOUT_S = 180
# Ниже этого размера кусок не делим: дальше только пустая трата вызовов.
MIN_SPLIT_ROWS = 6

NO_WORKS = "НЕТ"

SYSTEM = """Ты — разборщик таблиц для сервиса контроля строительных площадок.

КОНТЕКСТ.
Пользователь загрузил календарный план (график) строительства. Это таблица из Excel или CSV. \
Твоя задача — найти в ней строки с работами (этапами) и выписать для каждой: название работы, \
дату начала и дату окончания. Из твоего ответа программа построит список этапов. \
Ты не оцениваешь план, не исправляешь его и ничего не считаешь: ты только переписываешь то, что в таблице уже есть.

КАК ВЫГЛЯДИТ ВХОД.
Каждая строка таблицы записана так: [НОМЕР] ячейка | ячейка | ячейка
НОМЕР в квадратных скобках — номер строки в файле. Он нужен, чтобы программа нашла строку. \
Пустая ячейка записана как пробел между палочками.
Таблица может быть любой: шапка может называться как угодно, стоять не в первой строке, занимать две строки; \
колонок может быть много (номер, код, длительность, исполнитель, примечание) — они тебе не нужны. \
Перед шапкой часто стоят название документа, объекта, реквизиты подрядчика.
Строки с пометкой «КОНТЕКСТ» — это начало файла. Они показывают, какие в таблице колонки. Их самих не разбирай.

ЧТО ВЫДАВАТЬ.
Для каждой строки, в которой есть название работы, выведи ровно одну строку ответа такого вида:
НОМЕР|НАЗВАНИЕ|НАЧАЛО|ОКОНЧАНИЕ

Правила полей:
1. НОМЕР — число из квадратных скобок в начале входной строки. Не собственная нумерация плана (1.1, 2.3 и т.п.).
2. НАЗВАНИЕ — название работы, переписанное из строки как есть, без изменений. Номер пункта плана в название не включай.
3. НАЧАЛО и ОКОНЧАНИЕ — даты в формате ДД.ММ.ГГГГ (например 05.03.2026). Даты бери только из этой же строки. \
Если в таблице дата записана иначе (2026-03-05, 5 марта 2026, 05.03.26), перепиши её в формате ДД.ММ.ГГГГ.
4. Если даты нет — поставь вместо неё дефис: -
5. Если в строке одна дата и не понятно, начало это или окончание, — считай её началом, окончание поставь -.
6. Длительность («30 дней», «2 мес.») — не дата. Никогда не вычисляй дату из длительности. Ставь -.
7. Никогда не придумывай и не угадывай даты и названия. Нет в строке — ставь дефис.

КАКИЕ СТРОКИ ПРОПУСКАТЬ (ничего про них не выводить):
- шапку таблицы (названия колонок);
- название документа, объекта, адрес, реквизиты, подписи, «Утверждаю», «Согласовано»;
- итоговые строки («Итого», «Всего»);
- пустые строки и строки, где нет названия работы.
Строки-разделы («Раздел 1. Подготовительные работы») и вложенные работы (1.1, 1.2) выводи все, если в них есть название.

ФОРМАТ ОТВЕТА — СТРОГО.
- Только строки вида НОМЕР|НАЗВАНИЕ|НАЧАЛО|ОКОНЧАНИЕ, по одной на строку, в порядке возрастания НОМЕРА.
- Никаких пояснений, заголовков, комментариев, Markdown, нумерованных списков, кавычек, обратных апострофов.
- В названии не должно быть символа «|».
- Если в таблице нет ни одной работы, выведи одно слово: НЕТ

ПРИМЕР 1. Вход:
[1] График производства работ
[2] Объект: жилой дом, ул. Ленина, 5
[3] № | Наименование работ | Начало | Окончание | Длительность
[4] 1 | Земляные работы | 01.03.2026 | 20.03.2026 | 20
[5] 1.1 | Разработка котлована | 01.03.2026 | 10.03.2026 | 10
[6] 2 | Устройство фундамента | 21.03.2026 | 30.04.2026 | 41
[7] Итого |  |  |  | 71
Ответ:
4|Земляные работы|01.03.2026|20.03.2026
5|Разработка котлована|01.03.2026|10.03.2026
6|Устройство фундамента|21.03.2026|30.04.2026

ПРИМЕР 2. Вход:
[1] Этап | Срок начала | Срок завершения
[2] Монтаж каркаса | 2026-05-04 |
[3] Кровля | 5 июня 2026 | 25 июня 2026
[4] Благоустройство |  |
Ответ:
2|Монтаж каркаса|04.05.2026|-
3|Кровля|05.06.2026|25.06.2026
4|Благоустройство|-|-

ПРИМЕР 3. Вход:
[1] Реквизиты подрядчика: ООО «Строй»
[2] Подписи сторон
Ответ:
НЕТ"""


class Row(NamedTuple):
    """Строка исходной таблицы: номер в файле и ячейки как текст."""

    number: int
    cells: list[str]


class Work(NamedTuple):
    """Разобранная моделью и проверенная строка."""

    row: int
    name: str
    start: date | None
    end: date | None


class Issue(NamedTuple):
    """Строка, которую модель выдала, а проверка не пропустила."""

    row: int
    raw: str
    reason: str


class TooManyRows(ValueError):
    """Таблица длиннее MAX_ROWS."""


# ---------- вход ----------

def render_row(row: Row) -> str:
    """`[12] a | b | c` — вид строки для модели; «|» внутри ячеек заменяется."""
    cells = [re.sub(r"\s+", " ", c.replace("|", "/")).strip()[:MAX_CELL_CHARS] for c in row.cells]
    while cells and not cells[-1]:
        cells.pop()
    return f"[{row.number}] " + " | ".join(cells)


def chunks(rows: list[Row]) -> list[list[Row]]:
    if len(rows) > MAX_ROWS:
        raise TooManyRows(f"в таблице {len(rows)} строк, для разбора моделью допустимо до {MAX_ROWS}")
    return [rows[i:i + CHUNK_ROWS] for i in range(0, len(rows), CHUNK_ROWS)]


def build_prompt(part: list[Row], context: list[Row]) -> str:
    lines: list[str] = []
    if context:
        lines.append("КОНТЕКСТ (начало файла, не разбирай):")
        lines += [render_row(r) for r in context]
        lines.append("")
    lines.append("ТАБЛИЦА (разбери эти строки):")
    lines += [render_row(r) for r in part]
    lines += ["", "Ответ (только строки НОМЕР|НАЗВАНИЕ|НАЧАЛО|ОКОНЧАНИЕ, без пояснений, "
                  f"или слово {NO_WORKS}):"]
    return "\n".join(lines)


# ---------- даты ----------

_MONTHS = {"января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
           "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12}
_NUMERIC = re.compile(r"(?<!\d)(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?!\d)")
_ISO = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)")
_WORDS = re.compile(r"(?<!\d)(\d{1,2})\s+(" + "|".join(_MONTHS) + r")\s+(\d{4})", re.IGNORECASE)


def _make(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None  # «30.02.2027» — такого дня нет (см. parse_schedule.py)


def dates_in(text: str) -> set[date]:
    """Все даты, которые можно прочесть в тексте строки."""
    found: set[date | None] = set()
    for d, m, y in _NUMERIC.findall(text):
        year = int(y) + 2000 if len(y) == 2 else int(y)
        found.add(_make(year, int(m), int(d)))
    for y, m, d in _ISO.findall(text):
        found.add(_make(int(y), int(m), int(d)))
    for d, month, y in _WORDS.findall(text):
        found.add(_make(int(y), _MONTHS[month.lower()], int(d)))
    found.discard(None)
    return found  # type: ignore[return-value]


_ANSWER_DATE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")


def _answer_date(field: str) -> tuple[date | None, bool]:
    """(дата, корректно ли поле). Дефис и пустое поле — «даты нет», это корректно."""
    field = field.strip()
    if field in ("", "-", "—", "–"):
        return None, True
    match = _ANSWER_DATE.match(field)
    if not match:
        return None, False
    d = _make(int(match[3]), int(match[2]), int(match[1]))
    return d, d is not None


# ---------- ответ ----------

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_LINE = re.compile(r"^\s*\[?(\d+)\]?\s*\|(.*)$")


def _words(text: str) -> list[str]:
    return re.findall(r"[\w]+", text.lower().replace("ё", "е"))


def name_in_row(name: str, row_text: str) -> bool:
    """Название модели действительно взято из строки.

    Допускаем небольшие расхождения (модель обрезала хвост, поправила пробелы):
    не менее 70% слов названия должны встретиться в строке.
    """
    words = _words(name)
    if not words:
        return False
    source = set(_words(row_text))
    hits = sum(1 for w in words if w in source)
    return hits / len(words) >= 0.7


def parse_answer(text: str, part: list[Row]) -> tuple[list[Work], list[Issue]]:
    """Ответ модели → проверенные работы и отброшенные строки."""
    text = _THINK.sub("", text).replace("```", "")
    by_number = {r.number: r for r in part}
    works: list[Work] = []
    issues: list[Issue] = []
    seen: set[int] = set()

    for line in text.splitlines():
        line = line.strip().strip("`").strip()
        if not line or line.upper() == NO_WORKS:
            continue
        match = _LINE.match(line)
        if not match:
            continue
        number = int(match[1])
        row = by_number.get(number)
        if row is None or number in seen:
            continue  # чужой или повторный номер: строки нет в этом куске
        fields = [f.strip() for f in match[2].split("|")]
        if len(fields) < 3:
            issues.append(Issue(number, line, "модель вернула строку в неверном формате"))
            continue
        name, start_raw, end_raw = fields[0], fields[1], fields[2]
        raw = " | ".join(row.cells)
        row_text = " ".join(row.cells)
        if not name or not name_in_row(name, row_text):
            issues.append(Issue(number, raw, "название не найдено в строке файла"))
            continue
        seen.add(number)

        known = dates_in(row_text)
        picked: list[date | None] = []
        problem: str | None = None
        for label, field in (("начала", start_raw), ("окончания", end_raw)):
            value, ok = _answer_date(field)
            if not ok:
                problem = f"модель вернула дату {label} в неверном формате: {field}"
            elif value is not None and value not in known:
                problem = f"дата {label} {field} не найдена в строке файла"
            picked.append(value)
        if problem:
            issues.append(Issue(number, raw, problem))
            continue
        works.append(Work(number, name, picked[0], picked[1]))

    return works, issues


# ---------- прогон ----------

def _ask_part(part: list[Row], context: list[Row], base_url: str, api_key: str, model: str
              ) -> tuple[list[Work], list[Issue]]:
    """Один кусок таблицы → работы. Если ответ обрезан бюджетом токенов — делим пополам."""
    try:
        answer = ask(build_prompt(part, context), base_url, api_key, model,
                     timeout=CALL_TIMEOUT_S, system=SYSTEM, max_tokens=MAX_TOKENS)
    except EmptyAnswer:
        if len(part) < MIN_SPLIT_ROWS * 2:
            raise
        middle = len(part) // 2
        works, issues = [], []
        for half in (part[:middle], part[middle:]):
            w, i = _ask_part(half, context, base_url, api_key, model)
            works += w
            issues += i
        return works, issues
    return parse_answer(answer, part)


def parse_table(rows: list[Row], base_url: str, api_key: str, model: str) -> tuple[list[Work], list[Issue]]:
    """Разобрать всю таблицу кусками. Ошибки провайдера пробрасываются наружу."""
    rows = [r for r in rows if any(c.strip() for c in r.cells)]
    if not rows:
        return [], []
    context = rows[:CONTEXT_ROWS]
    works: list[Work] = []
    issues: list[Issue] = []
    for index, part in enumerate(chunks(rows)):
        part_works, part_issues = _ask_part(
            part, [] if index == 0 else context, base_url, api_key, model)
        works += part_works
        issues += part_issues
    works.sort(key=lambda w: w.row)
    issues.sort(key=lambda i: i.row)
    return works, issues


def main() -> int:
    """CLI: `python tools/schedule_llm.py plan.csv` — показать, что разобрала модель."""
    import csv

    from ask_report import describe_llm_error, llm_config

    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    cfg = llm_config()
    if not cfg:
        print("нет LLM_BASE_URL, LLM_API_KEY или LLM_MODEL", file=sys.stderr)
        return 1
    text = Path(sys.argv[1]).read_text(encoding="utf-8-sig")
    delimiter = ";" if text.count(";") > text.count(",") else ","
    table = [Row(i, r) for i, r in enumerate(csv.reader(text.splitlines(), delimiter=delimiter), 1)]
    try:
        works, issues = parse_table(table, *cfg)
    except Exception as exc:
        print(f"ошибка: {describe_llm_error(exc)}", file=sys.stderr)
        return 1
    for w in works:
        print(f"{w.row:>4}  {w.start or '-'}  {w.end or '-'}  {w.name}")
    for i in issues:
        print(f"{i.row:>4}  ПРОПУЩЕНО: {i.reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
