"""Тип объекта и рабочие дни объекта (clean-mvp): поля объекта и вход движка."""

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient

from app.domains.assessment.engine import RuleEngine
from tests.test_photo_router import seed_stand_user


async def test_site_defaults_to_weekdays(client: AsyncClient, container: AsyncContainer) -> None:
    await seed_stand_user(container)
    site = (await client.post("/sites", json={"name": "Школа"})).json()
    assert (site["object_type"], site["workdays"]) == ("other", [0, 1, 2, 3, 4])


async def test_site_keeps_type_and_workdays(client: AsyncClient, container: AsyncContainer) -> None:
    await seed_stand_user(container)
    r = await client.post(
        "/sites", json={"name": "Школа", "object_type": "education", "workdays": [5, 0, 1, 2, 3, 4]}
    )
    assert r.status_code == 201
    assert (r.json()["object_type"], r.json()["workdays"]) == ("education", [0, 1, 2, 3, 4, 5])


@pytest.mark.parametrize("days", [[], [7], [0, 0], [-1]])
async def test_bad_workdays_rejected(client: AsyncClient, container: AsyncContainer, days) -> None:
    await seed_stand_user(container)
    r = await client.post("/sites", json={"name": "Школа", "workdays": days})
    assert r.status_code == 422


async def test_workdays_change_recomputes_with_site_days(
    client: AsyncClient, container: AsyncContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Правка рабочих дней сразу пересчитывает объект — по его дням, а не по умолчанию."""
    await seed_stand_user(container)
    site = (await client.post("/sites", json={"name": "Школа"})).json()["id"]
    csv = "name,start,end\nФундамент,2026-09-01,2026-09-10\n".encode()
    r = await client.post(
        f"/sites/{site}/schedule/import", files={"file": ("s.csv", csv, "text/csv")}
    )
    assert r.status_code == 201, r.text

    seen: list[tuple[int, ...]] = []
    original = RuleEngine.compute_site

    def spy(self, *args, **kwargs):
        seen.append(self.config.workdays)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(RuleEngine, "compute_site", spy)
    r = await client.patch(f"/sites/{site}", json={"workdays": [0, 1, 2, 3, 4, 5, 6]})
    assert r.status_code == 200
    assert seen == [(0, 1, 2, 3, 4, 5, 6)]

    # Тот же набор — не пересчитываем
    await client.patch(f"/sites/{site}", json={"workdays": [0, 1, 2, 3, 4, 5, 6]})
    assert len(seen) == 1
    # null для рабочих дней запрещён
    assert (await client.patch(f"/sites/{site}", json={"workdays": None})).status_code == 422
