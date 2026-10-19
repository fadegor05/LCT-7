"""Решение инженера по гипотезе (clean-mvp, §8.8): подтвердить, отклонить, снять."""

import uuid
from datetime import date

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.assessment.models import Deviation
from tests.test_photo_router import seed_stand_user

EQ = uuid.uuid4()


def _deviation(site: str, *, hypothesis: bool, type_: str = "extra_equipment") -> Deviation:
    return Deviation(
        site_id=uuid.UUID(site),
        stage_id=None,
        type=type_,
        is_hypothesis=hypothesis,
        severity="attention",
        confidence="medium",
        period_start=date(2026, 8, 14),
        period_end=date(2026, 8, 14),
        expected="Техника этапов графика",
        observed="Кран-манипулятор: нет в графике",
        limits_text="Гипотеза",
        rule_id=None,
        title="Кран-манипулятор: нет в графике",
        equipment_type_id=EQ if hypothesis else None,
    )


async def _seed(container: AsyncContainer, *rows: Deviation) -> list[str]:
    async with container() as request:
        session = await request.get(AsyncSession)
        session.add_all(rows)
        await session.commit()
        return [str(r.id) for r in rows]


@pytest.fixture
async def site(client: AsyncClient, container: AsyncContainer) -> str:
    await seed_stand_user(container)
    return (await client.post("/sites", json={"name": "Объект"})).json()["id"]


async def test_confirm_reject_and_clear(
    client: AsyncClient, container: AsyncContainer, site: str
) -> None:
    hyp, fact = await _seed(
        container,
        _deviation(site, hypothesis=True),
        _deviation(site, hypothesis=False, type_="stale_data"),
    )
    base = f"/sites/{site}/assessment"
    [item] = [d for d in (await client.get(f"{base}/deviations")).json() if d["id"] == hyp]
    assert item["key"] == f"extra_equipment:-:{EQ}"
    assert item["decision"] is None
    assert (await client.get(f"{base}/summary")).json()["awaiting_decision"] == 1

    r = await client.put(
        f"{base}/deviations/{hyp}/decision", json={"decision": "confirmed", "comment": " видно "}
    )
    assert r.status_code == 200, r.text
    assert r.json()["decision"]["decision"] == "confirmed"
    assert r.json()["decision"]["comment"] == "видно"
    assert r.json()["decision"]["decided_by_name"]
    assert (await client.get(f"{base}/summary")).json()["awaiting_decision"] == 0

    # Отклонённая гипотеза — в архиве: её нет в списке и в счёте, карточка открывается
    await client.put(f"{base}/deviations/{hyp}/decision", json={"decision": "rejected"})
    ids = [d["id"] for d in (await client.get(f"{base}/deviations")).json()]
    assert ids == [fact]
    assert (await client.get(f"{base}/summary")).json()["attention_count"] == 1
    detail = (await client.get(f"{base}/deviations/{hyp}")).json()
    assert detail["decision"]["decision"] == "rejected"

    # «Изменить решение» — гипотеза снова ждёт
    await client.put(f"{base}/deviations/{hyp}/decision", json={"decision": None})
    assert len((await client.get(f"{base}/deviations")).json()) == 2
    assert (await client.get(f"{base}/summary")).json()["awaiting_decision"] == 1


async def test_only_hypotheses_take_decisions(
    client: AsyncClient, container: AsyncContainer, site: str
) -> None:
    [fact] = await _seed(container, _deviation(site, hypothesis=False, type_="stale_data"))
    r = await client.put(
        f"/sites/{site}/assessment/deviations/{fact}/decision", json={"decision": "confirmed"}
    )
    assert r.status_code == 422


async def test_decision_survives_recompute(
    client: AsyncClient, container: AsyncContainer, site: str
) -> None:
    """Пересчёт пересоздаёт строки отклонений — решение держится за ключ, а не за id."""
    [old] = await _seed(container, _deviation(site, hypothesis=True))
    await client.put(
        f"/sites/{site}/assessment/deviations/{old}/decision", json={"decision": "confirmed"}
    )
    async with container() as request:
        session = await request.get(AsyncSession)
        await session.delete(await session.get(Deviation, uuid.UUID(old)))
        await session.commit()
    [new] = await _seed(container, _deviation(site, hypothesis=True))
    [item] = (await client.get(f"/sites/{site}/assessment/deviations")).json()
    assert item["id"] == new and item["decision"]["decision"] == "confirmed"


async def test_decision_on_foreign_site_is_404(
    client: AsyncClient, container: AsyncContainer, site: str
) -> None:
    r = await client.put(
        f"/sites/{uuid.uuid4()}/assessment/deviations/{uuid.uuid4()}/decision",
        json={"decision": "confirmed"},
    )
    assert r.status_code == 404
