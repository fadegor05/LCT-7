"""Фильтр вопросов и ответов ассистента по теме отчёта.

Предотвращает использование ассистента как общей LLM:
- вопросы вне темы отклоняются до вызова LLM (вопрос не стоит денег);
- ответы с кодом или не привязанные к отчёту не возвращаются.

Три уровня защиты:
1. Очистка вопроса от экранирования (блок </вопрос>, управляющие символы).
2. Фильтр вопроса: injection, codegen, явный off_topic (остальное решает модель).
3. Фильтр ответа: refused, code, too_long, ungrounded.
"""

import re
import unicodedata

# Константы
REFUSAL_TOKEN = "[[ВНЕ_ОТЧЁТА]]"
NO_DATA_PHRASE = "в данных этого нет"
OUT_OF_SCOPE_MESSAGE = (
    "Ассистент отвечает только на вопросы по отчёту об этой площадке: "
    "этапы, отставание, отклонения, техника. Например: «где отставание и на сколько», "
    "«что с этапом 3»."
)
MAX_ANSWER_CHARS = 1500


def _normalize(text: str) -> str:
    """Нормализация текста: NFKC, удаление управляющих символов, ё→е, схлопывание пробелов."""
    # NFKC нормализация (fullwidth → normal)
    normalized = unicodedata.normalize("NFKC", text)

    # Удаляем все символы с категорией "C" (format, control, surrogate, private use, not assigned)
    # Это включает U+200B (zero-width space), U+200D (zero-width joiner), U+FEFF (BOM), soft hyphen и т.д.
    normalized = "".join(
        c for c in normalized if not unicodedata.category(c).startswith("C")
    )

    # Заменяем ё на е и Ё на Е
    normalized = normalized.replace("ё", "е").replace("Ё", "Е")

    # Схлопываем пробелы
    normalized = re.sub(r"\s+", " ", normalized)

    return normalized.strip()


def _has_anchor(text_lower: str, anchors: set[str]) -> bool:
    """Проверка наличия якоря в тексте с требованием границ слов.

    Якорь должен быть окружён границами слов (\\b), чтобы "p1" не матчился в "p10".
    """
    for anchor in anchors:
        pattern = r"(?<!\w)" + re.escape(anchor) + r"(?!\w)"
        if re.search(pattern, text_lower):
            return True
    return False


# Регулярные выражения для фильтра вопросов

# injection: инструкции переопределения, смена роли, попытки вытащить инструкции
INJECTION_PATTERNS = [
    re.compile(r"игнорируй.{0,20}(инструкц|предыдущ|всё|все)", re.IGNORECASE),
    re.compile(r"забудь.{0,20}(инструкц|предыдущ|всё|все)", re.IGNORECASE),
    re.compile(r"ты теперь", re.IGNORECASE),
    re.compile(r"притворись", re.IGNORECASE),
    re.compile(r"представь,?\s*что ты", re.IGNORECASE),
    re.compile(r"системн\w+\s+(промпт|инструкци)", re.IGNORECASE),
    re.compile(r"system prompt", re.IGNORECASE),
    re.compile(r"ignore\s+(all\s+|previous\s+)?", re.IGNORECASE),
    re.compile(r"act as", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"\bdan\b", re.IGNORECASE),
]

# codegen: запрос на генерацию кода с генерирующим глаголом и кодовым сущ.
CODEGEN_VERBS = re.compile(
    r"напиш\w*|сгенерир\w*|реализу\w*|создай|покажи|write|generate|implement",
    re.IGNORECASE,
)
CODEGEN_NOUNS = re.compile(
    r"функци\w*|скрипт\w*|программ\w*|алгоритм\w*|класс|код\b(?!\s*этап)|"
    r"на python|на js|на java|sql|sort|сортиров\w*",
    re.IGNORECASE,
)
BARE_CODE_PATTERN = re.compile(r"^(def |class |import |from .+ import |SELECT )", re.IGNORECASE)

# off_topic: только явные просьбы, не связанные со стройкой. Остальное решает модель:
# на вопрос не по отчёту она отвечает REFUSAL_TOKEN, а фильтр ответа проверяет привязку
# к отчёту. Белый список слов здесь не годится: он резал опечатки («отстование») и любую
# переформулировку («на какой стадии проект»).
OFF_TOPIC_PATTERNS = [
    re.compile(r"\bпогод\w*"),
    re.compile(r"\bперевед\w*|\bпереведи\b|\btranslate\b"),
    re.compile(r"\bанекдот\w*|\bшутк\w*|\bпошути\w*|\bстих\w*|\bпесн\w*"),
    re.compile(r"\bрецепт\w*"),
    re.compile(r"\bкурс\w*\s+(доллар|евро|валют|рубл|биткоин)\w*"),
    re.compile(r"\bреши\b|\bуравнени\w*"),
    # Арифметика: «сколько будет 2+2», «2*3=?»
    re.compile(r"\d\s*[+*^×]\s*\d"),
]

# Кириллица: вопрос целиком на другом языке — не к ассистенту по русскому отчёту
CYRILLIC_PATTERN = re.compile(r"[а-я]")

# Регулярные выражения для фильтра ответов

