"""HTTP-контракт камер стройки и их рабочей зоны."""

import uuid
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from dishka import AsyncContainer
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.cli import create_user
from app.domains.photo.models import Photo
from app.domains.user.provider import UserProvider
from app.domains.user.service import UserService
from app.main import create_app
from tests.conftest import _make_container

ZONE = [[0.1, 0.2], [0.9, 0.2], [0.9, 0.95], [0.1, 0.95]]
PASSWORD = "correct horse battery"


async def seed_stand_user(container: AsyncContainer) -> None:
    async with container() as request_container:
        service = await request_container.get(UserService)
        await service.ensure_stand_user()


async def _site(client: AsyncClient) -> str:
    return (await client.post("/sites", json={"name": "Объект"})).json()["id"]


async def _camera(client: AsyncClient, site: str, **body) -> dict:
    r = await client.post(f"/sites/{site}/cameras", json={"name": "К-1", **body})
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
async def stand_client(client: AsyncClient, container: AsyncContainer) -> AsyncClient:
    await seed_stand_user(container)
    return client


async def test_create_and_list_cameras(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    first = await _camera(stand_client, site, stream_url=" rtsp://10.0.0.5/stream ", zone=ZONE)
    await _camera(stand_client, site, name="К-2")

    assert first["stream_url"] == "rtsp://10.0.0.5/stream"
    assert first["zone"] == ZONE
    assert first["frames_count"] == 0
    assert first["last_capture_at"] is None and first["last_capture_error"] is None

    cameras = (await stand_client.get(f"/sites/{site}/cameras")).json()
    # created_at — секундная точность на SQLite, порядок одинаковых меток не важен
    assert sorted(c["name"] for c in cameras) == ["К-1", "К-2"]
    by_name = {c["name"]: c for c in cameras}
    assert by_name["К-2"]["stream_url"] is None and by_name["К-2"]["zone"] is None


async def test_blank_stream_url_means_none(stand_client: AsyncClient) -> None:
    camera = await _camera(stand_client, await _site(stand_client), stream_url="   ")

    assert camera["stream_url"] is None


@pytest.mark.parametrize(
    "zone",
    [
        [[0.1, 0.1], [0.5, 0.5]],  # меньше трёх вершин
        [[0.1, 0.1], [1.2, 0.1], [0.5, 0.9]],  # за пределами кадра
        [[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]],  # на одной линии
        [[0.1, 0.1, 0.3], [0.5, 0.1], [0.5, 0.9]],  # не пара координат
        [[i / 200, (i % 2) / 2] for i in range(101)],  # слишком много вершин
    ],
)
async def test_invalid_zone_is_422(stand_client: AsyncClient, zone: list) -> None:
    site = await _site(stand_client)

    r = await stand_client.post(f"/sites/{site}/cameras", json={"name": "К-1", "zone": zone})

    assert r.status_code == 422


async def test_blank_name_is_422(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)

    r = await stand_client.post(f"/sites/{site}/cameras", json={"name": "  "})

    assert r.status_code == 422


async def test_patch_changes_only_sent_fields(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, zone=ZONE)
    url = f"/sites/{site}/cameras/{camera['id']}"

    r = await stand_client.patch(url, json={"name": "К-1 север"})

    assert r.status_code == 200
    assert r.json()["name"] == "К-1 север" and r.json()["zone"] == ZONE


async def test_patch_zone_and_remove_zone_and_stream(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url="rtsp://10.0.0.5/live")
    url = f"/sites/{site}/cameras/{camera['id']}"

    r = await stand_client.patch(url, json={"zone": ZONE})
    assert r.json()["zone"] == ZONE

    r = await stand_client.patch(url, json={"zone": None, "stream_url": None})
    assert r.json()["zone"] is None and r.json()["stream_url"] is None


async def test_patch_rejects_invalid_zone(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)

    r = await stand_client.patch(
        f"/sites/{site}/cameras/{camera['id']}", json={"zone": [[0.1, 0.1], [0.5, 0.5]]}
    )

    assert r.status_code == 422


async def test_patch_rejects_null_name(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)

    r = await stand_client.patch(f"/sites/{site}/cameras/{camera['id']}", json={"name": None})

    assert r.status_code == 422


async def test_camera_of_another_site_is_404(stand_client: AsyncClient) -> None:
    camera = await _camera(stand_client, await _site(stand_client))
    other = await _site(stand_client)
    url = f"/sites/{other}/cameras/{camera['id']}"

    assert (await stand_client.patch(url, json={"name": "x"})).status_code == 404
    assert (await stand_client.delete(url)).status_code == 404
    assert (await stand_client.get(f"/sites/{other}/cameras")).json() == []


async def test_unknown_site_is_404(stand_client: AsyncClient) -> None:
    r = await stand_client.post(f"/sites/{uuid.uuid4()}/cameras", json={"name": "К-1"})

    assert r.status_code == 404


async def test_delete_camera(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)

    r = await stand_client.delete(f"/sites/{site}/cameras/{camera['id']}")

    assert r.status_code == 204
    assert (await stand_client.get(f"/sites/{site}/cameras")).json() == []


async def test_stream_camera_captures_every_five_minutes_by_default(
    stand_client: AsyncClient,
) -> None:
    site = await _site(stand_client)

    camera = await _camera(stand_client, site, stream_url="rtsp://10.0.0.5/live")
    own = await _camera(
        stand_client, site, name="К-2", stream_url="rtsp://h/x", capture_every_s=600
    )
    plain = await _camera(stand_client, site, name="К-3", capture_every_s=600)

    assert camera["capture_every_s"] == 300
    assert own["capture_every_s"] == 600
    # Без ссылки снимать нечего
    assert plain["capture_every_s"] is None


async def test_removing_the_stream_stops_capture(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url="rtsp://10.0.0.5/live")
    url = f"/sites/{site}/cameras/{camera['id']}"

    r = await stand_client.patch(url, json={"stream_url": None})
    assert r.json()["capture_every_s"] is None

    r = await stand_client.patch(
        url, json={"stream_url": "rtsp://10.0.0.6/live", "capture_every_s": 120}
    )
    assert r.json()["capture_every_s"] == 120

    # Только интервал: ссылка остаётся
    r = await stand_client.patch(url, json={"capture_every_s": 900})
    assert (r.json()["stream_url"], r.json()["capture_every_s"]) == ("rtsp://10.0.0.6/live", 900)


@pytest.mark.parametrize(
    "body",
    [
        {"stream_url": "file:///etc/passwd"},  # не сетевой протокол
        {"stream_url": "ftp://cam/x"},
        {"stream_url": "rtsp://cam/x", "capture_every_s": 59},  # чаще минуты
        {"stream_url": "rtsp://cam/x", "capture_every_s": 86401},  # реже суток
    ],
)
async def test_stream_link_and_interval_are_checked(stand_client: AsyncClient, body: dict) -> None:
    site = await _site(stand_client)

    r = await stand_client.post(f"/sites/{site}/cameras", json={"name": "К-1", **body})

    assert r.status_code == 422


async def test_bad_stream_link_error_does_not_echo_credentials(
    stand_client: AsyncClient,
) -> None:
    site = await _site(stand_client)

    r = await stand_client.post(
        f"/sites/{site}/cameras",
        json={"name": "К-1", "stream_url": "ftp://admin:topsecret@10.0.0.5/live"},
    )

    assert r.status_code == 422
    assert "topsecret" not in r.text


async def test_photo_read_exposes_camera_id_and_camera_counts_its_photos(
    stand_client: AsyncClient, container: AsyncContainer
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)
    maker = await container.get(async_sessionmaker[AsyncSession])
    async with maker() as session:
        photo = Photo(
            site_id=uuid.UUID(site),
            storage_key="photos/a.jpg",
            original_name="a.jpg",
            width=10,
            height=10,
        )
        session.add(photo)
        await session.commit()
        photo_id = photo.id
        plain = (await stand_client.get(f"/sites/{site}/photos")).json()[0]
        assert plain["camera_id"] is None
        await session.execute(
            update(Photo).where(Photo.id == photo_id).values(camera_id=uuid.UUID(camera["id"]))
        )
        await session.commit()

    listed = (await stand_client.get(f"/sites/{site}/cameras")).json()

    assert listed[0]["frames_count"] == 1
    photos = (await stand_client.get(f"/sites/{site}/photos")).json()
    assert photos[0]["camera_id"] == camera["id"]


async def test_cameras_are_not_visible_without_token(
    tmp_path: Path,
) -> None:
    container = _make_container(tmp_path, user_provider=UserProvider())
    try:
        app = create_app(container)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test/api"
        ) as client:
            r = await client.get(f"/sites/{uuid.uuid4()}/cameras")
            assert r.status_code == 401
    finally:
        await container.close()


