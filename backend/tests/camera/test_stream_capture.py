"""Фоновый планировщик снимков: StreamCapture.run_once(now) с реальной базой тестов.

Сниматель — FakeGrabber из conftest (`grabber`), запись кадра идёт обычным путём загрузки.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.camera.models import Camera
from app.domains.camera.stream import StreamCapture
from app.domains.photo.models import Photo
from app.domains.user.service import UserService
from tests.fakes import FakeGrabber

STREAM = "rtsp://admin:secret@10.0.0.5/live"
# Пятница 18.09.2026, 10:24 по Москве = 07:24 UTC: внутри окна 8-20
IN_WINDOW = datetime(2026, 9, 18, 7, 24, tzinfo=UTC)
# 02:00 UTC = 05:00 по Москве: вне окна 8-20
OUT_OF_WINDOW = datetime(2026, 9, 18, 2, 0, tzinfo=UTC)


@pytest.fixture
async def stand_client(client: AsyncClient, container: AsyncContainer) -> AsyncClient:
    async with container() as request_container:
        await (await request_container.get(UserService)).ensure_stand_user()
    return client


async def _site(client: AsyncClient) -> str:
    return (await client.post("/sites", json={"name": "Объект"})).json()["id"]


async def _stream_camera(client: AsyncClient, site: str) -> str:
    r = await client.post(
        f"/sites/{site}/cameras",
        json={"name": "К-1", "stream_url": STREAM, "capture_every_s": 300},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _stored(maker: async_sessionmaker[AsyncSession], camera_id: str) -> Camera:
    async with maker() as session:
        camera = await session.get(Camera, uuid.UUID(camera_id))
        assert camera is not None
        return camera


@pytest.fixture
async def maker(container: AsyncContainer) -> async_sessionmaker[AsyncSession]:
    return await container.get(async_sessionmaker[AsyncSession])


async def _photo_count(maker: async_sessionmaker[AsyncSession]) -> int:
    async with maker() as session:
        return (await session.execute(select(func.count()).select_from(Photo))).scalar_one()


async def test_due_camera_inside_window_is_captured_and_stamped(
    stand_client: AsyncClient,
    container: AsyncContainer,
    grabber: FakeGrabber,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    camera = await _stream_camera(stand_client, await _site(stand_client))
    capture = await container.get(StreamCapture)

    assert await capture.run_once(now=IN_WINDOW) == 1

    assert grabber.calls == [STREAM]
    assert await _photo_count(maker) == 1
    stored = await _stored(maker, camera)
    assert stored.last_capture_at is not None
    assert stored.last_capture_at.replace(tzinfo=UTC) == IN_WINDOW


async def test_no_capture_60_seconds_later(
    stand_client: AsyncClient, container: AsyncContainer, grabber: FakeGrabber
) -> None:
    await _stream_camera(stand_client, await _site(stand_client))
    capture = await container.get(StreamCapture)
    assert await capture.run_once(now=IN_WINDOW) == 1

    assert await capture.run_once(now=IN_WINDOW + timedelta(seconds=60)) == 0
    assert grabber.calls == [STREAM]


async def test_capture_again_after_301_seconds(
    stand_client: AsyncClient, container: AsyncContainer, grabber: FakeGrabber
) -> None:
    await _stream_camera(stand_client, await _site(stand_client))
    capture = await container.get(StreamCapture)
    assert await capture.run_once(now=IN_WINDOW) == 1

    assert await capture.run_once(now=IN_WINDOW + timedelta(seconds=301)) == 1
    assert grabber.calls == [STREAM, STREAM]


async def test_no_capture_outside_site_hours(
    stand_client: AsyncClient,
    container: AsyncContainer,
    grabber: FakeGrabber,
    maker: async_sessionmaker[AsyncSession],
) -> None:
    camera = await _stream_camera(stand_client, await _site(stand_client))
    capture = await container.get(StreamCapture)

    assert await capture.run_once(now=OUT_OF_WINDOW) == 0

    assert grabber.calls == []
    assert await _photo_count(maker) == 0
    stored = await _stored(maker, camera)
    assert stored.last_capture_at is None
    assert stored.last_capture_attempt_at is None
