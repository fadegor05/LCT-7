"""Извлечение кадров из видео через ffmpeg: команды, длительность, лимиты, таймаут.

Настоящий ffmpeg не трогаем: процесс подменяет FakeSpawn, он же пишет «кадры» в каталог вывода.
"""

import asyncio
from pathlib import Path
from typing import Any

import pytest

from app.adapters.video.base import VideoError
from app.adapters.video.ffmpeg import FfmpegFrameExtractor

JPEG = b"\xff\xd8\xff\xe0"


class FakeProcess:
    def __init__(self, out: bytes = b"", err: bytes = b"", returncode: int = 0, hang: bool = False):
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
    """Подмена asyncio.create_subprocess_exec: ffprobe отдаёт длительность, ffmpeg пишет кадры."""

    def __init__(
        self,
        *,
        duration: bytes = b"10.0\n",
        frames: int = 0,
        ffprobe_rc: int = 0,
        ffmpeg_rc: int = 0,
        ffmpeg_err: bytes = b"",
        error: Exception | None = None,
        hang: bool = False,
    ) -> None:
        self.duration = duration
        self.frames = frames
        self.ffprobe_rc = ffprobe_rc
        self.ffmpeg_rc = ffmpeg_rc
        self.ffmpeg_err = ffmpeg_err
        self.error = error
        self.hang = hang
        self.calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.processes: list[FakeProcess] = []

    async def __call__(self, *args: Any, **kwargs: Any) -> FakeProcess:
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        if args[0] == "ffprobe":
            process = FakeProcess(out=self.duration, returncode=self.ffprobe_rc, hang=self.hang)
        else:
            # Последний аргумент — шаблон вывода: f%05d.jpg в каталоге tmpdir
            out_dir = Path(args[-1]).parent
            for i in range(self.frames):
                (out_dir / f"f{i + 1:05d}.jpg").write_bytes(JPEG + str(i).encode())
            process = FakeProcess(err=self.ffmpeg_err, returncode=self.ffmpeg_rc, hang=self.hang)
        self.processes.append(process)
        return process

    def ffmpeg_args(self) -> list[Any]:
        return next(list(a) for a, _ in self.calls if a[0] == "ffmpeg")

    def ffprobe_args(self) -> list[Any]:
        return next(list(a) for a, _ in self.calls if a[0] == "ffprobe")


def extractor(spawn: FakeSpawn, timeout_s: float = 60.0) -> FfmpegFrameExtractor:
    return FfmpegFrameExtractor(timeout_s=timeout_s, spawn=spawn)


def _value(args: list[Any], flag: str) -> Any:
    return args[args.index(flag) + 1]


async def test_duration_args_local_files_only_and_no_shell(tmp_path: Path) -> None:
    path = tmp_path / "my clip.mp4"
    spawn = FakeSpawn()

    await extractor(spawn).duration_s(path)

    args = spawn.ffprobe_args()
    assert args[0] == "ffprobe"
    assert _value(args, "-protocol_whitelist") == "file"
    assert _value(args, "-show_entries") == "format=duration"
    assert _value(args, "-of") == "default=nw=1:nk=1"
    assert args[-1] == str(path)  # путь с пробелом — один аргумент, без оболочки
    _, kwargs = spawn.calls[0]
    assert "shell" not in kwargs


async def test_extract_args_local_files_only_and_no_shell(tmp_path: Path) -> None:
    path = tmp_path / "clip.mp4"
    spawn = FakeSpawn(duration=b"10.0\n", frames=4)

    await extractor(spawn).extract(path, step_s=3, max_frames=200)

    args = spawn.ffmpeg_args()
    assert args[0] == "ffmpeg"
    assert "-protocol_whitelist" in args
    assert _value(args, "-protocol_whitelist") == "file"
    assert {"-hide_banner", "-nostdin"} <= set(args)
    assert _value(args, "-loglevel") == "error"
    assert _value(args, "-i") == str(path)
    assert _value(args, "-vf") == "fps=1/3:start_time=0:round=up"
    assert _value(args, "-frames:v") == "4"
    assert _value(args, "-q:v") == "3"
    ffmpeg_kwargs = spawn.calls[-1][1]
    assert "shell" not in ffmpeg_kwargs


