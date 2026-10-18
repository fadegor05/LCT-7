"""Снимки со стрима: «Снять кадр сейчас», планировщик, запуск в lifespan.

Сниматель — FakeGrabber из conftest (`grabber`), детектор — FakeDetector.
"""

import uuid
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from dishka import AsyncContainer
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.adapters.ml.base import DetectorClient
from app.core.settings import Settings, get_settings
from app.domains.camera.models import Camera
from app.domains.camera.stream import StreamCapture
from app.domains.photo.models import Photo
from app.domains.user.service import UserService
from app.main import create_app
from tests.fakes import FakeDetector, FakeGrabber

STREAM = "rtsp://admin:secret@10.0.0.5/live"
# Пятница 18.09.2026, 10:00 по Москве
FRIDAY_10 = datetime(2026, 9, 18, 7, 0, tzinfo=UTC)
MSK = ZoneInfo("Europe/Moscow")


@pytest.fixture
async def stand_client(client: AsyncClient, container: AsyncContainer) -> AsyncClient:
    async with container() as request_container:
        await (await request_container.get(UserService)).ensure_stand_user()
    return client


@pytest.fixture
async def maker(container: AsyncContainer) -> async_sessionmaker[AsyncSession]:
    return await container.get(async_sessionmaker[AsyncSession])


async def _site(client: AsyncClient, name: str = "Объект") -> str:
    return (await client.post("/sites", json={"name": name})).json()["id"]


async def _camera(client: AsyncClient, site: str, name: str = "К-1", **body) -> str:
    r = await client.post(f"/sites/{site}/cameras", json={"name": name, **body})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def _stored(maker, camera_id: str) -> Camera:
    async with maker() as session:
        camera = await session.get(Camera, uuid.UUID(camera_id))
        assert camera is not None
        return camera


async def _capture(client: AsyncClient, site: str, camera: str):
    return await client.post(f"/sites/{site}/cameras/{camera}/capture")


async def test_capture_now_stores_the_frame_in_the_camera_feed(
    stand_client: AsyncClient, grabber: FakeGrabber, container: AsyncContainer, maker
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)

    r = await _capture(stand_client, site, camera)

    assert r.status_code == 201, r.text
    frame = r.json()
    assert frame["camera_id"] == camera
    assert frame["date_source"] == "channel"
    assert frame["captured_on"] == datetime.now(MSK).date().isoformat()
    assert grabber.calls == [STREAM]
    # Кадр идёт по обычному пути: его видел детектор
    detector = await container.get(DetectorClient)
    assert isinstance(detector, FakeDetector)
    assert [name for name, _ in detector.calls] == [frame["original_name"]]
    stored = await _stored(maker, camera)
    assert stored.last_capture_at is not None
    assert stored.last_capture_error is None and stored.capture_failures == 0


async def test_capture_reports_why_without_the_password(
    stand_client: AsyncClient, grabber: FakeGrabber, maker
) -> None:
    grabber.errors[STREAM] = "Камера не ответила за 15 с"
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)

    r = await _capture(stand_client, site, camera)

    assert r.status_code == 422
    assert r.json()["detail"] == "Камера не ответила за 15 с"
    stored = await _stored(maker, camera)
    assert stored.last_capture_error == "Камера не ответила за 15 с"
    assert stored.capture_failures == 1
    listed = (await stand_client.get(f"/sites/{site}/cameras")).json()[0]
    assert listed["last_capture_error"] == "Камера не ответила за 15 с"
    assert "secret" not in r.text


async def test_capture_needs_a_stream_link(stand_client: AsyncClient) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site)
    r = await _capture(stand_client, site, camera)
    assert r.status_code == 422
    assert r.json()["detail"] == "У камеры нет ссылки на стрим"


async def test_capture_of_another_sites_camera_is_404(stand_client: AsyncClient) -> None:
    site = await _site(stand_client, "Первый")
    other = await _site(stand_client, "Второй")
    foreign = await _camera(stand_client, other, stream_url=STREAM)
    r = await _capture(stand_client, site, foreign)
    assert r.status_code == 404


async def test_busy_camera_answers_409(stand_client: AsyncClient, grabber: FakeGrabber) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)
    grabber.busy = True
    r = await _capture(stand_client, site, camera)
    assert r.status_code == 409
    assert r.json()["detail"] == "Снимок с этой камеры уже идёт"


async def test_link_changed_during_the_capture_is_not_recorded(
    stand_client: AsyncClient, grabber: FakeGrabber, maker
) -> None:
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)
    real_grab = grabber.grab

    async def edited_meanwhile(url: str) -> bytes:
        # Пока сервер ждёт камеру, транзакция закрыта: правка ссылки не ждёт снимка
        r = await stand_client.patch(
            f"/sites/{site}/cameras/{camera}", json={"stream_url": "rtsp://10.0.0.9/live"}
        )
        assert r.status_code == 200
        return await real_grab(url)

    grabber.grab = edited_meanwhile  # type: ignore[method-assign]
    r = await _capture(stand_client, site, camera)

    assert r.status_code == 409
    assert r.json()["detail"] == "Ссылку камеры изменили во время снимка — снимите кадр ещё раз"
    stored = await _stored(maker, camera)
    assert stored.stream_url == "rtsp://10.0.0.9/live" and stored.last_capture_at is None


