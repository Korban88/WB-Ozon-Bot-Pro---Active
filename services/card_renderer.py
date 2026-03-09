"""
Text overlay renderer using Pillow.

overlay_text_on_image(): adds a professional text panel onto any image.
render_card_pillow():     full Pillow-only card (no AI) for fallback / offline mode.
"""

import io
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont

# Font search paths: Ubuntu → Windows dev fallback
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
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


def _contrasting(rgb: tuple) -> tuple:
    return (255, 255, 255) if _luminance(rgb) < 145 else (12, 12, 12)


def _darken(rgb: tuple, factor: float = 0.55) -> tuple:
    return tuple(max(0, int(c * factor)) for c in rgb)


def _shadow_text(draw, xy, text, fill, font, shadow_color, offset=2):
    """Draw text with drop shadow."""
    draw.text((xy[0] + offset, xy[1] + offset), text, fill=shadow_color, font=font)
    draw.text(xy, text, fill=fill, font=font)


def _clean_feat(feat: str) -> str:
    return re.sub(r'^[✅•▸✓➤→✦\-\s]+', '', feat).strip()


# ─────────────────────────────────────────────────────────────────────────────
def overlay_text_on_image(
    base_bytes: bytes,
    title:      str,
    features:   list[str],
    colors_str: str,
) -> bytes:
    """
    Add a professional text panel onto a composed background+product image.

    Layout (bottom 38%):
      [accent stripe 5px]
      [Title — bold, up to 2 lines]
      [thin accent rule]
      [✦ Feature 1]
      [✦ Feature 2]
      [✦ Feature 3]

    Returns PNG bytes.
    """
    parsed       = _parse_colors(colors_str)
    panel_color  = parsed[1] if len(parsed) > 1 else (20, 20, 40)
    accent_color = parsed[2] if len(parsed) > 2 else (220, 160, 40)
    text_color   = _contrasting(panel_color)
    shadow_color = _darken(panel_color, 0.4) if _luminance(panel_color) > 60 else (0, 0, 0)

    base = Image.open(io.BytesIO(base_bytes)).convert("RGBA")
    w, h = base.size

    panel_h = int(h * 0.38)
    panel_y = h - panel_h

    # ── Semi-transparent panel ───────────────────────────────────────────────
    overlay    = Image.new("RGBA", base.size, (0, 0, 0, 0))
    panel_draw = ImageDraw.Draw(overlay)

    # Slightly lighter top strip → full panel color below (faux gradient)
    r, g, b = panel_color
    lighter = (min(r + 35, 255), min(g + 35, 255), min(b + 35, 255))
    panel_draw.rectangle([0, panel_y,     w, panel_y + 8], fill=(*lighter,     200))
    panel_draw.rectangle([0, panel_y + 8, w, h],           fill=(*panel_color, 228))

    base = Image.alpha_composite(base, overlay).convert("RGB")
    draw = ImageDraw.Draw(base)

    # ── Accent top stripe ────────────────────────────────────────────────────
    draw.rectangle([0, panel_y, w, panel_y + 5], fill=accent_color)

    # ── Fonts (scale to image size) ──────────────────────────────────────────
    scale      = w / 1000
    f_title    = _load_font(_BOLD_FONTS, int(36 * scale))
    f_feat     = _load_font(_REG_FONTS,  int(23 * scale))
    f_bullet   = _load_font(_BOLD_FONTS, int(23 * scale))

    pad   = int(36 * scale)
    y     = panel_y + int(18 * scale)

    # ── Title (≤ 2 lines) ─────────────────────────────────────────────────────
    for line in textwrap.wrap(title.strip()[:80], width=30)[:2]:
        _shadow_text(draw, (pad, y), line,
                     fill=text_color, font=f_title, shadow_color=shadow_color,
                     offset=int(2 * scale))
        y += int(47 * scale)

    y += int(8 * scale)

    # ── Thin accent rule ─────────────────────────────────────────────────────
    draw.rectangle([pad, y, w - pad, y + 2], fill=accent_color)
    y += int(13 * scale)

    # ── Features ─────────────────────────────────────────────────────────────
    for feat in features[:3]:
        clean = _clean_feat(feat)[:60]
        if not clean:
            continue
        _shadow_text(draw, (pad, y), "✦",
                     fill=accent_color, font=f_bullet, shadow_color=shadow_color, offset=1)
        _shadow_text(draw, (pad + int(30 * scale), y), clean,
                     fill=text_color, font=f_feat, shadow_color=shadow_color, offset=1)
        y += int(38 * scale)

    buf = io.BytesIO()
    base.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────────────
def render_card_pillow(
    background_bytes: bytes,
    product_bytes:    bytes,
    title:            str,
    features:         list[str],
    colors_str:       str,
) -> bytes:
    """
    Full Pillow-only card: background + product (white frame) + text overlay.
    Used when card_composer is unavailable (rembg not installed, no OpenAI).
    """
    parsed      = _parse_colors(colors_str)
    bg_color    = parsed[0] if parsed          else (245, 245, 250)
    accent      = parsed[2] if len(parsed) > 2 else (200, 150, 50)

    CARD_W, CARD_H = 1000, 1000
    PHOTO_ZONE_H   = int(CARD_H * 0.62)

    bg  = Image.open(io.BytesIO(background_bytes)).convert("RGB").resize((CARD_W, CARD_H))
    draw = ImageDraw.Draw(bg)

    # Product with white rounded frame
    try:
        MAX_W, MAX_H = int(CARD_W * 0.72), int(PHOTO_ZONE_H * 0.88)
        product = Image.open(io.BytesIO(product_bytes)).convert("RGBA")
        product.thumbnail((MAX_W, MAX_H), Image.LANCZOS)

        px = (CARD_W - product.width)  // 2
        py = max(20, (PHOTO_ZONE_H - product.height) // 2 - 10)

        pad = 14
        draw.rounded_rectangle(
            [px - pad, py - pad, px + product.width + pad, py + product.height + pad],
            radius=10, fill=(255, 255, 255, 230),
        )
        white_bg = Image.new("RGB", product.size, (255, 255, 255))
        white_bg.paste(product, mask=product.split()[3])
        bg.paste(white_bg, (px, py))
    except Exception:
        pass

    buf = io.BytesIO()
    bg.save(buf, "PNG")
    composed = buf.getvalue()

    return overlay_text_on_image(composed, title, features, colors_str)
