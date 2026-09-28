"""Тесты разбора плана моделью: формат ответа, проверка по исходной строке, ручка."""

import sys
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import schedule_llm  # noqa: E402
from schedule_llm import Row, parse_answer, parse_table
from service.app import app  # noqa: E402

TABLE = [
    Row(1, ["График работ"]),
    Row(2, ["№", "Наименование", "Начало", "Окончание"]),
    Row(3, ["1", "Земляные работы", "01.03.2026", "20.03.2026"]),
    Row(4, ["2", "Фундамент", "2026-03-21", ""]),
    Row(5, ["Итого"]),
]


def test_parse_answer_happy_path():
    works, issues = parse_answer(
        "3|Земляные работы|01.03.2026|20.03.2026\n4|Фундамент|21.03.2026|-", TABLE
    )
    assert [(w.row, w.name, w.start, w.end) for w in works] == [
        (3, "Земляные работы", date(2026, 3, 1), date(2026, 3, 20)),
        (4, "Фундамент", date(2026, 3, 21), None),
    ]
    assert issues == []


def test_parse_answer_tolerates_noise():
    """Рассуждения, ограждения кода, скобки вокруг номера — не ломают разбор."""
    answer = "<think>подумаю</think>\n```\n[3]|Земляные работы|01.03.2026|20.03.2026\n```"
    works, _ = parse_answer(answer, TABLE)
    assert [w.row for w in works] == [3]


def test_parse_answer_no_works():
    assert parse_answer("НЕТ", TABLE) == ([], [])


def test_invented_date_is_rejected():
    works, issues = parse_answer("3|Земляные работы|01.03.2026|25.03.2026", TABLE)
    assert works == []
    assert "не найдена в строке" in issues[0].reason


def test_invented_name_is_rejected():
    works, issues = parse_answer("3|Монтаж лифтов|01.03.2026|20.03.2026", TABLE)
    assert works == []
    assert issues[0].reason == "название не найдено в строке файла"


def test_bad_date_format_is_rejected():
    _, issues = parse_answer("3|Земляные работы|1 марта|20.03.2026", TABLE)
    assert "неверном формате" in issues[0].reason


def test_foreign_and_duplicate_rows_are_ignored():
    answer = "99|Что-то|-|-\n3|Земляные работы|-|-\n3|Земляные работы|01.03.2026|20.03.2026"
    works, issues = parse_answer(answer, TABLE)
    assert len(works) == 1 and works[0].start is None
    assert issues == []


def test_dates_in_formats():
    found = schedule_llm.dates_in("05.03.26 | 2026-04-01 | 5 апреля 2026 | 30.02.2027")
    assert found == {date(2026, 3, 5), date(2026, 4, 1), date(2026, 4, 5)}


def test_chunks_and_context(monkeypatch):
    rows = [Row(i, [f"Работа {i}", "01.01.2026", "02.01.2026"]) for i in range(1, 91)]
    prompts: list[str] = []

    def fake_ask(prompt, *_args, **_kwargs):
        prompts.append(prompt)
        return "НЕТ"

    monkeypatch.setattr(schedule_llm, "ask", fake_ask)
    parse_table(rows, "u", "k", "m")
    assert len(prompts) == 3
    assert "КОНТЕКСТ" not in prompts[0]
    assert "КОНТЕКСТ" in prompts[1]


def test_too_many_rows():
    rows = [Row(i, [f"Работа {i}"]) for i in range(1, schedule_llm.MAX_ROWS + 2)]
    with pytest.raises(schedule_llm.TooManyRows):
        schedule_llm.chunks(rows)


def test_system_prompt_states_format():
    assert "НОМЕР|НАЗВАНИЕ|НАЧАЛО|ОКОНЧАНИЕ" in schedule_llm.SYSTEM
    assert "ДД.ММ.ГГГГ" in schedule_llm.SYSTEM


# ---------- ручка ----------

BODY = {"rows": [{"row": r.number, "cells": r.cells} for r in TABLE]}


def test_endpoint_not_configured(monkeypatch):
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    import suggest_stage_mapping

    monkeypatch.setattr(suggest_stage_mapping, "from_env", lambda _key: None)
    import ask_report

    monkeypatch.setattr(ask_report, "from_env", lambda _key: None)
    assert TestClient(app).post("/parse-schedule", json=BODY).status_code == 503


def test_endpoint_ok(monkeypatch):
    import ask_report

    monkeypatch.setattr(ask_report, "llm_config", lambda: ask_report.LLMConfig("u", "k", "m"))
    monkeypatch.setattr(
        schedule_llm, "ask", lambda *a, **k: "3|Земляные работы|01.03.2026|20.03.2026"
    )
    response = TestClient(app).post("/parse-schedule", json=BODY)
    assert response.status_code == 200
    assert response.json()["rows"] == [
        {"row": 3, "name": "Земляные работы", "start": "2026-03-01", "end": "2026-03-20"}
    ]


def test_endpoint_llm_failure_is_504(monkeypatch):
    import ask_report

    monkeypatch.setattr(ask_report, "llm_config", lambda: ask_report.LLMConfig("u", "k", "m"))

    def boom(*_a, **_k):
        raise TimeoutError

    monkeypatch.setattr(schedule_llm, "ask", boom)
    assert TestClient(app).post("/parse-schedule", json=BODY).status_code == 504
