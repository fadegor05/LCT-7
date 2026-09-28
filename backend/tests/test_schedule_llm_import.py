"""Импорт графика в трёх режимах (auto / llm / builtin) и адаптер LLM-разбора."""

from datetime import date

import httpx
import pytest
from dishka import AsyncContainer
from httpx import AsyncClient

from app.adapters.ml.assistant import AssistantBadRequest, AssistantTimeout, AssistantUnavailable
from app.adapters.ml.schedule_llm import (
    HttpScheduleLlmClient,
    LlmScheduleIssue,
    LlmScheduleResult,
    LlmScheduleRow,
    NullScheduleLlmClient,
    ScheduleLlmClient,
)
from app.core.settings import AssistantSettings
from app.domains.schedule.parser import ScheduleParser
from tests.fakes import FakeScheduleLlmClient
from tests.test_schedule_router import seed_stand_user

STANDARD = "Название;Начало;Окончание\nФундамент;01.01.2026;10.01.2026\n".encode()
# Шапка названа так, что встроенный парсер её не узнаёт
ARBITRARY = (
    "Вид деятельности;С;По\nФундамент;01.01.2026;10.01.2026\nСтены;11.01.2026;20.01.2026\n".encode()
)
LLM_RESULT = LlmScheduleResult(
    rows=[
        LlmScheduleRow(2, "Фундамент", date(2026, 1, 1), date(2026, 1, 10)),
        LlmScheduleRow(3, "Стены", date(2026, 1, 11), None),
    ],
    issues=[LlmScheduleIssue(4, "Кровля | 99.99.2026", "дата не найдена в строке файла")],
)


async def _site(
    client: AsyncClient, container: AsyncContainer
) -> tuple[str, FakeScheduleLlmClient]:
    await seed_stand_user(container)
    site_id = (await client.post("/sites", json={"name": "S"})).json()["id"]
    fake = await container.get(ScheduleLlmClient)
    assert isinstance(fake, FakeScheduleLlmClient)
    fake.result, fake.error, fake.calls = LLM_RESULT, None, []
    return site_id, fake


async def _import(client: AsyncClient, site_id: str, content: bytes, mode: str | None):
    return await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("plan.csv", content, "text/csv")},
        data={"mode": mode} if mode else None,
    )


async def test_auto_uses_builtin_when_it_works(client, container) -> None:
    site_id, fake = await _site(client, container)
    response = await _import(client, site_id, STANDARD, None)
    assert response.status_code == 201
    assert response.json()["parse_method"] == "builtin"
    assert fake.calls == []


async def test_auto_falls_back_to_llm(client, container) -> None:
    site_id, fake = await _site(client, container)
    response = await _import(client, site_id, ARBITRARY, "auto")
    assert response.status_code == 201
    data = response.json()
    assert data["parse_method"] == "llm"
    assert [s["name"] for s in data["stages"]] == ["Фундамент", "Стены"]
    assert data["stages"][1]["planned_end"] is None
    assert data["rows_total"] == 3 and data["rows_parsed"] == 2
    assert data["issues"][0]["row_number"] == 4
    # Модели отдана «сырая» таблица вместе с шапкой
    assert fake.calls[0][0] == (1, ["Вид деятельности", "С", "По"])


async def test_auto_reports_builtin_reason_when_llm_unavailable(client, container) -> None:
    site_id, fake = await _site(client, container)
    fake.error = AssistantUnavailable("LLM-разбор не настроен")
    response = await _import(client, site_id, ARBITRARY, "auto")
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "Не найдена колонка" in detail and "не настроен" in detail


async def test_auto_keeps_old_schedule_when_import_fails(client, container) -> None:
    site_id, fake = await _site(client, container)
    assert (await _import(client, site_id, STANDARD, "builtin")).status_code == 201
    fake.error = AssistantTimeout()
    assert (await _import(client, site_id, ARBITRARY, "auto")).status_code == 422
    stages = (await client.get(f"/sites/{site_id}/schedule")).json()["stages"]
    assert [s["name"] for s in stages] == ["Фундамент"]


async def test_llm_mode_skips_builtin(client, container) -> None:
    site_id, fake = await _site(client, container)
    response = await _import(client, site_id, STANDARD, "llm")
    assert response.status_code == 201
    assert response.json()["parse_method"] == "llm"
    assert len(fake.calls) == 1