@pytest.mark.parametrize(
    ("raw", "expected"),
    [(b"12.5\n", 12.5), (b"  7 \n", 7.0), (b"3600.000000\n", 3600.0)],
)
async def test_duration_parses_float(tmp_path: Path, raw: bytes, expected: float) -> None:
    spawn = FakeSpawn(duration=raw)
    assert await extractor(spawn).duration_s(tmp_path / "a.mp4") == expected


@pytest.mark.parametrize(
    "spawn",
    [
        FakeSpawn(ffprobe_rc=1),
        FakeSpawn(duration=b""),
        FakeSpawn(duration=b"N/A\n"),
        FakeSpawn(duration=b"0\n"),
        FakeSpawn(duration=b"-3\n"),
        FakeSpawn(duration=b"inf\n"),
        FakeSpawn(duration=b"abc\n"),
    ],
)
async def test_unreadable_duration_means_not_a_video(tmp_path: Path, spawn: FakeSpawn) -> None:
    with pytest.raises(VideoError, match="Файл не похож на видео"):
        await extractor(spawn).duration_s(tmp_path / "a.mp4")


async def test_frames_limit_error_names_the_step_that_fits(tmp_path: Path) -> None:
    # 1000 с при шаге 5 с дают floor(1000/5)+1 = 201 кадр; лимит 10 → шаг ceil(1000/9) = 112 с
    spawn = FakeSpawn(duration=b"1000\n")

    with pytest.raises(VideoError) as info:
        await extractor(spawn).extract(tmp_path / "a.mp4", step_s=5, max_frames=10)

    assert str(info.value) == (
        "В отрывке получится 201 кадров, максимум 10. Увеличьте шаг до 112 с или больше"
    )
    assert not any(a[0] == "ffmpeg" for a, _ in spawn.calls)


async def test_step_from_the_error_text_fits_the_limit(tmp_path: Path) -> None:
    spawn = FakeSpawn(duration=b"1000\n", frames=9)

    await extractor(spawn).extract(tmp_path / "a.mp4", step_s=112, max_frames=10)

    assert _value(spawn.ffmpeg_args(), "-frames:v") == "9"


async def test_frames_come_back_in_time_order(tmp_path: Path) -> None:
    spawn = FakeSpawn(duration=b"10\n", frames=4)

    result = await extractor(spawn).extract(tmp_path / "a.mp4", step_s=3, max_frames=200)

    assert len(result) == 4
    assert all(frame.startswith(JPEG) for frame in result)
    assert [frame[len(JPEG) :] for frame in result] == [b"0", b"1", b"2", b"3"]


async def test_no_frames_is_an_error(tmp_path: Path) -> None:
    spawn = FakeSpawn(duration=b"10\n", frames=0)

    with pytest.raises(VideoError, match="В видео не нашлось кадров"):
        await extractor(spawn).extract(tmp_path / "a.mp4", step_s=3, max_frames=200)


async def test_ffmpeg_failure_hides_stderr_and_path(tmp_path: Path) -> None:
    path = tmp_path / "secret-site.mp4"
    spawn = FakeSpawn(duration=b"10\n", ffmpeg_rc=1, ffmpeg_err=f"{path}: Invalid data".encode())

    with pytest.raises(VideoError) as info:
        await extractor(spawn).extract(path, step_s=3, max_frames=200)

    assert "Invalid data" not in str(info.value)
    assert str(tmp_path) not in str(info.value)


async def test_timeout_kills_the_process(tmp_path: Path) -> None:
    spawn = FakeSpawn(hang=True)

    with pytest.raises(VideoError, match="Обработка видео не уложилась в 0.05 с"):
        await extractor(spawn, timeout_s=0.05).duration_s(tmp_path / "a.mp4")

    assert spawn.processes[0].killed


@pytest.mark.parametrize("call", ["duration", "extract"])
async def test_missing_ffmpeg_binary(tmp_path: Path, call: str) -> None:
    spawn = FakeSpawn(error=FileNotFoundError("ffprobe"))
    frame_extractor = extractor(spawn)

    with pytest.raises(VideoError, match="На сервере нет ffmpeg: загрузка видео недоступна"):
        if call == "duration":
            await frame_extractor.duration_s(tmp_path / "a.mp4")
        else:
            await frame_extractor.extract(tmp_path / "a.mp4", step_s=3, max_frames=200)
