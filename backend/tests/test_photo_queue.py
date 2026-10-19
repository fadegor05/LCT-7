"""Фоновая обработка загрузки: запрос принимает файлы, очередь ставит дату и технику.

Lifespan в тестах не запускается: очередь прогоняется вручную (`run_once`, `recover`).
"""

import uuid

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.ml.base import DetectionResult, DetectorError, RawDetection
from app.core.settings import Settings
from app.domains.observation.models import Observation
from app.domains.photo.models import Photo
from app.domains.photo.queue import PhotoQueue
from tests.fakes import FakeDetector
from tests.test_photo_router import _seed_equipment, create_jpeg_image, seed_stand_user


@pytest.fixture
async def background(container: AsyncContainer, monkeypatch: pytest.MonkeyPatch) -> PhotoQueue:
    settings = await container.get(Settings)
    monkeypatch.setattr(settings.upload, "background", True)
    return await container.get(PhotoQueue)


@pytest.fixture
async def maker(container: AsyncContainer) -> async_sessionmaker[AsyncSession]:
    return await container.get(async_sessionmaker[AsyncSession])


async def _site(client: AsyncClient, container: AsyncContainer) -> str:
    await seed_stand_user(container)
    return (await client.post("/sites", json={"name": "Объект"})).json()["id"]


async def _upload(client: AsyncClient, site: str, *names: str) -> dict:
    files = [("files", (name, create_jpeg_image(), "image/jpeg")) for name in names]
    response = await client.post(f"/sites/{site}/photos", files=files)
    assert response.status_code == 201, response.text
    return response.json()


async def _photos(maker) -> list[Photo]:
    async with maker() as session:
        return list((await session.execute(select(Photo))).scalars().all())


async def test_upload_only_accepts_and_queue_dates_and_detects(
    client: AsyncClient,
    container: AsyncContainer,
    detector: FakeDetector,
    background: PhotoQueue,
    maker,
) -> None:
    site = await _site(client, container)
    await _seed_equipment(container)
    detector.result = DetectionResult(
        model_version="v1",
        detections=[RawDetection(bbox=(0.1, 0.1, 0.5, 0.5), class_ours="COMP_1", conf=0.9)],
    )

    report = await _upload(client, site, "IMG_20260918_101500.jpg", "IMG_20260918_102000.jpg")

    # Запрос не ждал ни штампа, ни детектора
    assert report["uploaded"] == 2
    assert {i["photo"]["processing_status"] for i in report["items"]} == {"queued"}
    assert detector.calls == []
    assert (await client.get(f"/sites/{site}/photos/progress")).json() == {
        "queued": 2,
        "processing": 0,
    }
    # Кадр в очереди — не «без даты»: его рано разбирать вручную
    assert (await client.get(f"/sites/{site}/photos", params={"undated": True})).json() == []

    assert await background.run_once() == 2

    photos = await _photos(maker)
    assert {(p.processing_status, p.date_source, str(p.captured_on)) for p in photos} == {
        ("done", "filename", "2026-09-18")
    }
    assert sorted(p.captured_at.strftime("%H:%M") for p in photos if p.captured_at) == [
        "10:15",
        "10:20",
    ]
    assert all(p.upload_batch_id is None for p in photos), "пачка закрыта"
    assert len(detector.calls) == 2
    async with maker() as session:
        obs = (await session.execute(select(Observation))).scalars().all()
    assert [(str(o.observed_on), o.photo_count) for o in obs] == [("2026-09-18", 2)]
    assert (await client.get(f"/sites/{site}/photos/progress")).json() == {
        "queued": 0,
        "processing": 0,
    }


async def test_neighbours_dating_keeps_batch_order(
    client: AsyncClient, container: AsyncContainer, background: PhotoQueue, maker
) -> None:
    """Снимок без даты получает дату ближайшего соседа по пачке, как в загрузке без очереди."""
    site = await _site(client, container)
    await _upload(client, site, "IMG_20260918_101500.jpg", "no-date.jpg", "IMG_20260920_101500.jpg")
    await background.run_once()
    by_name = {p.original_name: p for p in await _photos(maker)}
    assert by_name["no-date.jpg"].date_source == "neighbours"
    # Ничья по расстоянию — выигрывает более ранний сосед
    assert str(by_name["no-date.jpg"].captured_on) == "2026-09-18"


async def test_detector_error_marks_failed_not_stuck(
    client: AsyncClient,
    container: AsyncContainer,
    detector: FakeDetector,
    background: PhotoQueue,
    maker,
) -> None:
    site = await _site(client, container)
    detector.error = DetectorError("ML недоступен", transient=True)
    await _upload(client, site, "IMG_20260918_101500.jpg")
    await background.run_once()
    [photo] = await _photos(maker)
    assert photo.processing_status == "failed"
    assert str(photo.captured_on) == "2026-09-18", "дата поставлена и без детектора"


async def test_recover_requeues_interrupted_frames(
    client: AsyncClient, container: AsyncContainer, background: PhotoQueue, maker
) -> None:
    """Перезапуск посреди обработки: кадр в processing возвращается в очередь и доходит."""
    site = await _site(client, container)
    await _upload(client, site, "IMG_20260918_101500.jpg")
    async with maker() as session:
        photo = (await session.execute(select(Photo))).scalar_one()
        photo.processing_status = "processing"
        await session.commit()

    await background.recover()
    assert (await client.get(f"/sites/{site}/photos/progress")).json()["queued"] == 1
    await background.run_once()
    [photo] = await _photos(maker)
    assert photo.processing_status == "done"


async def test_manual_date_set_while_queued_is_kept(
    client: AsyncClient, container: AsyncContainer, background: PhotoQueue, maker
) -> None:
    site = await _site(client, container)
    report = await _upload(client, site, "IMG_20260918_101500.jpg")
    photo_id = report["items"][0]["photo"]["id"]
    r = await client.patch(
        f"/sites/{site}/photos/{photo_id}/date", json={"captured_on": "2026-09-20"}
    )
    assert r.status_code == 200, r.text
    await background.run_once()
    [photo] = await _photos(maker)
    assert (photo.date_source, str(photo.captured_on)) == ("manual", "2026-09-20")
    assert photo.processing_status == "done"


async def test_progress_requires_site_access(client: AsyncClient, container: AsyncContainer):
    await seed_stand_user(container)
    response = await client.get(f"/sites/{uuid.uuid4()}/photos/progress")
    assert response.status_code == 404
