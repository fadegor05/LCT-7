"""Объединение соседних этапов графика: POST /sites/{site_id}/schedule/stages/merge."""

import uuid

from dishka import AsyncContainer
from httpx import AsyncClient

from tests.test_methodology_router import seed_equipment_types
from tests.test_schedule_router import make_csv_bytes, seed_stand_user


async def create_site_with_stages(
    client: AsyncClient, rows: list[tuple[str, str, str]]
) -> tuple[str, list[dict]]:
    """Создать сайт и импортировать график из строк (name, start, end)."""
    site_id = (await client.post("/sites", json={"name": "Merge"})).json()["id"]
    body = "name,start,end\n" + "".join(f"{n},{s},{e}\n" for n, s, e in rows)
    resp = await client.post(
        f"/sites/{site_id}/schedule/import",
        files={"file": ("schedule.csv", make_csv_bytes(body), "text/csv")},
    )
    assert resp.status_code == 201
    return site_id, resp.json()["stages"]


async def test_merge_adjacent_stages_spans_union_and_keeps_first_name(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Объединённый этап берёт название первого и окно из объединения дат."""
    await seed_stand_user(container)
    site_id, stages = await create_site_with_stages(
        client,
        [
            ("Фундамент", "2024-01-05", "2024-01-10"),
            ("Стены", "2024-01-01", "2024-01-20"),
            ("Кровля", "2024-01-21", "2024-01-31"),
        ],
    )

    resp = await client.post(
        f"/sites/{site_id}/schedule/stages/merge",
        json={"stage_ids": [stages[0]["id"], stages[1]["id"]]},
    )

    assert resp.status_code == 200
    merged = resp.json()["stages"]
    assert [s["name"] for s in merged] == ["Фундамент", "Кровля"]
    assert [s["position"] for s in merged] == [1, 2]
    assert merged[0]["id"] == stages[0]["id"]
    assert merged[0]["planned_start"] == "2024-01-01"
    assert merged[0]["planned_end"] == "2024-01-20"
    assert merged[0]["dates_source"] == "file"
    assert resp.json()["stages_with_dates"] == 2


async def test_merge_marks_window_manual_when_a_merged_stage_was_edited(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Если хотя бы один объединяемый этап правили вручную, результат тоже «вручную»."""
    await seed_stand_user(container)
    site_id, stages = await create_site_with_stages(
        client,
        [
            ("Фундамент", "2024-01-01", "2024-01-10"),
            ("Стены", "2024-01-11", "2024-01-20"),
        ],
    )
    await client.patch(
        f"/sites/{site_id}/schedule/stages/{stages[1]['id']}",
        json={"planned_start": "2024-01-11", "planned_end": "2024-01-25"},
    )

    resp = await client.post(
        f"/sites/{site_id}/schedule/stages/merge",
        json={"stage_ids": [stages[0]["id"], stages[1]["id"]]},
    )

    assert resp.status_code == 200
    merged = resp.json()["stages"][0]
    assert merged["planned_end"] == "2024-01-25"
    assert merged["dates_source"] == "manual"


async def test_merge_non_adjacent_stages_returns_422(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Объединять можно только соседние этапы."""
    await seed_stand_user(container)
    site_id, stages = await create_site_with_stages(
        client,
        [
            ("А", "2024-01-01", "2024-01-02"),
            ("Б", "2024-01-03", "2024-01-04"),
            ("В", "2024-01-05", "2024-01-06"),
        ],
    )

    resp = await client.post(
        f"/sites/{site_id}/schedule/stages/merge",
        json={"stage_ids": [stages[0]["id"], stages[2]["id"]]},
    )

    assert resp.status_code == 422
    assert resp.json()["detail"] == "Объединять можно только соседние этапы"
    assert len((await client.get(f"/sites/{site_id}/schedule")).json()["stages"]) == 3


async def test_merge_unknown_stage_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Неизвестный этап в запросе — 404, график не меняется."""
    await seed_stand_user(container)
    site_id, stages = await create_site_with_stages(
        client,
        [("А", "2024-01-01", "2024-01-02"), ("Б", "2024-01-03", "2024-01-04")],
    )

    resp = await client.post(
        f"/sites/{site_id}/schedule/stages/merge",
        json={"stage_ids": [stages[0]["id"], str(uuid.uuid4())]},
    )

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Этап не найден"


async def test_merge_needs_two_distinct_stages(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Один этап (или один и тот же дважды) объединять не с чем — 422."""
    await seed_stand_user(container)
    site_id, stages = await create_site_with_stages(
        client,
        [("А", "2024-01-01", "2024-01-02"), ("Б", "2024-01-03", "2024-01-04")],
    )
    url = f"/sites/{site_id}/schedule/stages/merge"

    single = await client.post(url, json={"stage_ids": [stages[0]["id"]]})
    same = await client.post(url, json={"stage_ids": [stages[0]["id"], stages[0]["id"]]})

    assert single.status_code == 422
    assert same.status_code == 422
    assert same.json()["detail"] == "Выберите хотя бы два разных этапа"


async def test_merge_on_unknown_site_returns_404(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Объединение на чужой/несуществующей стройке — 404 через SiteAccessGuard."""
    await seed_stand_user(container)
    resp = await client.post(
        f"/sites/{uuid.uuid4()}/schedule/stages/merge",
        json={"stage_ids": [str(uuid.uuid4()), str(uuid.uuid4())]},
    )
    assert resp.status_code == 404


async def test_merge_moves_kits_and_verifiability_into_target_rule(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Наборы техники второго этапа переезжают в объединённый, одинаковые не дублируются.

    Если проверяемым был только второй этап, объединённый становится проверяемым.
    """
    await seed_stand_user(container)
    await seed_equipment_types(container)
    site_id, stages = await create_site_with_stages(
        client,
        [
            ("Фундамент", "2024-01-01", "2024-01-10"),
            ("Стены", "2024-01-11", "2024-01-20"),
            ("Кровля", "2024-01-21", "2024-01-31"),
        ],
    )
    equipment = (await client.get("/equipment-types")).json()
    crane_id, excavator_id = equipment[0]["id"], equipment[1]["id"]
    methodology = (await client.get(f"/sites/{site_id}/methodology")).json()
    rule_by_name = {r["stage_name"]: r for r in methodology}
    first_rule, second_rule = rule_by_name["Фундамент"], rule_by_name["Стены"]

    shared = {
        "requirements": [
            {
                "equipment_type_id": crane_id,
                "min_count": 1,
                "obligation": "normative",
                "source_note": "общий набор",
            }
        ]
    }
    own = {
        "requirements": [
            {
                "equipment_type_id": excavator_id,
                "min_count": 1,
                "obligation": "normative",
                "source_note": "свой набор второго этапа",
            }
        ]
    }
    base = f"/sites/{site_id}/methodology"
    assert (
        await client.post(f"{base}/rules/{first_rule['id']}/sets", json=shared)
    ).status_code == 201
    assert (
        await client.post(f"{base}/rules/{second_rule['id']}/sets", json=shared)
    ).status_code == 201
    assert (
        await client.post(f"{base}/rules/{second_rule['id']}/sets", json=own)
    ).status_code == 201
    verify = await client.patch(
        f"{base}/rules/{second_rule['id']}",
        json={"is_verifiable": True, "unverifiable_reason": None},
    )
    assert verify.status_code == 200

    resp = await client.post(
        f"/sites/{site_id}/schedule/stages/merge",
        json={"stage_ids": [stages[0]["id"], stages[1]["id"]]},
    )
    assert resp.status_code == 200

    after = {r["stage_name"]: r for r in (await client.get(base)).json()}
    assert set(after) == {"Фундамент", "Кровля"}
    merged = after["Фундамент"]
    assert merged["is_verifiable"] is True
    assert merged["unverifiable_reason"] is None
    # Общий набор не дублируется: остаются собственный набор первого и «свой» второго
    assert len(merged["sets"]) == 2
    kit_sources = sorted(s["requirements"][0]["source_note"] for s in merged["sets"])
    assert kit_sources == ["общий набор", "свой набор второго этапа"]
