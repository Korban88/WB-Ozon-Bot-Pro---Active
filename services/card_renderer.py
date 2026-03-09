"""
Marketplace card renderer using Pillow.

Two modes:
  1. render_card()           — full card from scratch (Pillow only, fallback)
  2. overlay_text_on_image() — add text panel onto an AI-generated image
                               (used after gpt-image-1 visual generation)
"""

import io
import re
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

CARD_W = 1000
CARD_H = 1000
PHOTO_AREA_H = 580

# Font search paths: Ubuntu server first, Windows dev fallback
_BOLD_FONTS = [
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
_REG_FONTS = [
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-R.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
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
    hexes = re.findall(r'#([0-9A-Fa-f]{6})', colors_str)
    return [tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) for h in hexes[:3]]


def _luminance(rgb: tuple) -> float:
    r, g, b = rgb
    return 0.299 * r + 0.587 * g + 0.114 * b


def _contrasting(rgb: tuple) -> tuple:
    return (255, 255, 255) if _luminance(rgb) < 140 else (15, 15, 15)


def _darken(rgb: tuple, factor: float = 0.55) -> tuple:
    return tuple(max(0, int(c * factor)) for c in rgb)


def _text_shadow(draw: ImageDraw.ImageDraw, pos: tuple, text: str,
                 fill: tuple, shadow: tuple, font: ImageFont.ImageFont,
                 offset: int = 2) -> None:
    """Draw text with a subtle drop shadow."""
    draw.text((pos[0] + offset, pos[1] + offset), text, fill=shadow, font=font)
    draw.text(pos, text, fill=fill, font=font)


def _clean_feature(feat: str) -> str:
    return re.sub(r'^[✅•▸✓➤→\-\s]+', '', feat).strip()


# ── Mode 1: overlay text on an AI-generated image ─────────────────────────────
def overlay_text_on_image(
    base_bytes: bytes,
    title: str,
    features: list[str],
    colors_str: str,
) -> bytes:
    """
    Add a professional text panel onto an AI-generated background image.

    Layout: semi-transparent panel in the bottom ~38% of the image.
    Title + accent line + 3 feature bullets with drop shadows.

    Returns PNG bytes.
    """
    parsed       = _parse_colors(colors_str)
    panel_color  = parsed[1] if len(parsed) > 1 else (20, 20, 40)
    accent_color = parsed[2] if len(parsed) > 2 else (255, 165, 0)
    text_color   = _contrasting(panel_color)
    shadow_color = _darken(panel_color, 0.3) if _luminance(panel_color) > 80 else (0, 0, 0)

    base = Image.open(io.BytesIO(base_bytes)).convert("RGBA")
    w, h = base.size

    panel_h = int(h * 0.38)
    panel_y = h - panel_h

    # ── Semi-transparent panel ───────────────────────────────────────────────
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(overlay)

    # Gradient-like effect: slightly lighter strip at top of panel, full color below
    strip_h = 6
    r, g, b = panel_color
    panel_draw.rectangle([0, panel_y, w, panel_y + strip_h],
                         fill=(min(r + 40, 255), min(g + 40, 255), min(b + 40, 255), 200))
    panel_draw.rectangle([0, panel_y + strip_h, w, h], fill=(*panel_color, 225))

    base = Image.alpha_composite(base, overlay).convert("RGB")
    draw = ImageDraw.Draw(base)

    # ── Accent line ──────────────────────────────────────────────────────────
    draw.rectangle([0, panel_y, w, panel_y + 5], fill=accent_color)

    # ── Fonts ────────────────────────────────────────────────────────────────
    # Scale font sizes to actual image dimensions
    scale = w / 1000
    font_title  = _load_font(_BOLD_FONTS, int(38 * scale))
    font_feat   = _load_font(_REG_FONTS,  int(24 * scale))
    font_bullet = _load_font(_BOLD_FONTS, int(24 * scale))

    pad_x = int(36 * scale)
    y = panel_y + int(20 * scale)

    # ── Title (up to 2 lines) ────────────────────────────────────────────────
    title_clean = title.strip()[:80]
    title_lines = textwrap.wrap(title_clean, width=30)[:2]
    for line in title_lines:
        _text_shadow(draw, (pad_x, y), line, fill=text_color,
                     shadow=shadow_color, font=font_title, offset=int(2 * scale))
        y += int(48 * scale)

    y += int(10 * scale)

    # Thin accent rule
    draw.rectangle([pad_x, y, w - pad_x, y + 2], fill=accent_color)
    y += int(14 * scale)

    # ── Features ─────────────────────────────────────────────────────────────
    for feat in features[:3]:
        clean = _clean_feature(feat)[:58]
        if not clean:
            continue
        # Bullet in accent
        _text_shadow(draw, (pad_x, y), "✦", fill=accent_color,
                     shadow=shadow_color, font=font_bullet, offset=1)
        _text_shadow(draw, (pad_x + int(30 * scale), y), clean, fill=text_color,
                     shadow=shadow_color, font=font_feat, offset=1)
        y += int(38 * scale)

    buf = io.BytesIO()
    base.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Mode 2: full Pillow-only card (no AI) ─────────────────────────────────────
def render_card(
    photo_bytes: bytes,
    title: str,
    features: list[str],
    colors_str: str,
) -> bytes:
    """
    Render a full card using only Pillow (fallback when OpenAI is unavailable).
    Layout: product photo top 58%, text panel bottom 42%.
    """
    parsed      = _parse_colors(colors_str)
    bg_color    = parsed[0] if parsed else (255, 255, 255)
    panel_color = parsed[1] if len(parsed) > 1 else _darken(bg_color, 0.7)
    accent      = parsed[2] if len(parsed) > 2 else (255, 165, 0)
    text_color  = _contrasting(panel_color)
    shadow_color = _darken(panel_color, 0.5)

    img  = Image.new("RGB", (CARD_W, CARD_H), bg_color)
    draw = ImageDraw.Draw(img)

    # ── Product photo ─────────────────────────────────────────────────────────
    max_w = CARD_W - 80
    max_h = PHOTO_AREA_H - 60
    try:
        product = Image.open(io.BytesIO(photo_bytes)).convert("RGBA")
        product.thumbnail((max_w, max_h), Image.LANCZOS)
        px = (CARD_W - product.width) // 2
        py = 30 + (max_h - product.height) // 2
        pad = 12
        draw.rounded_rectangle(
            [px - pad, py - pad, px + product.width + pad, py + product.height + pad],
            radius=8, fill=(255, 255, 255),
        )
        white_bg = Image.new("RGB", product.size, (255, 255, 255))
        white_bg.paste(product, mask=product.split()[3])
        img.paste(white_bg, (px, py))
    except Exception:
        pass

    # ── Text panel ────────────────────────────────────────────────────────────
    draw.rectangle([0, PHOTO_AREA_H, CARD_W, CARD_H], fill=panel_color)
    draw.rectangle([0, PHOTO_AREA_H, CARD_W, PHOTO_AREA_H + 5], fill=accent)

    font_title = _load_font(_BOLD_FONTS, 36)
    font_feat  = _load_font(_REG_FONTS,  23)

    y = PHOTO_AREA_H + 22
    for line in textwrap.wrap(title.strip()[:80], width=30)[:2]:
        _text_shadow(draw, (30, y), line, fill=text_color,
                     shadow=shadow_color, font=font_title)
        y += 48

    y += 8
    draw.rectangle([30, y, CARD_W - 30, y + 2], fill=accent)
    y += 14

    for feat in features[:3]:
        clean = _clean_feature(feat)[:58]
        if not clean:
            continue
        _text_shadow(draw, (30, y), "✦", fill=accent, shadow=shadow_color, font=font_feat)
        _text_shadow(draw, (60, y), clean, fill=text_color, shadow=shadow_color, font=font_feat)
        y += 38

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
