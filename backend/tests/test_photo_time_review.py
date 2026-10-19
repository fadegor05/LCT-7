"""«Без даты или времени» (clean-mvp): подтверждение даты и времени кадра, пакетный ввод,
выброс серии камеры ждёт подтверждения и в расчёт не идёт."""

import uuid
from datetime import datetime

from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.observation.models import Observation
from app.domains.photo.models import Photo
from tests.test_photo_router import create_jpeg_image, seed_stand_user


async def _site_with(
    client: AsyncClient, container: AsyncContainer, *names: str
) -> tuple[str, list[str]]:
    await seed_stand_user(container)
    site = (await client.post("/sites", json={"name": "Объект"})).json()["id"]
    files = [("files", (n, create_jpeg_image(), "image/jpeg")) for n in names]
    report = (await client.post(f"/sites/{site}/photos", files=files)).json()
    return site, [i["photo"]["id"] for i in report["items"]]


async def _photo(container: AsyncContainer, photo_id: str) -> Photo:
    async with container() as request:
        session = await request.get(AsyncSession)
        return (
            await session.execute(select(Photo).where(Photo.id == uuid.UUID(photo_id)))
        ).scalar_one()


async def test_confirm_date_and_time(client: AsyncClient, container: AsyncContainer) -> None:
    site, [pid] = await _site_with(client, container, "no-date.jpg")
    assert [
        p["id"]
        for p in (await client.get(f"/sites/{site}/photos", params={"undated": True})).json()
    ] == [pid]

    r = await client.patch(
        f"/sites/{site}/photos/{pid}/date", json={"captured_at": "2026-08-05T10:30:00"}
    )
    assert r.status_code == 200, r.text
    assert (r.json()["captured_on"], r.json()["captured_at"]) == (
        "2026-08-05",
        "2026-08-05T10:30:00",
    )
    assert r.json()["date_source"] == "manual"
    assert (await client.get(f"/sites/{site}/photos", params={"undated": True})).json() == []


async def test_future_time_rejected(client: AsyncClient, container: AsyncContainer) -> None:
    site, [pid] = await _site_with(client, container, "no-date.jpg")
    future = datetime(datetime.now().year + 1, 1, 1, 10, 0).isoformat()
    r = await client.patch(f"/sites/{site}/photos/{pid}/date", json={"captured_at": future})
    assert r.status_code == 422
    assert r.json()["detail"] == "Время съёмки не может быть в будущем"
    r = await client.patch(f"/sites/{site}/photos/{pid}/date", json={})
    assert r.status_code == 422


async def test_batch_first_plus_step(client: AsyncClient, container: AsyncContainer) -> None:
    site, ids = await _site_with(client, container, "a.jpg", "b.jpg", "c.jpg")
    r = await client.post(
        f"/sites/{site}/photos/time-batch",
        json={"photo_ids": ids, "first": "2026-08-05T10:30:00", "step_minutes": 1.5},
    )
    assert r.status_code == 200, r.text
    assert [p["captured_at"] for p in r.json()] == [
        "2026-08-05T10:30:00",
        "2026-08-05T10:31:30",
        "2026-08-05T10:33:00",
    ]
    async with container() as request:
        session = await request.get(AsyncSession)
        obs = (await session.execute(select(Observation))).scalars().all()
    assert [(str(o.observed_on), o.photo_count) for o in obs] == [("2026-08-05", 3)]


async def test_series_outlier_waits_for_confirmation(
    client: AsyncClient, container: AsyncContainer
) -> None:
    """Время выбилось из серии камеры: кадр в «Без даты или времени» и не в наблюдении."""
    site, [ok, odd] = await _site_with(
        client, container, "IMG_20260805_101500.jpg", "IMG_20260805_102000.jpg"
    )
    async with container() as request:
        session = await request.get(AsyncSession)
        photo = await session.get(Photo, uuid.UUID(odd))
        assert photo is not None
        photo.time_check = "series_outlier"
        await session.commit()
    # Пересчёт даты: выброс в наблюдение не входит
    r = await client.patch(
        f"/sites/{site}/photos/{ok}/date", json={"captured_at": "2026-08-05T10:15:00"}
    )
    assert r.status_code == 200
    undated = (await client.get(f"/sites/{site}/photos", params={"undated": True})).json()
    assert [p["id"] for p in undated] == [odd]
    async with container() as request:
        session = await request.get(AsyncSession)
        [obs] = (await session.execute(select(Observation))).scalars().all()
    assert obs.photo_count == 1

    # Подтвердили время — кадр в расчёте, проверка серии снята
    await client.patch(
        f"/sites/{site}/photos/{odd}/date", json={"captured_at": "2026-08-05T10:20:00"}
    )
    assert (await _photo(container, odd)).time_check is None
    async with container() as request:
        session = await request.get(AsyncSession)
        [obs] = (await session.execute(select(Observation))).scalars().all()
    assert obs.photo_count == 2
