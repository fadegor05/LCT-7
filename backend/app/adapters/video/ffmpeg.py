"""Кадры из загруженного видео через ffmpeg: длительность, шаг, лимит кадров.

Процессы запускаются без оболочки, только с локальными файлами: сетевые протоколы закрыты.
"""

import asyncio
import contextlib
import logging
import math
import subprocess
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from app.adapters.video.base import VideoError

logger = logging.getLogger(__name__)

# Только локальные файлы: ffmpeg не должен ходить по сети или читать чужие протоколы
PROTOCOLS = "file"
NOT_VIDEO = "Файл не похож на видео"
NO_FFMPEG = "На сервере нет ffmpeg: загрузка видео недоступна"

Spawn = Callable[..., Awaitable[Any]]


class FfmpegFrameExtractor:
    def __init__(
        self,
        timeout_s: float,
        ffmpeg: str = "ffmpeg",
        ffprobe: str = "ffprobe",
        spawn: Spawn = asyncio.create_subprocess_exec,
    ) -> None:
        self._timeout_s = timeout_s
        self._ffmpeg = ffmpeg
        self._ffprobe = ffprobe
        self._spawn = spawn

    async def duration_s(self, path: Path) -> float:
        args = [
            self._ffprobe,
            "-v",
            "error",
            "-protocol_whitelist",
            PROTOCOLS,
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ]
        code, out, err = await self._run(args, stdout=asyncio.subprocess.PIPE)
        if code != 0:
            logger.info("ffprobe завершился с кодом %s: %s", code, err[-300:])
            raise VideoError(NOT_VIDEO)
        try:
            duration = float(out.decode("utf-8", "replace").strip())
        except ValueError as e:
            logger.info("ffprobe не выдал длительность: %s", err[-300:])
            raise VideoError(NOT_VIDEO) from e
        if not math.isfinite(duration) or duration <= 0:
            logger.info("ffprobe выдал длительность %s", duration)
            raise VideoError(NOT_VIDEO)
        return duration

    async def extract(self, path: Path, step_s: int, max_frames: int) -> list[bytes]:
        duration = await self.duration_s(path)
        frames = math.floor(duration / step_s) + 1
        if frames > max_frames:
            # Наименьший шаг, при котором кадров не больше лимита
            fits = math.ceil(duration / (max_frames - 1))
            raise VideoError(
                f"В отрывке получится {frames} кадров, максимум {max_frames}. "
                f"Увеличьте шаг до {fits} с или больше"
            )
        with tempfile.TemporaryDirectory() as tmp:
            args = [
                self._ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-protocol_whitelist",
                PROTOCOLS,
                "-i",
                str(path),
                "-vf",
                # Первый кадр — на нулевой секунде; round=up берёт кадр не раньше отметки,
                # иначе последняя отметка (например 9 с) у round=near теряется
                f"fps=1/{step_s}:start_time=0:round=up",
                "-frames:v",
                str(frames),
                "-q:v",
                "3",
                "-f",
                "image2",
                str(Path(tmp) / "f%05d.jpg"),
            ]
            code, _, err = await self._run(args)
            if code != 0:
                logger.info("ffmpeg завершился с кодом %s: %s", code, err[-300:])
                raise VideoError("Не удалось прочитать видео")
            files = sorted(Path(tmp).glob("f*.jpg"))
            if not files:
                logger.info("ffmpeg не дал кадров: %s", err[-300:])
                raise VideoError("В видео не нашлось кадров")
            return [file.read_bytes() for file in files]

    async def _run(
        self, args: list[str], stdout: int = subprocess.DEVNULL
    ) -> tuple[int, bytes, bytes]:
        """Запуск с таймаутом: (код выхода, stdout, stderr). Код выхода разбирает вызывающий."""
        try:
            process = await self._spawn(
                *args,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            raise VideoError(NO_FFMPEG) from e
        except OSError as e:
            logger.info("ffmpeg не запустился: %s", type(e).__name__)
            raise VideoError("Не удалось запустить обработку видео") from e
        try:
            out, err = await asyncio.wait_for(process.communicate(), self._timeout_s)
        except TimeoutError as e:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            raise VideoError(f"Обработка видео не уложилась в {self._timeout_s:g} с") from e
        return process.returncode or 0, out or b"", err or b""
