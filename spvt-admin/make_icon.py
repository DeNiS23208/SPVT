"""Собрать assets/spvt-admin.ico из логотипа сайта (для иконки .exe и ярлыка Windows).

Кадры — квадратные (прозрачные поля), чтобы в Проводнике и на панели задач не было «сплющенной» картинки.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "assets"
DEFAULT_LOGO = ROOT.parent / "app" / "static" / "images" / "ink-logo.png"


def _square_frame(im: Image.Image, side: int) -> Image.Image:
    """Вписать изображение в квадрат side×side с сохранением пропорций."""
    im = im.convert("RGBA")
    w, h = im.size
    if w <= 0 or h <= 0:
        return Image.new("RGBA", (side, side), (0, 0, 0, 0))
    scale = min(side / w, side / h)
    nw = max(1, int(round(w * scale)))
    nh = max(1, int(round(h * scale)))
    resized = im.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    x = (side - nw) // 2
    y = (side - nh) // 2
    canvas.paste(resized, (x, y), resized)
    return canvas


def main() -> int:
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOGO
    if not src.is_file():
        print(f"Нет файла логотипа: {src}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "spvt-admin.ico"

    img = Image.open(src).convert("RGBA")
    master = _square_frame(img, 256)
    sides = (16, 24, 32, 48, 64, 128, 256)
    master.save(out, format="ICO", sizes=[(s, s) for s in sides])
    print(f"OK: {out} ({len(sides)} размеров)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
