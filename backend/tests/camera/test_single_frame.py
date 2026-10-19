"""Один кадр в ленту камеры: одиночная загрузка с camera_id и «Снять кадр сейчас»."""

import io

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from PIL import Image

from app.domains.user.service import UserService
from tests.fakes import FakeGrabber

STREAM = "rtsp://admin:secret@10.0.0.5/live"
ZONE = [[0.1, 0.2], [0.9, 0.2], [0.9, 0.95], [0.1, 0.95]]


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (200, 200), color="red").save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
async def stand_client(client: AsyncClient, container: AsyncContainer) -> AsyncClient:
    async with container() as request_container:
        await (await request_container.get(UserService)).ensure_stand_user()
    return client


async def _site(client: AsyncClient, name: str = "Объект") -> str:
    return (await client.post("/sites", json={"name": name})).json()["id"]


async def _camera(client: AsyncClient, site: str, **body) -> str:
    r = await client.post(f"/sites/{site}/cameras", json={"name": "К-1", **body})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _upload_one(client: AsyncClient, site: str, filename: str, camera: str | None = None):
    data = {"camera_id": camera} if camera is not None else {}
    return await client.post(
        f"/sites/{site}/photos",
        files=[("files", (filename, _jpeg(), "image/jpeg"))],
        data=data,
    )


# --- Сценарий 1: одиночная загрузка файла в ленту камеры ---------------------


async def test_single_file_with_camera_id_creates_linked_photo(
    stand_client: AsyncClient,
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, zone=ZONE)

    r = await _upload_one(stand_client, site, "IMG_20260918_100000.jpg", camera)

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["uploaded"] == 1 and body["failed"] == 0, body
    photo = body["items"][0]["photo"]
    assert photo is not None and body["items"][0]["error"] is None
    assert photo["camera_id"] == camera

    listed = (await stand_client.get(f"/sites/{site}/photos")).json()
    assert [p["id"] for p in listed] == [photo["id"]]
    assert listed[0]["camera_id"] == camera

    cameras = (await stand_client.get(f"/sites/{site}/cameras")).json()
    assert cameras[0]["frames_count"] == 1


async def test_single_file_without_date_is_created_undated(stand_client: AsyncClient) -> None:
    """Файл без EXIF, штампа и даты в имени: что видит пользователь при загрузке одного кадра."""
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, zone=ZONE)

    r = await _upload_one(stand_client, site, "cam.jpg", camera)

    assert r.status_code == 201, r.text
    item = r.json()["items"][0]
    assert item["error"] is None
    assert item["photo"]["captured_on"] is None
    assert item["photo"]["date_source"] is None
    assert item["photo"]["camera_id"] == camera
    undated = (await stand_client.get(f"/sites/{site}/photos?undated=true")).json()
    assert [p["id"] for p in undated] == [item["photo"]["id"]]


async def test_single_file_without_camera_id_is_not_linked(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    await _camera(stand_client, site, zone=ZONE)

    r = await _upload_one(stand_client, site, "IMG_20260918_100000.jpg")

    assert r.status_code == 201, r.text
    assert r.json()["items"][0]["photo"]["camera_id"] is None


# --- Сценарий 2: «Снять кадр сейчас» ----------------------------------------


async def test_capture_now_creates_photo_and_sets_last_capture_at(
    stand_client: AsyncClient, grabber: FakeGrabber
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)

    r = await stand_client.post(f"/sites/{site}/cameras/{camera}/capture")

    assert r.status_code == 201, r.text
    frame = r.json()
    assert frame["camera_id"] == camera
    assert grabber.calls == [STREAM]

    listed = (await stand_client.get(f"/sites/{site}/photos")).json()
    assert [p["id"] for p in listed] == [frame["id"]]

    cam = (await stand_client.get(f"/sites/{site}/cameras")).json()[0]
    assert cam["last_capture_at"] is not None
    assert cam["last_capture_error"] is None
    assert cam["frames_count"] == 1