async def test_a_new_link_resets_failures(
    stand_client: AsyncClient, grabber: FakeGrabber, maker
) -> None:
    grabber.errors[STREAM] = "Камера не ответила за 15 с"
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)
    await _capture(stand_client, site, camera)
    await stand_client.patch(
        f"/sites/{site}/cameras/{camera}", json={"stream_url": "rtsp://10.0.0.9/live"}
    )
    stored = await _stored(maker, camera)
    assert (stored.capture_failures, stored.last_capture_error) == (0, None)


async def test_scheduler_captures_due_cameras_with_a_link(
    stand_client: AsyncClient, container: AsyncContainer, grabber: FakeGrabber, maker
) -> None:
    site = await _site(stand_client)
    live = await _camera(stand_client, site, "К-1", stream_url=STREAM)
    failing = await _camera(stand_client, site, "К-2", stream_url="rtsp://10.0.0.6/live")
    await _camera(stand_client, site, "К-3")  # без ссылки — не снимаем
    grabber.errors["rtsp://10.0.0.6/live"] = "По ссылке не удалось получить кадр"
    capture = await container.get(StreamCapture)

    assert await capture.run_once(FRIDAY_10) == 2
    assert sorted(grabber.calls) == sorted([STREAM, "rtsp://10.0.0.6/live"])
    async with maker() as session:
        photos = (await session.execute(select(Photo))).scalars().all()
    assert [(str(p.camera_id), p.captured_on) for p in photos] == [(live, date(2026, 9, 18))]
    assert (await _stored(maker, failing)).capture_failures == 1

    # Через минуту никому не пора; через 5 минут — снова обеим
    assert await capture.run_once(FRIDAY_10 + timedelta(minutes=1)) == 0
    assert await capture.run_once(FRIDAY_10 + timedelta(minutes=5)) == 2


async def test_scheduler_waits_for_the_site_hours(
    stand_client: AsyncClient, container: AsyncContainer, grabber: FakeGrabber
) -> None:
    site = await _site(stand_client)
    await _camera(stand_client, site, stream_url=STREAM)
    capture = await container.get(StreamCapture)
    assert await capture.run_once(FRIDAY_10.replace(hour=18)) == 0  # 21:00 по Москве
    assert await capture.run_once(FRIDAY_10) == 1
    assert grabber.calls == [STREAM]


async def test_backoff_after_failures_postpones_the_next_try(
    stand_client: AsyncClient, container: AsyncContainer, grabber: FakeGrabber, maker
) -> None:
    grabber.errors[STREAM] = "Камера не ответила за 15 с"
    site = await _site(stand_client)
    camera = await _camera(stand_client, site, stream_url=STREAM)
    async with maker() as session:  # три сбоя подряд: следующий интервал удвоен
        await session.execute(
            update(Camera).where(Camera.id == uuid.UUID(camera)).values(capture_failures=3)
        )
        await session.commit()
    capture = await container.get(StreamCapture)
    # Четвёртый сбой: интервал 10 мин → 20 мин, и так до часа
    assert await capture.run_once(FRIDAY_10) == 1
    assert (await _stored(maker, camera)).capture_failures == 4
    assert await capture.run_once(FRIDAY_10 + timedelta(minutes=10)) == 0
    assert await capture.run_once(FRIDAY_10 + timedelta(minutes=20)) == 1


async def test_lifespan_does_not_capture_unless_enabled(
    container: AsyncContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    started: list[str] = []
    stopped: list[str] = []

    async def start(self) -> None:
        started.append("start")

    async def stop(self) -> None:
        stopped.append("stop")

    monkeypatch.setattr(StreamCapture, "start", start)
    monkeypatch.setattr(StreamCapture, "stop", stop)
    settings = get_settings()
    monkeypatch.setattr(settings.stream, "enabled", False)
    app = create_app(container)
    async with app.router.lifespan_context(app):
        pass
    assert started == [] and stopped == []

    monkeypatch.setattr(settings.stream, "enabled", True)
    async with app.router.lifespan_context(app):
        pass
    assert started == ["start"] and stopped == ["stop"]


def test_stream_is_off_in_the_default_settings() -> None:
    assert Settings().stream.enabled is False


async def test_production_container_wires_the_grabber_and_the_scheduler() -> None:
    from app.adapters.stream.base import StreamGrabber
    from app.adapters.stream.guard import GuardedGrabber
    from app.plugins.di import create_container

    container = create_container()
    try:
        assert isinstance(await container.get(StreamGrabber), GuardedGrabber)
        assert isinstance(await container.get(StreamCapture), StreamCapture)
    finally:
        await container.close()
