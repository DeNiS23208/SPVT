#!/usr/bin/env python3
"""Заменить в ink-logo.png текст «Иркутская нефтяная компания» на «ИНК-СЕРВИС»."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
LOGO = ROOT / "app" / "static" / "images" / "ink-logo.png"
OUT = ROOT / "app" / "static" / "images" / "ink-logo-inkservice.png"

TEXT_GREEN = (45, 110, 62)
TEXT_BOX = (255, 188, 800, 445)
TEXT_CLEAR_FROM = 282  # не трогаем значок слева
TEXT_GAP = 18  # отступ текста от правого края эмблемы


def _is_logo_green(r: int, g: int, b: int, a: int) -> bool:
    return a > 40 and g > r + 12 and g > 55 and g < 210


def _sample_text_green(img: Image.Image) -> tuple[int, int, int]:
    x1, y1, x2, y2 = TEXT_BOX
    pixels = img.load()
    rs: list[int] = []
    gs: list[int] = []
    bs: list[int] = []
    for y in range(y1, y2):
        for x in range(x1, x2):
            r, g, b, a = pixels[x, y]
            if _is_logo_green(r, g, b, a):
                rs.append(r)
                gs.append(g)
                bs.append(b)
    if not gs:
        return TEXT_GREEN
    n = len(gs)
    return (sum(rs) // n, sum(gs) // n, sum(bs) // n)


def _emblem_right_edge(img: Image.Image, y1: int, y2: int) -> int:
    """Правый край значка (серый контур + зелёный), без зоны текста."""
    pixels = img.load()
    w, _ = img.size
    edge = 0
    for x in range(min(400, w)):
        count = 0
        for y in range(y1, y2):
            if pixels[x, y][3] > 25:
                count += 1
        if count >= 40:
            edge = x
    return edge


def _pick_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        Path(r"C:\Windows\Fonts\arialbd.ttf"),
        Path(r"C:\Windows\Fonts\arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def relabel_logo(src: Path = LOGO, out: Path = LOGO) -> None:
    img = Image.open(src).convert("RGBA")
    w, h = img.size
    x1, y1, x2, y2 = TEXT_BOX
    pixels = img.load()
    fill_green = _sample_text_green(img)

    # Убираем старый текст справа от значка.
    for y in range(max(0, y1), min(h, y2)):
        for x in range(max(TEXT_CLEAR_FROM, x1), min(w, x2)):
            if pixels[x, y][3] > 4:
                pixels[x, y] = (0, 0, 0, 0)

    emblem_right = _emblem_right_edge(img, y1 + 10, y2 - 10)
    text_start = max(TEXT_CLEAR_FROM, emblem_right + TEXT_GAP)

    draw = ImageDraw.Draw(img)
    label = "ИНК-СЕРВИС"
    max_text_width = x2 - text_start - 12
    font_size = 72
    font = _pick_font(font_size)
    while font_size > 40:
        bbox = draw.textbbox((0, 0), label, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        if tw <= max_text_width and th < (y2 - y1 - 36):
            break
        font_size -= 3
        font = _pick_font(font_size)

    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = text_start
    ty = y1 + ((y2 - y1) - th) // 2 - bbox[1]

    draw.text((tx, ty), label, font=font, fill=(*fill_green, 255))

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, format="PNG", optimize=True, compress_level=9)
    print(f"Saved {out} ({img.size[0]}x{img.size[1]})")


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else LOGO
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else OUT
    relabel_logo(src, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
