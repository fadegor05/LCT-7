"""Настоящий ffmpeg: кадры из сгенерированного клипа. Пропускается без ffmpeg в PATH."""

import shutil
import subprocess
from pathlib import Path

import pytest

from app.adapters.video.ffmpeg import FfmpegFrameExtractor

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="нет ffmpeg в PATH")


async def test_real_ffmpeg_extracts_frames_every_three_seconds(tmp_path: Path) -> None:
    clip = tmp_path / "clip.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=10:size=320x240:rate=5",
            "-pix_fmt",
            "yuv420p",
            str(clip),
        ],
        check=True,
    )

    frames = await FfmpegFrameExtractor(timeout_s=60).extract(clip, step_s=3, max_frames=200)

    # 0, 3, 6, 9 с
    assert len(frames) == 4
    assert all(frame.startswith(b"\xff\xd8") for frame in frames)
