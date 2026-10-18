"""Синтетические кадры со штампом: белые знаки с чёрным контуром по раскладке профиля.

Кадры организаторов в git не попадают, поэтому тесты чтения штампа рисуют строку
сами — встроенным шрифтом Pillow, на разных фонах: светлое небо, тёмная зелень, шум.
"""

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from stamp.layout import FORMAT, Profile


def background(profile: Profile, kind: str, seed: int = 0) -> Image.Image:
    rng = np.random.default_rng(seed)
    h, w = profile.height, profile.width
    if kind == "sky":
        base = np.linspace(215, 185, h)[:, None] * np.ones((1, w))
    elif kind == "dark":
        base = np.full((h, w), 55.0)
    else:  # «пёстрый»: листва, металлоконструкции — пятна разной яркости с мягкими краями
        coarse = rng.uniform(40, 220, size=(h // 24 + 2, w // 24 + 2))
        base = np.asarray(
            Image.fromarray(coarse.astype(np.float32)).resize((w, h), Image.Resampling.BICUBIC),
            dtype=np.float64,
        )
    noise = rng.normal(0, 6, size=(h, w))
    return Image.fromarray(np.clip(base + noise, 0, 255).astype(np.uint8), "L")


def draw_stamp(image: Image.Image, profile: Profile, text: str) -> Image.Image:
    assert len(text) == len(FORMAT)
    out = image.copy()
    draw = ImageDraw.Draw(out)
    height = profile.y1 - profile.y0
    font = ImageFont.load_default(size=int(height * 0.95))
    xs = profile.edges()
    for ch, a, b in zip(text, xs, xs[1:], strict=False):
        if ch == " ":
            continue
        left, top, right, bottom = draw.textbbox((0, 0), ch, font=font, stroke_width=2)
        x = (a + b) / 2 - (right + left) / 2
        y = profile.y0 + height / 2 - (bottom + top) / 2
        draw.text((x, y), ch, font=font, fill=245, stroke_width=2, stroke_fill=10)
    return out


def frame(profile: Profile, text: str | None, kind: str = "sky", seed: int = 0) -> np.ndarray:
    image = background(profile, kind, seed)
    if text is not None:
        image = draw_stamp(image, profile, text)
    return np.asarray(image, dtype=np.float32)
