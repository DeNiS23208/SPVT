"""Сжатие загружаемых изображений для быстрой отдачи по сети."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps

MAX_HERO_WIDTH = 1920
HERO_WEBP_QUALITY = 84

MAX_LOGO_WIDTH = 960


def _load_image(data: bytes) -> Image.Image:
    return Image.open(BytesIO(data))


def optimize_hero_bytes(data: bytes) -> bytes:
    """Фон главной: RGB, до 1920px по ширине, WebP."""
    img = _load_image(data)
    img = ImageOps.exif_transpose(img)

    if img.mode in ("RGBA", "P"):
        rgba = img.convert("RGBA")
        bg = Image.new("RGB", rgba.size, (11, 18, 32))
        bg.paste(rgba, mask=rgba.split()[3])
        img = bg
    else:
        img = img.convert("RGB")

    w, h = img.size
    if w > MAX_HERO_WIDTH:
        new_h = int(h * (MAX_HERO_WIDTH / w))
        img = img.resize((MAX_HERO_WIDTH, new_h), Image.Resampling.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="WEBP", quality=HERO_WEBP_QUALITY, method=6)
    return buf.getvalue()


def optimize_logo_bytes(data: bytes) -> bytes:
    """Логотип: PNG с альфой (маска в CSS), до 960px — совместимость с mask-image."""
    img = _load_image(data)
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGBA")

    w, h = img.size
    if w > MAX_LOGO_WIDTH:
        new_h = int(h * (MAX_LOGO_WIDTH / w))
        img = img.resize((MAX_LOGO_WIDTH, new_h), Image.Resampling.LANCZOS)

    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True, compress_level=9)
    return buf.getvalue()