@pytest.fixture
async def real_auth_container(tmp_path: Path) -> AsyncIterator[AsyncContainer]:
    container = _make_container(tmp_path, user_provider=UserProvider())
    yield container
    await container.close()


async def _login(client: AsyncClient, login: str) -> dict[str, str]:
    r = await client.post("/auth/login", json={"login": login, "password": PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def test_user_cannot_touch_cameras_of_foreign_site(
    real_auth_container: AsyncContainer,
) -> None:
    maker = await real_auth_container.get(async_sessionmaker[AsyncSession])
    await create_user(maker, "anna", None, PASSWORD)
    await create_user(maker, "boris", None, PASSWORD)
    app = create_app(real_auth_container)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test/api") as client:
        anna = await _login(client, "anna")
        boris = await _login(client, "boris")
        site = (await client.post("/sites", json={"name": "Анны"}, headers=anna)).json()["id"]
        camera = await client.post(f"/sites/{site}/cameras", json={"name": "К-1"}, headers=anna)
        cam_url = f"/sites/{site}/cameras/{camera.json()['id']}"

        assert (await client.get(f"/sites/{site}/cameras", headers=boris)).status_code == 404
        assert (await client.patch(cam_url, json={"name": "х"}, headers=boris)).status_code == 404
        assert (await client.delete(cam_url, headers=boris)).status_code == 404
        own = await client.get(f"/sites/{site}/cameras", headers=anna)
        assert [c["name"] for c in own.json()] == ["К-1"]
