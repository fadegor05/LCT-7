"""Снимок кадра со стрима через ffmpeg: RTSP, RTSPS, HTTP(S) — MJPEG, HLS, снимок камеры.

Процесс запускается без оболочки: ссылка идёт в аргументы как одна строка.
"""

import asyncio
import contextlib
import logging
import subprocess
from collections.abc import Awaitable, Callable
from typing import Any

from app.adapters.stream.base import StreamError, mask_credentials

logger = logging.getLogger(__name__)

# Ответ ffmpeg инженеру не отдаём как есть: по нему не изучить, что стоит по адресу
_REASONS = (
    (("Connection refused",), "Камера отказала в соединении"),
    (
        ("401", "403", "Unauthorized", "Forbidden"),
        "Камера не пустила: проверьте логин и пароль в ссылке",
    ),
    (("404",), "По ссылке нет видео"),
)
UNKNOWN = "По ссылке не удалось получить кадр"
# Только эти схемы: `file:`, `concat:`, `pipe:` и прочие локальные ffmpeg не открываем
SCHEMES = ("rtsp://", "rtsps://", "http://", "https://")
SCHEME_ERROR = "ссылка на стрим — rtsp://, rtsps://, http:// или https://"
# Только сетевые протоколы
PROTOCOLS = "rtsp,rtsps,rtp,srtp,udp,tcp,tls,http,https,httpproxy,crypto,hls"

Spawn = Callable[..., Awaitable[Any]]


def _reason(stderr: str) -> str:
    for marks, reason in _REASONS:
        if any(mark in stderr for mark in marks):
            return reason
    return UNKNOWN


def build_args(url: str, binary: str = "ffmpeg") -> list[str]:
    """Команда ffmpeg, которая снимает один кадр JPEG в stdout."""
    args = [binary, "-hide_banner", "-loglevel", "error", "-nostdin"]
    args += ["-protocol_whitelist", PROTOCOLS]
    if url.lower().startswith(("rtsp://", "rtsps://")):
        args += ["-rtsp_transport", "tcp"]  # UDP теряется за NAT и в Docker
    args += ["-i", url, "-frames:v", "1", "-f", "image2", "-c:v", "mjpeg", "-q:v", "3", "-"]
    return args


class FfmpegGrabber:
    def __init__(
        self,
        timeout_s: float,
        binary: str = "ffmpeg",
        spawn: Spawn = asyncio.create_subprocess_exec,
    ) -> None:
        self._timeout_s = timeout_s
        self._binary = binary
        self._spawn = spawn

    async def grab(self, url: str) -> bytes:
        if not url.lower().startswith(SCHEMES):
            raise StreamError(SCHEME_ERROR)
        args = build_args(url, self._binary)
        try:
            process = await self._spawn(
                *args,
                stdin=subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            raise StreamError("На сервере нет ffmpeg: снимки со стрима недоступны") from e
        except OSError as e:
            logger.info("ffmpeg не запустился: %s", type(e).__name__)
            raise StreamError(UNKNOWN) from e
        try:
            out, err = await asyncio.wait_for(process.communicate(), self._timeout_s)
        except TimeoutError as e:
            with contextlib.suppress(ProcessLookupError):
                process.kill()
            await process.wait()
            raise StreamError(f"Камера не ответила за {self._timeout_s:g} с") from e
        if process.returncode != 0 or not out:
            detail = mask_credentials(err.decode("utf-8", "replace").strip())
            logger.info("ffmpeg не дал кадр: %s", detail[-300:])
            raise StreamError(_reason(detail))
        return out
