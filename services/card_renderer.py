"""
Marketplace card mockup renderer using Pillow.

Creates a 1000×1000px product card image:
  - Top 58%: original product photo on concept background color
  - Accent separator line
  - Bottom 42%: title + 3 features in concept colors
"""

import io
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont

CARD_W = 1000
CARD_H = 1000
PHOTO_AREA_H = 580  # top zone height

# Font search paths (Ubuntu server → Windows dev fallback)
_BOLD_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_REG_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "C:/Windows/Fonts/arial.ttf",
]


def _load_font(paths: list[str], size: int) -> ImageFont.ImageFont:
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _parse_colors(colors_str: str) -> list[tuple[int, int, int]]:
    """Extract up to 3 RGB tuples from a hex-color string like '#FFFFFF · #1A237E · #FFD700'."""
    hexes = re.findall(r'#([0-9A-Fa-f]{6})', colors_str)
    return [tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) for h in hexes[:3]]


def _contrasting(rgb: tuple) -> tuple:
    """Return white or near-black depending on background luminance."""
    r, g, b = rgb
    return (255, 255, 255) if (0.299 * r + 0.587 * g + 0.114 * b) < 140 else (20, 20, 20)


def render_card(
    photo_bytes: bytes,
    title: str,
    features: list[str],
    colors_str: str,
) -> bytes:
    """
    Render a marketplace card mockup image (1000×1000 PNG).

    Args:
        photo_bytes: original product photo bytes from Telegram
        title:       product title from the generated card
        features:    list of feature strings (first 3 used)
        colors_str:  color palette string, e.g. "Белый #FFFFFF · Тёмно-синий #1A237E · Золотой #FFD700"

    Returns:
        PNG image as bytes
    """
    parsed = _parse_colors(colors_str)
    bg_color    = parsed[0] if len(parsed) > 0 else (255, 255, 255)
    title_color = parsed[1] if len(parsed) > 1 else _contrasting(bg_color)
    accent      = parsed[2] if len(parsed) > 2 else (255, 165, 0)
    body_fg     = _contrasting(bg_color)

    img  = Image.new("RGB", (CARD_W, CARD_H), bg_color)
    draw = ImageDraw.Draw(img)

    # ── Product photo ────────────────────────────────────────────────────────
    max_w = CARD_W - 80
    max_h = PHOTO_AREA_H - 60
    try:
        product = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
        product.thumbnail((max_w, max_h), Image.LANCZOS)

        px = (CARD_W - product.width) // 2
        py = 30 + (max_h - product.height) // 2

        # White shadow frame behind product
        pad = 10
        draw.rectangle(
            [px - pad, py - pad, px + product.width + pad, py + product.height + pad],
            fill=(255, 255, 255),
        )

        # Composite RGBA product onto card
        white_bg = Image.new("RGB", product.size, (255, 255, 255))
        white_bg.paste(product, mask=product.split()[3])
        img.paste(white_bg, (px, py))
    except Exception:
        # Fallback: placeholder text
        draw.text((CARD_W // 2 - 70, PHOTO_AREA_H // 2 - 15), "[ фото товара ]", fill=body_fg)

    # ── Accent separator ────────────────────────────────────────────────────
    draw.rectangle([0, PHOTO_AREA_H, CARD_W, PHOTO_AREA_H + 6], fill=accent)

    # ── Text area ────────────────────────────────────────────────────────────
    font_title = _load_font(_BOLD_FONTS, 32)
    font_feat  = _load_font(_REG_FONTS,  22)

    y = PHOTO_AREA_H + 22

    # Title (up to 2 wrapped lines)
    title_clean = title.strip()[:90]
    for line in textwrap.wrap(title_clean, width=30)[:2]:
        draw.text((30, y), line, fill=title_color, font=font_title)
        y += 44

    y += 10

    # Features (up to 3)
    for feat in features[:3]:
        clean = re.sub(r'^[✅•▸✓➤→\-\s]+', '', feat).strip()[:65]
        draw.text((30, y), f"✓  {clean}", fill=accent, font=font_feat)
        y += 36

    # ── Output ───────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
