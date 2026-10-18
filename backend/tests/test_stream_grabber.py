"""Снимок со стрима через ffmpeg: команда, разбор ошибок, таймаут, маскировка ссылки.

Настоящий ffmpeg и сеть не трогаем: процесс подменяет FakeSpawn.
"""

import asyncio
import subprocess
from typing import Any

import pytest

from app.adapters.stream.base import StreamError, mask_credentials
from app.adapters.stream.ffmpeg import UNKNOWN, FfmpegGrabber, build_args

JPEG = b"\xff\xd8\xff\xe0fake-frame"


class FakeProcess:
    def __init__(self, out: bytes = b"", err: bytes = b"", returncode: int = 0, hang=False):
        self._out = out
        self._err = err
        self.returncode: int | None = returncode
        self._hang = hang
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        if self._hang:
            await asyncio.sleep(3600)
        return self._out, self._err

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return self.returncode or 0


class FakeSpawn:
    def __init__(self, process: FakeProcess | None = None, error: Exception | None = None):
        self.process = process or FakeProcess()
        self.error = error
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    async def __call__(self, *args: Any, **kwargs: Any) -> FakeProcess:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return self.process


def grabber(spawn: FakeSpawn, timeout_s: float = 15.0) -> FfmpegGrabber:
    return FfmpegGrabber(timeout_s=timeout_s, spawn=spawn)


def test_protocol_whitelist_comes_before_the_input_and_keeps_local_files_out() -> None:
    args = build_args("rtsp://admin:pw@10.0.0.5/live")
    assert args[0] == "ffmpeg"
    whitelist = args[args.index("-protocol_whitelist") + 1].split(",")
    assert {"rtsp", "http", "https"} <= set(whitelist)
    assert not {"file", "concat", "subfile", "pipe"} & set(whitelist)
    assert args.index("-protocol_whitelist") < args.index("-i")
    assert args[args.index("-i") + 1] == "rtsp://admin:pw@10.0.0.5/live"


def test_rtsp_is_read_over_tcp_and_one_mjpeg_frame_goes_to_stdout() -> None:
    args = build_args("rtsp://10.0.0.5/live")
    assert args[args.index("-rtsp_transport") + 1] == "tcp"
    assert args[args.index("-frames:v") + 1] == "1"
    assert args[args.index("-c:v") + 1] == "mjpeg"
    assert args[-1] == "-"


def test_http_stream_has_no_rtsp_transport_option() -> None:
    assert "-rtsp_transport" not in build_args("http://10.0.0.5/snapshot.jpg")


async def test_returns_the_frame_bytes_without_a_shell() -> None:
    spawn = FakeSpawn(FakeProcess(out=JPEG))
    assert await grabber(spawn).grab("http://10.0.0.5/snapshot.jpg") == JPEG
    ((args, kwargs),) = spawn.calls
    assert args[0] == "ffmpeg" and "sh" not in args and "-c" not in args
    assert args[args.index("-i") + 1] == "http://10.0.0.5/snapshot.jpg"
    assert kwargs.get("shell") is None
    assert kwargs["stdin"] == subprocess.DEVNULL


@pytest.mark.parametrize("url", ["file:/etc/passwd", "concat:a|b", "pipe:0", "ftp://cam/x"])
async def test_only_stream_schemes_reach_ffmpeg(url: str) -> None:
    spawn = FakeSpawn()
    with pytest.raises(StreamError):
        await grabber(spawn).grab(url)
    assert spawn.calls == []


@pytest.mark.parametrize(
    ("stderr", "reason"),
    [
        (b"Connection refused", "Камера отказала в соединении"),
        (b"HTTP error 401 Unauthorized", "Камера не пустила: проверьте логин и пароль в ссылке"),
        (b"Server returned 403 Forbidden", "Камера не пустила: проверьте логин и пароль в ссылке"),
        (b"Server returned 404 Not Found", "По ссылке нет видео"),
        (b"Server returned 500", UNKNOWN),
    ],
)
async def test_failures_are_named_in_plain_words(stderr: bytes, reason: str) -> None:
    spawn = FakeSpawn(FakeProcess(err=stderr, returncode=1))
    with pytest.raises(StreamError) as e:
        await grabber(spawn).grab("http://10.0.0.5/x.jpg")
    assert str(e.value) == reason


async def test_empty_output_is_a_failure_even_with_exit_zero() -> None:
    with pytest.raises(StreamError) as e:
        await grabber(FakeSpawn(FakeProcess(out=b"", returncode=0))).grab("rtsp://10.0.0.5/x")
    assert str(e.value) == UNKNOWN


async def test_credentials_never_reach_the_error_text() -> None:
    stderr = b"rtsp://admin:secret@10.0.0.5:554/live: Connection refused"
    with pytest.raises(StreamError) as e:
        await grabber(FakeSpawn(FakeProcess(err=stderr, returncode=1))).grab(
            "rtsp://admin:secret@10.0.0.5:554/live"
        )
    assert "secret" not in str(e.value)
    odd = b"rtsp://admin:secret@10.0.0.5/live: something unexpected"
    with pytest.raises(StreamError) as e:
        await grabber(FakeSpawn(FakeProcess(err=odd, returncode=1))).grab("rtsp://x/y")
    assert "secret" not in str(e.value)


async def test_silent_camera_times_out_and_the_process_is_killed() -> None:
    process = FakeProcess(hang=True)
    with pytest.raises(StreamError, match="Камера не ответила за 0.05 с"):
        await grabber(FakeSpawn(process), timeout_s=0.05).grab("rtsp://10.0.0.5/x")
    assert process.killed


async def test_missing_ffmpeg_is_a_readable_error() -> None:
    spawn = FakeSpawn(error=FileNotFoundError("ffmpeg"))
    with pytest.raises(StreamError) as e:
        await grabber(spawn).grab("rtsp://10.0.0.5/x")
    assert str(e.value) == "На сервере нет ffmpeg: снимки со стрима недоступны"


async def test_other_spawn_errors_are_masked_stream_errors() -> None:
    with pytest.raises(StreamError) as e:
        await grabber(FakeSpawn(error=OSError("boom"))).grab("rtsp://admin:pw@10.0.0.5/x")
    assert str(e.value) == UNKNOWN


def test_credentials_are_masked_in_any_text() -> None:
    text = "rtsp://admin:secret@10.0.0.5:554/live and http://u:p@cam/x"
    assert mask_credentials(text) == "rtsp://***@10.0.0.5:554/live and http://***@cam/x"
    assert mask_credentials("rtsp://10.0.0.5/live") == "rtsp://10.0.0.5/live"
    # Пароль, вставленный как есть, с «@» или «/» внутри
    assert mask_credentials("rtsp://admin:p@ss@cam/live") == "rtsp://***@cam/live"
    assert mask_credentials("rtsp://admin:pa/ss@cam:554/x") == "rtsp://***@cam:554/x"
