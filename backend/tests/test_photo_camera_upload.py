"""Загрузка фотографии с необязательным camera_id: привязка к камере того же объекта."""

import io
import uuid

import pytest
from dishka import AsyncContainer
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.methodology.models import EquipmentType
from app.domains.photo.models import Detection, Photo, ProcessingStatus
from app.domains.user.service import UserService
from app.main import create_app

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


async def _site(client: AsyncClient, name: str) -> str:
    return (await client.post("/sites", json={"name": name})).json()["id"]


async def _camera(client: AsyncClient, site: str, **body) -> str:
    r = await client.post(f"/sites/{site}/cameras", json={"name": "К-1", **body})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _upload(client: AsyncClient, site: str, **form: str):
    return await client.post(
        f"/sites/{site}/photos",
        files=[("files", ("cam.jpg", _jpeg(), "image/jpeg"))],
        data=form,
    )


async def test_upload_without_camera_id_leaves_photo_unlinked(stand_client: AsyncClient) -> None:
    site = await _site(stand_client, "Объект")

    r = await _upload(stand_client, site)

    assert r.status_code == 201, r.text
    photo = r.json()["items"][0]["photo"]
    assert photo["camera_id"] is None


async def test_upload_with_own_camera_id_is_persisted(stand_client: AsyncClient) -> None:
    site = await _site(stand_client, "Объект")
    camera = await _camera(stand_client, site, zone=ZONE)

    r = await _upload(stand_client, site, camera_id=camera)

    assert r.status_code == 201, r.text
    photo_id = r.json()["items"][0]["photo"]["id"]
    assert r.json()["items"][0]["photo"]["camera_id"] == camera
    detail = (await stand_client.get(f"/sites/{site}/photos/{photo_id}")).json()
    assert detail["camera_id"] == camera


async def test_upload_with_camera_of_another_site_is_404(stand_client: AsyncClient) -> None:
    site = await _site(stand_client, "Первый")
    other = await _site(stand_client, "Второй")
    foreign_camera = await _camera(stand_client, other, zone=ZONE)

    r = await _upload(stand_client, site, camera_id=foreign_camera)

    assert r.status_code == 404, r.text
    assert (await stand_client.get(f"/sites/{site}/photos")).json() == []


async def test_upload_with_unknown_camera_is_404(stand_client: AsyncClient) -> None:
    site = await _site(stand_client, "Объект")

    r = await _upload(stand_client, site, camera_id=str(uuid.uuid4()))

    assert r.status_code == 404, r.text
    assert (await stand_client.get(f"/sites/{site}/photos")).json() == []


async def test_upload_with_malformed_camera_id_is_422(stand_client: AsyncClient) -> None:
    site = await _site(stand_client, "Объект")

    r = await _upload(stand_client, site, camera_id="не-uuid")

    assert r.status_code == 422, r.text


async def test_camera_delete_keeps_photo_and_clears_link(fk_container: AsyncContainer) -> None:
    """ON DELETE SET NULL проверяется только с включёнными FK (SQLite по умолчанию их не знает)."""
    app = create_app(fk_container)
    async with fk_container() as request_container:
        await (await request_container.get(UserService)).ensure_stand_user()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test/api") as client:
        site = await _site(client, "Объект")
        camera = await _camera(client, site, zone=ZONE)
        photo_id = (await _upload(client, site, camera_id=camera)).json()["items"][0]["photo"]["id"]

        assert (await client.delete(f"/sites/{site}/cameras/{camera}")).status_code == 204
        detail = (await client.get(f"/sites/{site}/photos/{photo_id}")).json()
        assert detail["camera_id"] is None


async def test_photo_detail_marks_detection_inside_camera_zone(
    stand_client: AsyncClient, container: AsyncContainer
) -> None:
    """in_zone в детекции: центр нижней кромки рамки против зоны камеры снимка."""
    site = await _site(stand_client, "Объект")
    camera = await _camera(stand_client, site, zone=ZONE)
    photo_id = uuid.uuid4()
    equipment_id = uuid.uuid4()
    async with container() as request_container:
        session = await request_container.get(AsyncSession)
        session.add(EquipmentType(id=equipment_id, code="crane", title="Кран"))
        await session.flush()
        session.add(
            Photo(
                id=photo_id,
                site_id=uuid.UUID(site),
                storage_key=f"sites/{site}/photos/{photo_id}.jpg",
                original_name="a.jpg",
                width=200,
                height=200,
                processing_status=ProcessingStatus.DONE.value,
                camera_id=uuid.UUID(camera),
            )
        )
        await session.flush()
        for bbox in ([0.4, 0.5, 0.6, 0.8], [0.0, 0.5, 0.05, 0.6]):
            session.add(
                Detection(
                    id=uuid.uuid4(),
                    photo_id=photo_id,
                    equipment_type_id=equipment_id,
                    bbox=bbox,
                    score=0.9,
                    model_version="test",
                )
            )
        await session.commit()

    detail = (await stand_client.get(f"/sites/{site}/photos/{photo_id}")).json()

    assert detail["camera_id"] == camera
    assert sorted(d["in_zone"] for d in detail["detections"]) == [False, True]
