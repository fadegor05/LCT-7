"""Поля попыток снимка в ответах камер: момент последней попытки и сбои подряд."""

from datetime import datetime

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient

from app.domains.user.service import UserService
from tests.fakes import FakeGrabber

STREAM = "rtsp://admin:secret@10.0.0.5/live"


@pytest.fixture
async def stand_client(client: AsyncClient, container: AsyncContainer) -> AsyncClient:
    async with container() as request_container:
        await (await request_container.get(UserService)).ensure_stand_user()
    return client


async def _site(client: AsyncClient) -> str:
    return (await client.post("/sites", json={"name": "Объект"})).json()["id"]


async def test_new_camera_has_no_attempts(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    await stand_client.post(f"/sites/{site}/cameras", json={"name": "К-1", "stream_url": STREAM})

    listed = (await stand_client.get(f"/sites/{site}/cameras")).json()[0]

    assert listed["last_capture_attempt_at"] is None
    assert listed["capture_failures"] == 0


async def test_failed_capture_now_moves_attempt_time_and_failures(
    stand_client: AsyncClient, grabber: FakeGrabber
) -> None:
    grabber.errors[STREAM] = "Камера не ответила за 15 с"
    site = await _site(stand_client)
    camera = (
        await stand_client.post(
            f"/sites/{site}/cameras", json={"name": "К-1", "stream_url": STREAM}
        )
    ).json()["id"]
    before = (await stand_client.get(f"/sites/{site}/cameras")).json()[0]

    r = await stand_client.post(f"/sites/{site}/cameras/{camera}/capture")
    assert r.status_code == 422

    after = (await stand_client.get(f"/sites/{site}/cameras")).json()[0]
    assert before["capture_failures"] == 0 and before["last_capture_attempt_at"] is None
    assert after["capture_failures"] == 1
    assert after["last_capture_attempt_at"] is not None
    # Момент попытки — настоящая дата-время, не пустая строка и не строка из ошибки
    datetime.fromisoformat(after["last_capture_attempt_at"])

    await stand_client.post(f"/sites/{site}/cameras/{camera}/capture")
    again = (await stand_client.get(f"/sites/{site}/cameras")).json()[0]
    assert again["capture_failures"] == 2
