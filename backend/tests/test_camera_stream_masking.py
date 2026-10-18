"""Пароль камеры не уходит в ответы API; правка с замаскированной ссылкой не портит сохранённую.

Сниматель — FakeGrabber из conftest (`grabber`): снимок идёт по настоящей ссылке из базы.
"""

import uuid

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domains.camera.models import Camera
from app.domains.user.service import UserService
from tests.fakes import FakeGrabber

STREAM = "rtsp://admin:secret@10.0.0.5/live"
MASKED = "rtsp://***@10.0.0.5/live"


@pytest.fixture
async def stand_client(client: AsyncClient, container: AsyncContainer) -> AsyncClient:
    async with container() as request_container:
        await (await request_container.get(UserService)).ensure_stand_user()
    return client


@pytest.fixture
async def maker(container: AsyncContainer) -> async_sessionmaker[AsyncSession]:
    return await container.get(async_sessionmaker[AsyncSession])


async def _site(client: AsyncClient) -> str:
    return (await client.post("/sites", json={"name": "Объект"})).json()["id"]


async def _camera(client: AsyncClient, site: str, **body) -> dict:
    r = await client.post(f"/sites/{site}/cameras", json={"name": "К-1", **body})
    assert r.status_code == 201, r.text
    return r.json()


async def _stored_url(maker: async_sessionmaker[AsyncSession], camera_id: str) -> str | None:
    async with maker() as session:
        camera = await session.get(Camera, uuid.UUID(camera_id))
        assert camera is not None
        return camera.stream_url


async def test_create_list_and_patch_never_return_the_password(
    stand_client: AsyncClient,
) -> None:
    site = await _site(stand_client)
    created = await _camera(stand_client, site, stream_url=STREAM)
    url = f"/sites/{site}/cameras/{created['id']}"

    patched = await stand_client.patch(url, json={"name": "К-1 север"})
    listed = await stand_client.get(f"/sites/{site}/cameras")

    assert created["stream_url"] == MASKED
    assert patched.json()["stream_url"] == MASKED
    assert listed.json()[0]["stream_url"] == MASKED
    for response in (created, patched.json(), listed.text):
        assert "secret" not in str(response)


async def test_patch_with_the_masked_link_keeps_the_stored_url(
    stand_client: AsyncClient, maker: async_sessionmaker[AsyncSession]
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)
    url = f"/sites/{site}/cameras/{camera['id']}"

    # Так присылает диалог камеры, когда ссылку не трогали
    r = await stand_client.patch(url, json={"stream_url": MASKED, "name": "К-1 юг"})

    assert r.status_code == 200, r.text
    assert await _stored_url(maker, camera["id"]) == STREAM
    assert r.json()["stream_url"] == MASKED


async def test_patch_without_stream_url_keeps_the_stored_url(
    stand_client: AsyncClient, maker: async_sessionmaker[AsyncSession]
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)

    await stand_client.patch(f"/sites/{site}/cameras/{camera['id']}", json={"name": "К-1 юг"})

    assert await _stored_url(maker, camera["id"]) == STREAM


async def test_masked_link_with_a_new_host_keeps_the_stored_password(
    stand_client: AsyncClient, maker: async_sessionmaker[AsyncSession]
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)

    r = await stand_client.patch(
        f"/sites/{site}/cameras/{camera['id']}",
        json={"stream_url": "rtsp://***@10.0.0.6/live"},
    )

    assert r.status_code == 200, r.text
    assert await _stored_url(maker, camera["id"]) == "rtsp://admin:secret@10.0.0.6/live"
    assert r.json()["stream_url"] == "rtsp://***@10.0.0.6/live"


async def test_patch_with_a_full_link_replaces_the_stored_url(
    stand_client: AsyncClient, maker: async_sessionmaker[AsyncSession]
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)

    r = await stand_client.patch(
        f"/sites/{site}/cameras/{camera['id']}",
        json={"stream_url": "rtsp://user:new%40pass@10.0.0.7/live"},
    )

    assert r.status_code == 200, r.text
    assert await _stored_url(maker, camera["id"]) == "rtsp://user:new%40pass@10.0.0.7/live"
    assert "new%40pass" not in r.text


async def test_masked_link_on_create_is_422(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)

    r = await stand_client.post(
        f"/sites/{site}/cameras", json={"name": "К-1", "stream_url": MASKED}
    )

    assert r.status_code == 422


async def test_masked_link_without_stored_password_is_422(
    stand_client: AsyncClient, maker: async_sessionmaker[AsyncSession]
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url="rtsp://10.0.0.5/live")

    r = await stand_client.patch(
        f"/sites/{site}/cameras/{camera['id']}", json={"stream_url": MASKED}
    )

    assert r.status_code == 422
    assert await _stored_url(maker, camera["id"]) == "rtsp://10.0.0.5/live"


async def test_capture_now_after_a_masked_round_trip_uses_the_real_url(
    stand_client: AsyncClient, grabber: FakeGrabber
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)
    await stand_client.patch(f"/sites/{site}/cameras/{camera['id']}", json={"stream_url": MASKED})

    r = await stand_client.post(f"/sites/{site}/cameras/{camera['id']}/capture")

    assert r.status_code == 201, r.text
    assert grabber.calls == [STREAM]
