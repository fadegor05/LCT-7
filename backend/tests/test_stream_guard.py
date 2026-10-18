"""Защита снимков со стрима: служебные адреса, частные сети, одна съёмка на камеру, общий лимит."""

import asyncio
import re

import pytest

from app.adapters.stream.base import StreamBusy, StreamError
from app.adapters.stream.guard import PRIVATE_ADDRESS, SERVICE_ADDRESS, GuardedGrabber
from app.core.settings import Settings
from tests.fakes import FakeGrabber

HOSTS = {
    "localhost": ["127.0.0.1", "::1"],
    "minio": ["172.18.0.3"],
    "cam.site": ["192.168.1.10"],
    "cam.public": ["8.8.8.8"],
    "rebind.example": ["127.0.0.1"],
}


async def resolve(host: str) -> list[str]:
    return HOSTS.get(host, [host])


def guarded(inner=None, **stream) -> GuardedGrabber:
    settings = Settings()
    for key, value in stream.items():
        setattr(settings.stream, key, value)
    return GuardedGrabber(inner or FakeGrabber(), settings, resolve=resolve)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8000/api/health",
        "http://127.0.0.1:9000/frames",
        "http://[::1]/x",
        "http://169.254.169.254/latest/meta-data",
        "http://0.0.0.0:5432/",
        "http://minio:9000/frames/a.jpg",
        "http://172.18.0.3:9000/frames/a.jpg",  # адрес minio напрямую
        "http://[::ffff:127.0.0.1]/x",  # IPv4-mapped петля
    ],
)
async def test_service_and_loopback_addresses_are_never_cameras(url: str) -> None:
    inner = FakeGrabber()
    with pytest.raises(StreamError, match=SERVICE_ADDRESS):
        await guarded(inner).grab(url)
    assert inner.calls == []


async def test_private_network_is_refused_by_default() -> None:
    inner = FakeGrabber()
    for url in (
        "rtsp://admin:pw@cam.site/live",
        "rtsp://192.168.1.10:554/live",
        "rtsp://10.0.0.5/x",
    ):
        with pytest.raises(StreamError, match=re.escape(PRIVATE_ADDRESS)):
            await guarded(inner).grab(url)
    assert inner.calls == []


async def test_allowlisted_camera_network_is_fine() -> None:
    inner = FakeGrabber()
    grabber = guarded(inner, allowed_networks=["192.168.1.0/24"])
    assert (await grabber.grab("rtsp://admin:pw@cam.site/live"))[:2] == b"\xff\xd8"
    assert (await grabber.grab("rtsp://192.168.1.77:554/live"))[:2] == b"\xff\xd8"
    with pytest.raises(StreamError, match=re.escape(PRIVATE_ADDRESS)):
        await grabber.grab("rtsp://10.0.0.5/live")  # вне списка — по-прежнему нельзя
    assert len(inner.calls) == 2


async def test_allowlist_does_not_open_loopback_or_service_addresses() -> None:
    inner = FakeGrabber()
    grabber = guarded(inner, allowed_networks=["127.0.0.0/8", "172.18.0.0/16"])
    with pytest.raises(StreamError, match=SERVICE_ADDRESS):
        await grabber.grab("http://127.0.0.1:9000/x")
    with pytest.raises(StreamError, match=SERVICE_ADDRESS):
        await grabber.grab("http://172.18.0.3:9000/x")
    assert inner.calls == []


async def test_public_camera_is_fine() -> None:
    inner = FakeGrabber()
    assert (await guarded(inner).grab("rtsp://cam.public/live"))[:2] == b"\xff\xd8"
    assert inner.calls == ["rtsp://cam.public/live"]


async def test_name_resolving_to_loopback_is_refused() -> None:
    inner = FakeGrabber()
    with pytest.raises(StreamError, match=SERVICE_ADDRESS):
        await guarded(inner).grab("rtsp://rebind.example/live")
    assert inner.calls == []


async def test_extra_networks_can_be_closed() -> None:
    inner = FakeGrabber()
    with pytest.raises(StreamError, match=SERVICE_ADDRESS):
        await guarded(inner, blocked_networks=["8.8.0.0/16"]).grab("rtsp://8.8.8.8/live")
    assert inner.calls == []


async def test_extra_service_hosts_can_be_closed() -> None:
    inner = FakeGrabber()
    with pytest.raises(StreamError, match=SERVICE_ADDRESS):
        await guarded(inner, blocked_hosts=["cam.public"]).grab("rtsp://cam.public/live")


async def test_a_link_without_host_leaks_nothing() -> None:
    with pytest.raises(StreamError) as e:
        await guarded().grab("rtsp://admin:secret@/live")
    assert "secret" not in str(e.value)


class SlowGrabber(FakeGrabber):
    def __init__(self) -> None:
        super().__init__()
        self.release = asyncio.Event()
        self.running = 0
        self.peak = 0

    async def grab(self, url: str) -> bytes:
        self.running += 1
        self.peak = max(self.peak, self.running)
        try:
            await self.release.wait()
            return await super().grab(url)
        finally:
            self.running -= 1


async def test_one_capture_per_camera_at_a_time() -> None:
    inner = SlowGrabber()
    grabber = guarded(inner, allowed_networks=["192.168.1.0/24"])
    first = asyncio.create_task(grabber.grab("rtsp://192.168.1.10/live"))
    await asyncio.sleep(0)
    with pytest.raises(StreamBusy, match="Снимок с этой камеры уже идёт"):
        await grabber.grab("rtsp://192.168.1.10/live")
    inner.release.set()
    assert (await first)[:2] == b"\xff\xd8"
    assert (await grabber.grab("rtsp://192.168.1.10/live"))[:2] == b"\xff\xd8"


async def test_all_captures_share_one_limit() -> None:
    inner = SlowGrabber()
    grabber = guarded(inner, concurrency=2, allowed_networks=["192.168.1.0/24"])
    tasks = [asyncio.create_task(grabber.grab(f"rtsp://192.168.1.{i}/live")) for i in range(1, 6)]
    await asyncio.sleep(0.05)
    assert inner.running == 2
    inner.release.set()
    await asyncio.gather(*tasks)
    assert inner.peak == 2
