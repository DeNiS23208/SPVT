#!/usr/bin/env python3
"""Сборка ink-logo.png из оригинала: убрать только чёрный фон, сохранить тёмно-серые элементы."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image

try:
    import numpy as np
except ImportError:
    print("Для скрипта нужен numpy: pip install numpy", file=sys.stderr)
    sys.exit(1)


def remove_black_bg(img: Image.Image, lum_cut: float = 14.0, sat_cut: float = 22.0) -> Image.Image:
    rgba = img.convert("RGBA")
    a = np.array(rgba)
    rgb = a[:, :, :3].astype(np.float32)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    sat = mx - mn
    is_bg = (lum < lum_cut) & (sat < sat_cut)
    alpha = (~is_bg).astype(np.uint8) * 255
    out = np.dstack([a[:, :, 0], a[:, :, 1], a[:, :, 2], alpha])
    return Image.fromarray(out, "RGBA")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="Исходный PNG/JPEG с чёрным фоном")
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=Path("app/static/images/ink-logo.png"),
        help="Куда сохранить",
    )
    parser.add_argument("--max-width", type=int, default=960)
    args = parser.parse_args()

    img = Image.open(args.source)
    img = remove_black_bg(img)
    w, h = img.size
    if w > args.max_width:
        nh = int(h * (args.max_width / w))
        img = img.resize((args.max_width, nh), Image.Resampling.LANCZOS)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    img.save(args.out, format="PNG", optimize=True, compress_level=9)
    print(args.out, img.size, args.out.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
