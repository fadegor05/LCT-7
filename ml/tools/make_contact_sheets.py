# -*- coding: utf-8 -*-
"""Сборка контактных листов: много снимков сеткой на одной картинке.

Отдельный файл отвечает на вопрос «что на этом кадре», контактный лист — на
вопрос «что общего у этих кадров и чем они отличаются». Именно так находятся
серии одной площадки, сезоны, ракурсы и выбросы в разметке: закономерность
видна только рядом с соседями.

Второй режим — вырез области (--crop). Мелкая деталь вроде штампа даты в углу
кадра нечитаема при просмотре целого снимка, но полсотни вырезов, сведённых
рядом, проверяются глазами за один проход.

Вместе с листами пишется индекс (лист, строка, колонка, файл): по нему видно,
какой плитке какой файл соответствует, и в него же удобно дописывать колонку
разметки — например site_id.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
BACKGROUND = (24, 24, 28)
LABEL_COLOR = (235, 235, 235)


def natural_key(path: Path) -> list:
    """Screenshot_2 перед Screenshot_10: числа сравниваются как числа."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", path.name)]


def collect(source: Path) -> list[Path]:
    if source.is_file():
        names = source.read_text(encoding="utf-8").split()
        return [Path(n) for n in names]
    files = [p for p in source.iterdir() if p.suffix.lower() in EXTENSIONS]
    return sorted(files, key=natural_key)


def parse_crop(value: str) -> tuple[float, float, float, float]:
    parts = [float(v) for v in value.split(",")]
    if len(parts) != 4 or not all(0.0 <= v <= 1.0 for v in parts):
        raise argparse.ArgumentTypeError(
            "--crop ожидает четыре доли в диапазоне 0..1: left,top,right,bottom")
    left, top, right, bottom = parts
    if left >= right or top >= bottom:
        raise argparse.ArgumentTypeError("--crop: left<right и top<bottom")
    return left, top, right, bottom


def make_tile(path: Path, size: tuple[int, int],
              crop: tuple[float, float, float, float] | None) -> Image.Image:
    """Кадр (или его вырез), вписанный в плитку с сохранением пропорций."""
    tile = Image.new("RGB", size, BACKGROUND)
    with Image.open(path) as img:
        img = img.convert("RGB")
        if crop:
            w, h = img.size
            left, top, right, bottom = crop
            img = img.crop((int(w * left), int(h * top),
                            int(w * right), int(h * bottom)))
        img.thumbnail(size, Image.LANCZOS)
        tile.paste(img, ((size[0] - img.width) // 2, (size[1] - img.height) // 2))
    return tile


def draw_label(sheet: Image.Image, text: str, x: int, y: int,
               font: ImageFont.ImageFont) -> None:
    draw = ImageDraw.Draw(sheet)
    draw.text((x, y), text, fill=LABEL_COLOR, font=font)


def build(paths: list[Path], out_dir: Path, cols: int, rows: int,
          tile_w: int, tile_h: int, pad: int,
          crop: tuple[float, float, float, float] | None,
          label: bool) -> list[tuple[int, int, int, Path]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    per_sheet = cols * rows
    label_h = 18 if label else 0
    font = ImageFont.load_default(size=14) if label else None

    index: list[tuple[int, int, int, Path]] = []
    for sheet_no, start in enumerate(range(0, len(paths), per_sheet), start=1):
        chunk = paths[start:start + per_sheet]
        sheet = Image.new(
            "RGB",
            (cols * tile_w + pad * (cols + 1),
             rows * (tile_h + label_h) + pad * (rows + 1)),
            BACKGROUND,
        )
        for position, path in enumerate(chunk):
            row, col = divmod(position, cols)
            x = pad + col * (tile_w + pad)
            y = pad + row * (tile_h + label_h + pad)
            try:
                sheet.paste(make_tile(path, (tile_w, tile_h), crop), (x, y))
            except OSError as exc:            # битый или нечитаемый файл
                print(f"пропуск {path}: {exc}", file=sys.stderr)
                continue
            if label:
                draw_label(sheet, f"{start + position + 1}. {path.stem[:34]}",
                           x, y + tile_h + 2, font)
            index.append((sheet_no, row + 1, col + 1, path))

        target = out_dir / f"sheet_{sheet_no:02d}.png"
        sheet.save(target)
        print(f"{target}  ({len(chunk)} кадров)")
    return index


def write_index(index: list[tuple[int, int, int, Path]], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter=";")
        writer.writerow(["sheet", "row", "col", "image"])
        for sheet_no, row, col, image in index:
            writer.writerow([sheet_no, row, col, image.name])
    print(f"{path}  ({len(index)} строк)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path,
                        help="папка со снимками или текстовый файл со списком путей")
    parser.add_argument("-o", "--out", type=Path, default=Path("contact_sheets"))
    parser.add_argument("--cols", type=int, default=5)
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--tile", type=int, default=380, help="ширина плитки, px")
    parser.add_argument("--aspect", type=float, default=1.5,
                        help="отношение сторон плитки; 1.5 под кадр 3:2")
    parser.add_argument("--pad", type=int, default=4)
    parser.add_argument("--crop", type=parse_crop, default=None,
                        help="вырез в долях кадра: left,top,right,bottom "
                             "(штамп даты — 0.38,0.84,1,1)")
    parser.add_argument("--no-label", action="store_true",
                        help="не подписывать плитки номером и именем файла")
    parser.add_argument("--limit", type=int, default=None,
                        help="взять только первые N кадров")
    parser.add_argument("--index", type=Path, default=None,
                        help="куда записать соответствие плиток и файлов")
    args = parser.parse_args()

    paths = collect(args.source)
    if args.limit:
        paths = paths[:args.limit]
    if not paths:
        print("не найдено ни одного изображения", file=sys.stderr)
        return 1

    index = build(paths, args.out, args.cols, args.rows,
                  args.tile, int(args.tile / args.aspect), args.pad,
                  args.crop, not args.no_label)

    write_index(index, args.index or args.out / "index.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
