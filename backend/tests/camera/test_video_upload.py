"""Видео с камеры: кадры по шагу идут в ленту камеры с временем из видео, не из файла.

Настоящий ffmpeg не нужен: извлечение кадров подменяет FakeFrameExtractor (см. conftest).
"""

import tempfile
from pathlib import Path

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from starlette.datastructures import UploadFile

from app.adapters.video.base import FrameExtractor, VideoError
from app.core.settings import Settings
from app.domains.camera.video import spool_upload
from app.domains.photo.queue import PhotoQueue
from app.domains.user.service import UserService
from app.plugins.exceptions import AppError
from tests.fakes import FakeFrameExtractor

ZONE = [[0.1, 0.2], [0.9, 0.2], [0.9, 0.95], [0.1, 0.95]]
VIDEO = b"not really a video, the extractor is faked"


@pytest.fixture
async def stand_client(client: AsyncClient, container: AsyncContainer) -> AsyncClient:
    async with container() as request_container:
        await (await request_container.get(UserService)).ensure_stand_user()
    return client


@pytest.fixture
async def extractor(container: AsyncContainer) -> FakeFrameExtractor:
    return await container.get(FrameExtractor)  # type: ignore[return-value]


@pytest.fixture
async def background(container: AsyncContainer, monkeypatch: pytest.MonkeyPatch) -> PhotoQueue:
    settings = await container.get(Settings)
    monkeypatch.setattr(settings.upload, "background", True)
    return await container.get(PhotoQueue)


async def _site(client: AsyncClient, name: str = "Объект") -> str:
    return (await client.post("/sites", json={"name": name})).json()["id"]


async def _camera(client: AsyncClient, site: str) -> str:
    r = await client.post(f"/sites/{site}/cameras", json={"name": "К-1", "zone": ZONE})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _post_video(
    client: AsyncClient,
    site: str,
    camera: str,
    *,
    recorded_at: str = "2026-10-20T09:30:00",
    step_s: int | None = 60,
    name: str = "IMG_0001.mp4",
    content: bytes = VIDEO,
):
    data = {"recorded_at": recorded_at}
    if step_s is not None:
        data["step_s"] = str(step_s)
    return await client.post(
        f"/sites/{site}/cameras/{camera}/video",
        files={"file": (name, content, "video/mp4")},
        data=data,
    )


async def test_video_frames_are_queued_with_video_times(
    stand_client: AsyncClient, background: PhotoQueue, extractor: FakeFrameExtractor
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)

    r = await _post_video(stand_client, site, camera, step_s=60)

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["uploaded"] == 3 and body["failed"] == 0, body
    assert body["step_s"] == 60
    assert body["duration_s"] == extractor.duration
    assert [i["filename"] for i in body["items"]] == [
        "video-IMG_0001-0000.jpg",
        "video-IMG_0001-0001.jpg",
        "video-IMG_0001-0002.jpg",
    ]
    photos = [i["photo"] for i in body["items"]]
    assert {p["processing_status"] for p in photos} == {"queued"}
    assert {p["camera_id"] for p in photos} == {camera}
    assert [p["captured_at"] for p in photos] == [
        "2026-10-20T09:30:00",
        "2026-10-20T09:31:00",
        "2026-10-20T09:32:00",
    ]
    assert {p["captured_on"] for p in photos} == {"2026-10-20"}
    assert {p["date_source"] for p in photos} == {"channel"}
    # Путь — временный файл на диске; шаг и лимит кадров из настроек
    assert [(step, limit) for _, step, limit in extractor.calls] == [(60, 200)]
    assert (await stand_client.get(f"/sites/{site}/photos/progress")).json() == {
        "queued": 3,
        "processing": 0,
    }


async def test_queue_keeps_video_times_and_channel_source(
    stand_client: AsyncClient, background: PhotoQueue
) -> None:
    """Имя видео с датой не должно перебить время из видео: очередь дату из файла не берёт."""
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)
    r = await _post_video(stand_client, site, camera, name="IMG_20250101_000000.mp4")
    assert r.status_code == 201, r.text

    assert await background.run_once() == 3

    listed = (await stand_client.get(f"/sites/{site}/photos")).json()
    assert len(listed) == 3
    assert {p["processing_status"] for p in listed} == {"done"}
    assert sorted(p["captured_at"] for p in listed) == [
        "2026-10-20T09:30:00",
        "2026-10-20T09:31:00",
        "2026-10-20T09:32:00",
    ]
    assert {p["captured_on"] for p in listed} == {"2026-10-20"}
    assert {p["date_source"] for p in listed} == {"channel"}


