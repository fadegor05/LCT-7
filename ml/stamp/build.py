"""Эталоны знаков из подписанных кадров.

    python -m stamp.build labels.csv кадры/ [--out stamp/profiles]

labels.csv — строки `имя_файла,ДД-ММ-ГГГГ ЧЧ:ММ:СС` (имя без расширения или с ним).
Кадры организаторов в git не попадают; в репозиторий идут только эталоны — карты
ячеек 16×24, по которым кадр не восстановить.
"""

import argparse
import csv
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from stamp.features import cell_maps
from stamp.layout import FORMAT, profile_for
from stamp.templates import PROFILES_DIR, Templates


def gray_of(path: Path) -> np.ndarray:
    with Image.open(path) as im:
        return np.asarray(ImageOps.exif_transpose(im).convert("L"), dtype=np.float32)


def add_labeled(store: dict[str, Templates], gray: np.ndarray, text: str) -> bool:
    profile = profile_for(gray.shape[1], gray.shape[0])
    if profile is None or len(text) != len(FORMAT):
        return False
    templates = store.setdefault(profile.name, Templates())
    for ch, cell in zip(text, cell_maps(gray, profile), strict=True):
        if ch != " ":
            templates.add(ch, cell)
    return True


def find(images: Path, name: str) -> Path | None:
    for candidate in (images / name, *(images / f"{name}{ext}" for ext in (".jpg", ".jpeg", ".png"))):
        if candidate.exists():
            return candidate
    return next(images.rglob(f"{name}*"), None)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("labels", type=Path)
    ap.add_argument("images", type=Path)
    ap.add_argument("--out", type=Path, default=PROFILES_DIR)
    args = ap.parse_args()
    store: dict[str, Templates] = {}
    used = 0
    for name, text in csv.reader(args.labels.open(encoding="utf-8")):
        path = find(args.images, name)
        if path is not None and add_labeled(store, gray_of(path), text.strip()):
            used += 1
    args.out.mkdir(parents=True, exist_ok=True)
    for name, templates in store.items():
        templates.save(args.out / f"{name}.npz")
        print(name, templates.counts())
    print("кадров:", used)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
