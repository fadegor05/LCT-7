# -*- coding: utf-8 -*-
"""Наглядник классов: вырезает размеченные объекты и собирает в лист по классам.

Словесные критерии в LABELING_SPEC.md разночтения не снимают: «решётчатая стрела»
и «сплошная мачта» каждый представляет по-своему. Лист с реальными вырезами из
нашей же разметки снимает их за секунду и служит эталоном для второго разметчика.

Побочная польза: на листе сразу видны собственные ошибки разметки — объект,
попавший не в свой класс, бросается в глаза рядом с однородными соседями.
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BACKGROUND = (24, 24, 28)
TEXT = (235, 235, 235)


def parse_attributes(description: str | None) -> dict[str, str]:
    attrs = {}
    for part in (description or "").split(";"):
        key, _, value = part.strip().partition("=")
        if key.strip():
            attrs[key.strip()] = value.strip()
    return attrs


def collect(folders: list[Path], images_dir: Path, key: str) -> dict[str, list[tuple[Path, list]]]:
    """key = 'label' — группировка по классу, 'activity' — по состоянию."""
    groups: dict[str, list[tuple[Path, list]]] = collections.defaultdict(list)
    for folder in folders:
        for path in sorted(folder.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            image = images_dir / data.get("imagePath", f"{path.stem}.png")
            if not image.exists():
                continue
            for shape in data.get("shapes", []):
                attrs = parse_attributes(shape.get("description"))
                name = shape["label"] if key == "label" else attrs.get("activity", "unknown")
                if key == "activity":
                    name = f'{shape["label"]} / {name}'
                groups[name].append((image, shape["points"]))
    return groups


def crop(image_path: Path, points: list, size: int, pad: float = 0.12) -> Image.Image:
    with Image.open(image_path) as im:
        im = im.convert("RGB")
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        box = (max(0, min(xs) - w * pad), max(0, min(ys) - h * pad),
               min(im.width, max(xs) + w * pad), min(im.height, max(ys) + h * pad))
        piece = im.crop(tuple(int(v) for v in box))
    tile = Image.new("RGB", (size, size), BACKGROUND)
    piece.thumbnail((size, size), Image.LANCZOS)
    tile.paste(piece, ((size - piece.width) // 2, (size - piece.height) // 2))
    return tile


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folders", nargs="+", type=Path)
    parser.add_argument("--images", type=Path,
                        default=Path("data/raw/dataset/images/Строительная_техника"))
    parser.add_argument("-o", "--out", type=Path, default=Path("data/reference/guide/classes.png"))
    parser.add_argument("--per-class", type=int, default=4)
    parser.add_argument("--tile", type=int, default=190)
    parser.add_argument("--by", choices=["label", "activity"], default="label")
    args = parser.parse_args()

    groups = collect(args.folders, args.images, args.by)
    groups = {k: v for k, v in sorted(groups.items(), key=lambda kv: -len(kv[1]))}
    if not groups:
        print("нет размеченных объектов")
        return 1

    font = ImageFont.load_default(size=15)
    row_h = args.tile + 26
    width = 150 + args.per_class * (args.tile + 6)
    sheet = Image.new("RGB", (width, row_h * len(groups) + 10), BACKGROUND)
    draw = ImageDraw.Draw(sheet)

    for row, (name, items) in enumerate(groups.items()):
        y = 10 + row * row_h
        draw.text((8, y + args.tile // 2 - 8), f"{name}\n({len(items)})", fill=TEXT, font=font)
        for col, (image_path, points) in enumerate(items[:args.per_class]):
            try:
                sheet.paste(crop(image_path, points, args.tile), (150 + col * (args.tile + 6), y))
            except OSError as exc:
                print(f"пропуск {image_path}: {exc}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(args.out)
    print(f"классов: {len(groups)}, объектов: {sum(len(v) for v in groups.values())}")
    print(f"{args.out}  {sheet.size[0]}x{sheet.size[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
