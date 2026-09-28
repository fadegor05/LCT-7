"""Фильтр вопросов и ответов ассистента по теме отчёта.

Предотвращает использование ассистента как общей LLM:
- вопросы вне темы отклоняются до вызова LLM (вопрос не стоит денег);
- ответы с кодом или не привязанные к отчёту не возвращаются.

Три уровня защиты:
1. Очистка вопроса от экранирования (блок </вопрос>, управляющие символы).
2. Фильтр вопроса: injection, codegen, off_topic.
3. Фильтр ответа: refused, code, too_long, ungrounded.
"""

import re
from typing import Optional

# Константы
REFUSAL_TOKEN = "[[ВНЕ_ОТЧЁТА]]"
NO_DATA_PHRASE = "в данных этого нет"
OUT_OF_SCOPE_MESSAGE = (
    "Ассистент отвечает только на вопросы по отчёту об этой площадке: "
    "этапы, отставание, отклонения, техника. Например: «где отставание и на сколько», "
    "«что с этапом 3»."
)
MAX_ANSWER_CHARS = 1500

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

# off_topic: поиск якорей отчёта и ключевых слов
TOPIC_STEMS = [
    "отстав",
    "задерж",
    "опереж",
    "срок",
    "этап",
    "площад",
    "объект",
    "стройк",
    "график",
    "план",
    "отклонен",
    "статус",
    "техник",
    "простаи",
    "простой",
    "наблюдени",
    "снимк",
    "провер",
    "уверенн",
    "гипотез",
    "критичн",
    "вердикт",
    "сводк",
    "свай",
    "котлован",
    "кран",
    "экскават",
    "самосвал",
    "бетон",
    "ограждени",
    "прогноз",
]

TOPIC_REGEXES = [
    re.compile(r"\bдн(я|ей|и|ь)\b"),
    re.compile(r"\bp\d+\b"),
]

# Регулярные выражения для фильтра ответов

# code: поиск кода в ответе
CODE_FENCE_PATTERN = re.compile(r"```")
CODE_LINE_PATTERN = re.compile(
    r"^\s*(def |class |import |from \S+ import |for .+ in .+:|while .+:|"
    r"if .+:|return\b|function\b|const |let |var |#include|public |SELECT )",
    re.MULTILINE,
)
CODE_BRACKET_PATTERN = re.compile(r"[{};\n]")


def report_anchors(data: dict) -> set[str]:
    """Все якори из отчёта: site_id, stage_ref, stage_code, stage_name в нижнем регистре.

    Ходит по дереву dict и list, собирая строки из ключей
    site_id, stage_ref, stage_code, stage_name.
    """
    anchors: set[str] = set()

    def walk(node):
        if isinstance(node, dict):
            # Собираем якори из известных ключей
            if "site_id" in node and isinstance(node["site_id"], str):
                anchors.add(node["site_id"].lower())
            if "stage_ref" in node and isinstance(node["stage_ref"], str):
                anchors.add(node["stage_ref"].lower())
            if "stage_code" in node and isinstance(node["stage_code"], str):
                anchors.add(node["stage_code"].lower())
            if "stage_name" in node and isinstance(node["stage_name"], str):
                anchors.add(node["stage_name"].lower())

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


def question_verdict(question: str, data: dict) -> Optional[str]:
    """Определение причины отклонения вопроса или None если он разрешён.

    Проверяет по порядку:
    1. injection — попытка переопределить инструкции
    2. codegen — запрос на генерацию кода
    3. off_topic — вопрос не связан с отчётом
    """
    lower_q = question.lower()

    # 1. Проверка на injection
    for pattern in INJECTION_PATTERNS:
        if pattern.search(lower_q):
            return "injection"

    # 2. Проверка на codegen
    if BARE_CODE_PATTERN.search(question):
        return "codegen"

    if CODEGEN_VERBS.search(lower_q):
        if CODEGEN_NOUNS.search(lower_q):
            return "codegen"

    # 3. Проверка на off_topic: есть ли якори отчёта или ключевые слова
    anchors = report_anchors(data)
    has_anchor = any(anchor in lower_q for anchor in anchors)
    has_topic = any(stem in lower_q for stem in TOPIC_STEMS)
    has_topic_regex = any(regex.search(lower_q) for regex in TOPIC_REGEXES)

    if not (has_anchor or has_topic or has_topic_regex):
        return "off_topic"

    return None


def answer_verdict(answer: str, data: dict) -> Optional[str]:
    """Определение причины отклонения ответа или None если он разрешён.

    Проверяет по порядку:
    1. refused — отказ модели (REFUSAL_TOKEN)
    2. code — ответ содержит код
    3. too_long — ответ длиннее MAX_ANSWER_CHARS
    4. ungrounded — ответ не привязан к отчёту
    """
    stripped = answer.strip()

    # 1. Проверка на refused: REFUSAL_TOKEN в ответе (stripped или с пробелами)
    if REFUSAL_TOKEN in stripped:
        return "refused"

    # 2. Проверка на code
    # Поиск кодового блока с ``` забором
    if CODE_FENCE_PATTERN.search(answer):
        return "code"

    # Поиск ≥ 2 строк, похожих на код
    code_lines = CODE_LINE_PATTERN.findall(answer)
    if len(code_lines) >= 2:
        return "code"

    # Проверка плотности скобок и точек с запятой (> 3%)
    special_chars = sum(1 for c in answer if c in "{};\n")
    if answer and len(answer) > 0:
        density = special_chars / len(answer)
        if density > 0.03:
            return "code"

    # 3. Проверка на too_long
    if len(answer) > MAX_ANSWER_CHARS:
        return "too_long"

    # 4. Проверка на ungrounded: нет якорей отчёта и нет NO_DATA_PHRASE
    anchors = report_anchors(data)
    lower_a = answer.lower()

    has_anchor = any(anchor in lower_a for anchor in anchors)
    has_no_data = NO_DATA_PHRASE in lower_a

    if not (has_anchor or has_no_data):
        return "ungrounded"

    return None