# code: поиск кода в ответе
CODE_LINE_PATTERN = re.compile(
    r"^\s*(def |class |import |from \S+ import |for .+ in .+:|while .+:|"
    r"if .+:|return\b|function\b|const |let |var |#include|public |SELECT )",
    re.MULTILINE,
)


def report_anchors(data: dict) -> set[str]:
    """Все якори из отчёта: site_id, stage_ref, stage_code, stage_name в нижнем регистре.

    Ходит по дереву dict и list, собирая строки из ключей
    site_id, stage_ref, stage_code, stage_name. Все якори нормализуются.
    """
    anchors: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            # Собираем якори из известных ключей
            if "site_id" in node and isinstance(node["site_id"], str):
                anchors.add(_normalize(node["site_id"]).lower())
            if "stage_ref" in node and isinstance(node["stage_ref"], str):
                anchors.add(_normalize(node["stage_ref"]).lower())
            if "stage_code" in node and isinstance(node["stage_code"], str):
                anchors.add(_normalize(node["stage_code"]).lower())
            if "stage_name" in node and isinstance(node["stage_name"], str):
                anchors.add(_normalize(node["stage_name"]).lower())

            # Рекурсивно ходим по значениям
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return anchors


def clean_question(question: str) -> str:
    """Очистка вопроса от управляющих символов и тегов.

    - Удаляет теги <вопрос>, </вопрос>, <отчёт>, </отчёт> (case-insensitive)
    - Переводит \n, \t, прочие управляющие символы в пробелы
    - Схлопывает пробелы
    - Удаляет ведущие и концевые пробелы
    """
    # Удаляем теги (case-insensitive)
    clean = re.sub(r"</?вопрос>", "", question, flags=re.IGNORECASE)
    clean = re.sub(r"</?отчёт>", "", clean, flags=re.IGNORECASE)

    # Переводим управляющие символы в пробелы
    clean = re.sub(r"[\n\t\r\x00-\x1f]", " ", clean)

    # Схлопываем пробелы
    clean = re.sub(r"\s+", " ", clean)

    # Удаляем ведущие и концевые пробелы
    return clean.strip()


def question_verdict(question: str, data: dict) -> str | None:
    """Определение причины отклонения вопроса или None если он разрешён.

    Проверяет по порядку:
    1. injection — попытка переопределить инструкции
    2. codegen — запрос на генерацию кода
    3. off_topic — явная просьба не по теме (погода, перевод, арифметика, не по-русски).
       Остальные вопросы идут в модель: она сама отказывает REFUSAL_TOKEN.
    """
    # Нормализуем вопрос
    normalized = _normalize(question)
    lower_q = normalized.lower()

    # 1. Проверка на injection
    for pattern in INJECTION_PATTERNS:
        if pattern.search(lower_q):
            return "injection"

    # 2. Проверка на codegen
    # Проверяем bare code на нормализованном и lstrip'нутом тексте
    stripped = lower_q.lstrip()
    if BARE_CODE_PATTERN.search(stripped):
        return "codegen"

    if CODEGEN_VERBS.search(lower_q):
        if CODEGEN_NOUNS.search(lower_q):
            return "codegen"

    # 3. Проверка на off_topic: только явные просьбы не по теме. Якорь отчёта («p1»,
    # «этап 3», код этапа) снимает подозрение: такой вопрос точно про отчёт.
    if _has_anchor(lower_q, report_anchors(data)):
        return None

    if not CYRILLIC_PATTERN.search(lower_q):
        return "off_topic"

    if any(pattern.search(lower_q) for pattern in OFF_TOPIC_PATTERNS):
        return "off_topic"

    return None


def answer_verdict(answer: str, data: dict) -> str | None:
    """Определение причины отклонения ответа или None если он разрешён.

    Проверяет по порядку:
    1. refused — отказ модели (REFUSAL_TOKEN)
    2. code — ответ содержит код
    3. too_long — ответ длиннее MAX_ANSWER_CHARS
    4. ungrounded — ответ не привязан к отчёту
    """
    # 1. Проверка на refused: REFUSAL_TOKEN в ответе (проверяем на оригинальном ответе)
    if REFUSAL_TOKEN in answer.strip():
        return "refused"

    # Нормализуем ответ
    normalized = _normalize(answer)
    stripped = normalized.strip()
    lower_a = normalized.lower()

    # 2. Проверка на code
    # Поиск кодового блока с ``` забором
    if "```" in answer:
        return "code"

    # Поиск ≥ 2 строк, похожих на код (проверяем в оригинальном ответе для multiline)
    code_lines = CODE_LINE_PATTERN.findall(answer)
    if len(code_lines) >= 2:
        return "code"

    # Проверка плотности скобок и точек с запятой (> 3%)
    # НЕ считаем \n в плотности
    special_chars = sum(1 for c in answer if c in "{};" )
    if answer and len(answer) > 0:
        density = special_chars / len(answer)
        if density > 0.03:
            return "code"

    # 3. Проверка на too_long
    if len(answer) > MAX_ANSWER_CHARS:
        return "too_long"

    # 4. Проверка на ungrounded: нет якорей отчёта и нет NO_DATA_PHRASE
    anchors = report_anchors(data)
    has_anchor = _has_anchor(lower_a, anchors)
    has_no_data = NO_DATA_PHRASE in lower_a

    if not (has_anchor or has_no_data):
        return "ungrounded"

    return None