async def test_video_into_another_sites_camera_is_404(
    stand_client: AsyncClient, extractor: FakeFrameExtractor
) -> None:
    site = await _site(stand_client, "Первый")
    other = await _site(stand_client, "Второй")
    foreign_camera = await _camera(stand_client, other)

    r = await _post_video(stand_client, site, foreign_camera)

    assert r.status_code == 404, r.text
    assert extractor.calls == []
    assert (await stand_client.get(f"/sites/{site}/photos")).json() == []


async def test_step_out_of_range_is_422(
    stand_client: AsyncClient, extractor: FakeFrameExtractor
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)

    r = await _post_video(stand_client, site, camera, step_s=1)

    assert r.status_code == 422, r.text
    assert "5" in r.json()["detail"] and "3600" in r.json()["detail"]
    assert extractor.calls == []


async def test_missing_step_uses_default(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)

    r = await _post_video(stand_client, site, camera, step_s=None)

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["step_s"] == 30
    assert [i["photo"]["captured_at"] for i in body["items"]] == [
        "2026-10-20T09:30:00",
        "2026-10-20T09:30:30",
        "2026-10-20T09:31:00",
    ]


async def test_video_larger_than_limit_is_413_and_leaves_no_temp_file(
    stand_client: AsyncClient,
    container: AsyncContainer,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    extractor: FakeFrameExtractor,
) -> None:
    settings = await container.get(Settings)
    monkeypatch.setattr(settings.video, "max_mb", 0.0001)  # около 100 байт
    spool = tmp_path / "spool"
    spool.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(spool))
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)

    r = await _post_video(stand_client, site, camera, content=b"x" * 1000)

    assert r.status_code == 413, r.text
    assert r.json()["detail"] == "Видео слишком большое: максимум 0.0001 МБ"
    assert list(spool.iterdir()) == []
    assert extractor.calls == []


async def test_spool_upload_stops_at_limit_and_removes_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Файл без заранее известного размера: счёт идёт по кускам, временный файл убирается."""
    import io

    spool = tmp_path / "spool"
    spool.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(spool))
    upload = UploadFile(file=io.BytesIO(b"x" * 5000), filename="a.mp4")

    with pytest.raises(AppError) as excinfo:
        await spool_upload(upload, max_bytes=1000, max_mb=0.001)

    assert excinfo.value.status_code == 413
    assert list(spool.iterdir()) == []


async def test_video_extractor_error_is_422_with_its_text(
    stand_client: AsyncClient, extractor: FakeFrameExtractor
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)
    extractor.error = VideoError("Файл не похож на видео")

    r = await _post_video(stand_client, site, camera)

    assert r.status_code == 422, r.text
    assert r.json()["detail"] == "Файл не похож на видео"
    assert (await stand_client.get(f"/sites/{site}/photos")).json() == []


async def test_offset_recorded_at_is_converted_to_local_site_time(
    stand_client: AsyncClient, background: PhotoQueue
) -> None:
    """Время с поясом (UTC 06:30) — это местные 09:30 Москвы; без пояса — уже местное."""
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)

    r = await _post_video(stand_client, site, camera, recorded_at="2026-10-20T06:30:00+00:00")

    assert r.status_code == 201, r.text
    assert r.json()["items"][0]["photo"]["captured_at"] == "2026-10-20T09:30:00"


async def test_video_frames_processed_inline_when_not_background(
    stand_client: AsyncClient, container: AsyncContainer
) -> None:
    """UPLOAD__BACKGROUND=false: кадры обрабатываются в самом запросе, время видео сохраняется."""
    settings = await container.get(Settings)
    assert settings.upload.background is False  # тестовые настройки
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)

    r = await _post_video(stand_client, site, camera, step_s=60)

    assert r.status_code == 201, r.text
    photos = [i["photo"] for i in r.json()["items"]]
    assert {p["processing_status"] for p in photos} == {"done"}
    assert [p["captured_at"] for p in photos] == [
        "2026-10-20T09:30:00",
        "2026-10-20T09:31:00",
        "2026-10-20T09:32:00",
    ]
    assert {p["date_source"] for p in photos} == {"channel"}
