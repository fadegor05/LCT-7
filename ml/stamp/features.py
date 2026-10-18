"""Ячейка штампа как карта признаков, не зависящая от фона за строкой.

Знаки штампа — белые с чёрным контуром. Фон за строкой бывает любым (небо, деревья,
металлоконструкции), поэтому сравниваются не яркости, а то, что от фона не зависит:
тёмный контур и светлая заливка. Порог берётся на родном разрешении и только потом
ячейка уменьшается: тонкий контур (1–2 px) при уменьшении размылся бы.
"""

import numpy as np
from PIL import Image, ImageFilter

from stamp.layout import Profile

DARK = 100
BRIGHT = 160
# Контур — тёмное рядом со светлой заливкой, заливка — светлое рядом с контуром:
# так на любом фоне остаётся только кольцо вокруг знака, а фон вдали от знака — 0
RING = 2


def _dilate(mask: np.ndarray, r: int) -> np.ndarray:
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(mask, dy, 0), dx, 1)
    return out


def ternary(band: np.ndarray) -> np.ndarray:
    dark = band < DARK
    bright = band > BRIGHT
    outline = dark & _dilate(bright, RING)
    fill = bright & _dilate(dark, RING)
    return np.where(outline, -1.0, np.where(fill, 1.0, 0.0)).astype(np.float32)


LOCAL_BLUR = 6  # радиус размытия окружения, px
LOCAL_SCALE = 40.0  # разница яркости, которая уже считается полным контрастом


def local_contrast(band: np.ndarray) -> np.ndarray:
    """Насколько пиксель светлее (+) или темнее (−) своего окружения, в пределах [−1, 1]:
    жирная белая цифра светлее любого фона, её контур темнее."""
    blur = np.asarray(
        Image.fromarray(np.clip(band, 0, 255).astype(np.uint8)).filter(
            ImageFilter.GaussianBlur(LOCAL_BLUR)
        ),
        dtype=np.float32,
    )
    return np.clip((band - blur) / LOCAL_SCALE, -1.0, 1.0).astype(np.float32)


def cell_maps(gray: np.ndarray, profile: Profile, dx: float = 0.0) -> list[np.ndarray]:
    """19 нормированных карт ячеек строки штампа. gray — кадр в оттенках серого."""
    raw = gray[profile.y0 : profile.y1, :].astype(np.float32)
    band = ternary(raw) if profile.feature == "ring" else local_contrast(raw)
    xs = profile.edges(dx)
    out = []
    for i in range(len(xs) - 1):
        a, b = int(round(xs[i])), int(round(xs[i + 1]))
        cell = band[:, max(a, 0) : max(b, a + 1)]
        out.append(
            np.asarray(Image.fromarray(cell).resize(profile.cell, Image.Resampling.BOX), dtype=np.float32)
        )
    return out


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Косинус двух карт: 1 — одинаковые, около 0 — ничего общего."""
    den = float(np.linalg.norm(a) * np.linalg.norm(b))
    return float((a * b).sum() / den) if den else 0.0
