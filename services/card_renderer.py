"""
Card renderer: text overlay and Pillow-only fallback.

overlay_text_premium():
    Adds a gradient fade + clean text to an AI-generated scene.
    NO heavy panel, NO frames, NO accent stripes — just typography on a gradient.

render_card_pillow():
    Full Pillow card for offline/no-API mode.
"""

import io
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont

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


def _load_font(paths, size):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _parse_colors(s):
    hexes = re.findall(r'#([0-9A-Fa-f]{6})', s)
    return [tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) for h in hexes[:3]]


def _lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _contrast(c):
    return (255, 255, 255) if _lum(c) < 145 else (10, 10, 10)


def _clean(feat):
    return re.sub(r'^[✅•▸✓➤→✦\-\s]+', '', feat).strip()


def _draw_text_shadow(draw, xy, text, fill, font, shadow_opacity=130, offset=2):
    """Draw text with a soft shadow for readability on any background."""
    # Shadow: black with low opacity
    shadow_fill = (0, 0, 0)
    # We can't use alpha on RGB image directly, so draw shadow color
    # For dark text on light bg, skip shadow; for light text on dark bg, use shadow
    if fill[0] > 180:  # light text → draw dark shadow
        draw.text((xy[0] + offset, xy[1] + offset), text, fill=(0, 0, 0), font=font)
        draw.text((xy[0] + offset, xy[1]), text, fill=(0, 0, 0), font=font)
    else:              # dark text → very subtle light shadow
        draw.text((xy[0] + 1, xy[1] + 1), text,
                  fill=(255, 255, 255), font=font)
    draw.text(xy, text, fill=fill, font=font)


# ─────────────────────────────────────────────────────────────────────────────
def overlay_text_premium(
    base_bytes: bytes,
    title:      str,
    features:   list[str],
    colors_str: str,
) -> bytes:
    """
    Elegant text overlay — no heavy panel, no frames, no accent stripes.

    Design:
    • Gradient fade at the bottom 26% (smooth, no hard edge)
    • Title: bold, large, with text shadow
    • 3 feature lines: clean, regular, minimal bullets
    • Accent color used ONLY for feature bullets — not for background elements
    """
    parsed       = _parse_colors(colors_str)
    fade_color   = parsed[1] if len(parsed) > 1 else (15, 15, 25)
    accent_color = parsed[2] if len(parsed) > 2 else (210, 160, 40)
    text_color   = _contrast(fade_color)

    base = Image.open(io.BytesIO(base_bytes)).convert("RGBA")
    w, h = base.size

    # ── Gradient fade (bottom 26%) ────────────────────────────────────────────
    fade_h    = int(h * 0.26)
    fade_y    = h - fade_h
    overlay   = Image.new("RGBA", base.size, (0, 0, 0, 0))
    fade_draw = ImageDraw.Draw(overlay)

    r, g, b = fade_color
    for dy in range(fade_h):
        # Ease-in curve: slow start, fast end → more natural fade
        t     = dy / fade_h
        alpha = int((t ** 1.6) * 215)
        fade_draw.line([(0, fade_y + dy), (w, fade_y + dy)], fill=(r, g, b, alpha))

    base = Image.alpha_composite(base, overlay).convert("RGB")
    draw = ImageDraw.Draw(base)

    # ── Fonts ──────────────────────────────────────────────────────────────────
    scale  = w / 1000
    f_h1   = _load_font(_BOLD_FONTS, int(40 * scale))   # title
    f_feat = _load_font(_REG_FONTS,  int(22 * scale))   # features
    f_dot  = _load_font(_BOLD_FONTS, int(22 * scale))   # bullet

    pad = int(38 * scale)
    y   = fade_y + int(14 * scale)

    # ── Title ──────────────────────────────────────────────────────────────────
    title_clean = title.strip()[:80]
    lines = textwrap.wrap(title_clean, width=28)[:2]
    for line in lines:
        _draw_text_shadow(draw, (pad, y), line, fill=text_color, font=f_h1)
        y += int(50 * scale)

    y += int(6 * scale)

    # ── Features ──────────────────────────────────────────────────────────────
    # Slightly transparent version of text_color for features
    feat_color = (
        min(text_color[0] + 30, 255),
        min(text_color[1] + 30, 255),
        min(text_color[2] + 30, 255),
    ) if text_color == (10, 10, 10) else (
        max(text_color[0] - 30, 0),
        max(text_color[1] - 30, 0),
        max(text_color[2] - 30, 0),
    )

    for feat in features[:3]:
        clean = _clean(feat)[:60]
        if not clean:
            continue
        # Accent bullet
        _draw_text_shadow(draw, (pad, y), "•", fill=accent_color, font=f_dot)
        _draw_text_shadow(draw, (pad + int(22 * scale), y), clean,
                          fill=feat_color, font=f_feat)
        y += int(34 * scale)

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
    Pillow-only fallback card: background + product (clean frame) + gradient text.
    Used when OpenAI API is not available.
    """
    parsed      = _parse_colors(colors_str)
    accent      = parsed[2] if len(parsed) > 2 else (200, 150, 50)

    W, H = 1000, 1000
    ZONE = int(H * 0.72)  # product occupies top 72%

    bg   = Image.open(io.BytesIO(background_bytes)).convert("RGB").resize((W, H))
    draw = ImageDraw.Draw(bg)

    # Product with minimal soft frame (not the old heavy white rectangle)
    try:
        MAX_W, MAX_H = int(W * 0.70), int(ZONE * 0.85)
        prod = Image.open(io.BytesIO(product_bytes)).convert("RGBA")
        prod.thumbnail((MAX_W, MAX_H), Image.LANCZOS)

        px = (W - prod.width)  // 2
        py = max(20, (ZONE - prod.height) // 2 - 20)

        # Subtle soft shadow only — no white rectangle
        shadow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow_layer)
        s_draw.ellipse(
            [px + 20, py + prod.height - 20,
             px + prod.width - 20, py + prod.height + 30],
            fill=(0, 0, 0, 60)
        )
        from PIL import ImageFilter
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(18))
        bg_rgba = bg.convert("RGBA")
        bg_rgba = Image.alpha_composite(bg_rgba, shadow_layer)
        bg = bg_rgba.convert("RGB")

        # Paste product directly on background (no white frame)
        white_bg = Image.new("RGB", prod.size, (255, 255, 255))
        white_bg.paste(prod, mask=prod.split()[3])
        bg.paste(white_bg, (px, py))
    except Exception:
        pass

    buf = io.BytesIO()
    bg.save(buf, "PNG")
    return overlay_text_premium(buf.getvalue(), title, features, colors_str)
