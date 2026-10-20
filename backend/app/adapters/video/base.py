"""Кадры из видео: протокол и ошибки для инженера."""

from pathlib import Path
from typing import Protocol


class VideoError(Exception):
    """Видео не обработано; текст — для инженера, без путей и вывода ffmpeg."""


class FrameExtractor(Protocol):
    async def duration_s(self, path: Path) -> float:
        """Длительность видео в секундах; иначе `VideoError`."""
        ...

    async def extract(self, path: Path, step_s: int, max_frames: int) -> list[bytes]:
        """Кадры JPEG каждые `step_s` секунд, с нуля, по порядку времени; иначе `VideoError`."""
        ...