async def test_llm_mode_error_is_propagated(client, container) -> None:
    site_id, fake = await _site(client, container)
    fake.error = AssistantTimeout()
    response = await _import(client, site_id, STANDARD, "llm")
    assert response.status_code == 504
    assert response.json()["code"] == "assistant_timeout"


async def test_llm_mode_empty_result_is_422(client, container) -> None:
    site_id, fake = await _site(client, container)
    fake.result = LlmScheduleResult(rows=[], issues=[])
    assert (await _import(client, site_id, STANDARD, "llm")).status_code == 422


async def test_llm_rejects_reversed_dates(client, container) -> None:
    site_id, fake = await _site(client, container)
    fake.result = LlmScheduleResult(
        rows=[LlmScheduleRow(2, "Работа", date(2026, 2, 1), date(2026, 1, 1))], issues=[]
    )
    data = (await _import(client, site_id, STANDARD, "llm")).json()
    assert data["rows_parsed"] == 0
    assert data["issues"][0]["reason"] == "Дата окончания раньше даты начала"


async def test_builtin_mode_never_calls_llm(client, container) -> None:
    site_id, fake = await _site(client, container)
    response = await _import(client, site_id, ARBITRARY, "builtin")
    assert response.status_code == 422
    assert fake.calls == []


async def test_unknown_mode_is_422(client, container) -> None:
    site_id, _ = await _site(client, container)
    assert (await _import(client, site_id, STANDARD, "magic")).status_code == 422


def test_read_grid_formats_cells() -> None:
    grid = ScheduleParser().read_grid("p.csv", ARBITRARY)
    assert grid[1] == (2, ["Фундамент", "01.01.2026", "10.01.2026"])


# ---------- HTTP-адаптер ----------


def _client(handler) -> HttpScheduleLlmClient:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return HttpScheduleLlmClient("http://ml:8000", http, AssistantSettings())


async def test_http_client_parses_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/parse-schedule"
        assert b'"cells"' in request.content
        return httpx.Response(
            200,
            json={
                "rows": [{"row": 2, "name": "Фундамент", "start": "2026-01-01", "end": None}],
                "issues": [{"row": 3, "raw": "x", "reason": "r"}],
            },
        )

    result = await _client(handler).parse([(2, ["Фундамент", "01.01.2026"])])
    assert result.rows == [LlmScheduleRow(2, "Фундамент", date(2026, 1, 1), None)]
    assert result.issues == [LlmScheduleIssue(3, "x", "r")]


@pytest.mark.parametrize(
    ("status", "error"),
    [(413, AssistantBadRequest), (504, AssistantTimeout), (503, AssistantUnavailable)],
)
async def test_http_client_maps_errors(status, error) -> None:
    client = _client(lambda _r: httpx.Response(status, json={"detail": "x"}))
    with pytest.raises(error):
        await client.parse([(1, ["a"])])


async def test_http_client_bad_body_is_unavailable() -> None:
    client = _client(lambda _r: httpx.Response(200, json={"nope": 1}))
    with pytest.raises(AssistantUnavailable):
        await client.parse([(1, ["a"])])


async def test_null_client_is_unavailable() -> None:
    with pytest.raises(AssistantUnavailable):
        await NullScheduleLlmClient().parse([(1, ["a"])])


# ---------- длинные названия (регрессия: varchar(500) ронял импорт 500-кой) ----------

LONG_NAME = "Работы подготовительного периода:\n" + "\n".join(
    f"- пункт {i} " * 5 for i in range(40)
)


async def test_builtin_long_multiline_name_is_saved_cleaned(client, container) -> None:
    site_id, _ = await _site(client, container)
    csv = f'Название;Начало;Окончание\n"{LONG_NAME}";01.01.2026;10.01.2026\n'.encode()
    response = await _import(client, site_id, csv, "builtin")
    assert response.status_code == 201
    name = response.json()["stages"][0]["name"]
    assert len(name) <= 500 and name.endswith("…")
    assert "\n" not in name and name.startswith("Работы подготовительного периода: - пункт 0")


async def test_llm_long_name_is_saved_cleaned(client, container) -> None:
    site_id, fake = await _site(client, container)
    fake.result = LlmScheduleResult(rows=[LlmScheduleRow(2, LONG_NAME, None, None)], issues=[])
    response = await _import(client, site_id, STANDARD, "llm")
    assert response.status_code == 201
    assert len(response.json()["stages"][0]["name"]) <= 500
