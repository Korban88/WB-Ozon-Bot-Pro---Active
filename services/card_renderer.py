"""
Card renderer: concept-specific text overlay and Pillow-only fallback.

overlay_text_concept():
    5 typographic treatments — one per concept style:
    1 Luxury Dark   — tracked uppercase, em-dash features, gold accent
    2 Editorial     — oversized title, minimal features, asymmetric
    3 Lifestyle     — clean balanced, 3 features, warm
    4 Natural       — lighter gradient, regular weight, organic feel
    5 Minimal Pure  — very light gradient, small tracked type

render_card_pillow():
    Full Pillow card for offline/no-API fallback.
"""

import io
import re
import textwrap

from PIL import Image, ImageDraw

from services.fonts import get_font


def _parse_colors(s: str) -> list:
    hexes = re.findall(r'#([0-9A-Fa-f]{6})', s)
    result = [tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) for h in hexes[:3]]
    while len(result) < 3:
        result.append((80, 80, 80))
    return result


def _lum(c: tuple) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _fade_color(parsed: list) -> tuple:
    return sorted(parsed, key=_lum)[0]


def _text_on(bg: tuple) -> tuple:
    return (255, 255, 255) if _lum(bg) < 140 else (15, 15, 20)


def _clean(feat: str) -> str:
    return re.sub(r'^[✅•▸✓➤→✦\-\s]+', '', feat).strip()


def _shadow(draw, xy, text, font, fill):
    x, y = xy
    if fill[0] > 180:
        for dx, dy in ((2, 2), (1, 2), (2, 1)):
            draw.text((x + dx, y + dy), text, fill=(0, 0, 0), font=font)
    else:
        draw.text((x + 1, y + 1), text, fill=(255, 255, 255), font=font)
    draw.text(xy, text, fill=fill, font=font)


def _gradient_fade(base: Image.Image, fade_y: int, color: tuple,
                   max_alpha: int, exponent: float = 1.5) -> Image.Image:
    """Draw ease-in gradient fade from fade_y to bottom of image."""
    w, h    = base.size
    fade_h  = h - fade_y
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    d       = ImageDraw.Draw(overlay)
    r, g, b = color
    for dy in range(fade_h):
        t     = dy / fade_h
        alpha = int((t ** exponent) * max_alpha)
        d.line([(0, fade_y + dy), (w, fade_y + dy)], fill=(r, g, b, alpha))
    return Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")


def _track(text: str, spacing: int = 1) -> str:
    """Simulate letter-tracking: add spaces between every character."""
    return (" " * spacing).join(text.upper())


# ─────────────────────────────────────────────────────────────────────────────
#  1. LUXURY DARK
#     Tracked uppercase title. Em-dash prefix on features (no bullets).
#     Wide letter-spacing = expensive feel.
# ─────────────────────────────────────────────────────────────────────────────

def _overlay_luxury(draw, canvas, w, h, title, features, parsed, scale):
    fade_col = _fade_color(parsed)
    accent   = parsed[2]
    txt_col  = _text_on(fade_col)

    f_title = get_font("Bold",    int(34 * scale))
    f_feat  = get_font("Light",   int(20 * scale))

    pad = int(44 * scale)
    y   = int(h * 0.71) + int(20 * scale)

    # Title — tracked uppercase (feels luxurious)
    raw = title.strip().upper()[:50]
    tracked = _track(raw, 1) if len(raw) <= 18 else raw
    lines = textwrap.wrap(tracked, width=32)[:2]
    for line in lines:
        _shadow(draw, (pad, y), line, f_title, txt_col)
        y += int(44 * scale)

    y += int(14 * scale)

    # Thin separator line
    ar, ag, ab = accent
    draw.line([(pad, y), (w - pad, y)], fill=(ar, ag, ab), width=1)
    y += int(14 * scale)

    # Features — em-dash prefix, Light weight
    feat_col = tuple(max(c - 30, 0) for c in txt_col) if txt_col[0] > 180 \
               else tuple(min(c + 30, 255) for c in txt_col)
    for feat in features[:3]:
        clean = _clean(feat)[:55]
        if not clean:
            continue
        _shadow(draw, (pad, y), "—", f_feat, (ar, ag, ab))
        _shadow(draw, (pad + int(24 * scale), y), clean, f_feat, feat_col)
        y += int(30 * scale)


# ─────────────────────────────────────────────────────────────────────────────
#  2. EDITORIAL BOLD
#     Oversized single title line. Minimal features. Left-offset.
#     Asymmetric — text block hugs lower-left.
# ─────────────────────────────────────────────────────────────────────────────

def _overlay_editorial(draw, canvas, w, h, title, features, parsed, scale):
    fade_col = _fade_color(parsed)
    accent   = parsed[2]
    txt_col  = _text_on(fade_col)

    f_title = get_font("Bold",    int(50 * scale))   # deliberately large
    f_feat  = get_font("Regular", int(19 * scale))

    pad = int(38 * scale)
    y   = int(h * 0.70) + int(12 * scale)

    # Very large single title line (crop aggressively — editorial doesn't wrap softly)
    raw   = title.strip()[:35]
    lines = textwrap.wrap(raw, width=20)[:1]  # only 1 line for editorial impact
    for line in lines:
        _shadow(draw, (pad, y), line, f_title, txt_col)
        y += int(62 * scale)

    y += int(6 * scale)

    # 2 features max, no bullets, smaller, slightly offset right
    feat_col = tuple(max(c - 20, 0) for c in txt_col) if txt_col[0] > 180 \
               else tuple(min(c + 20, 255) for c in txt_col)
    ar, ag, ab = accent
    offset = int(14 * scale)
    for feat in features[:2]:
        clean = _clean(feat)[:50]
        if not clean:
            continue
        draw.line([(pad + offset, y + int(10 * scale)),
                   (pad + offset, y + int(28 * scale))],
                  fill=(ar, ag, ab), width=2)
        _shadow(draw, (pad + offset + int(12 * scale), y), clean, f_feat, feat_col)
        y += int(32 * scale)


# ─────────────────────────────────────────────────────────────────────────────
#  3. LIFESTYLE HERO
#     Clean, balanced, confident. Standard 3-feature bullets.
#     Warm and approachable.
# ─────────────────────────────────────────────────────────────────────────────

def _overlay_lifestyle(draw, canvas, w, h, title, features, parsed, scale):
    fade_col = _fade_color(parsed)
    accent   = parsed[2]
    txt_col  = _text_on(fade_col)

    f_title = get_font("Bold",    int(42 * scale))
    f_feat  = get_font("Regular", int(23 * scale))
    f_dot   = get_font("SemiBold", int(23 * scale))

    pad = int(40 * scale)
    y   = int(h * 0.72) + int(16 * scale)

    for line in textwrap.wrap(title.strip()[:80], width=26)[:2]:
        _shadow(draw, (pad, y), line, f_title, txt_col)
        y += int(52 * scale)

    y += int(8 * scale)

    feat_col = tuple(max(c - 22, 0) for c in txt_col) if txt_col[0] > 180 \
               else tuple(min(c + 22, 255) for c in txt_col)
    for feat in features[:3]:
        clean = _clean(feat)[:55]
        if not clean:
            continue
        _shadow(draw, (pad, y + 1), "•", f_dot, accent)
        _shadow(draw, (pad + int(28 * scale), y), clean, f_feat, feat_col)
        y += int(36 * scale)


# ─────────────────────────────────────────────────────────────────────────────
#  4. NATURAL ARTISAN
#     Lighter gradient, Regular weight (not Bold) for warmth.
#     Features with a soft dash, more relaxed spacing.
# ─────────────────────────────────────────────────────────────────────────────

def _overlay_natural(draw, canvas, w, h, title, features, parsed, scale):
    fade_col = _fade_color(parsed)
    accent   = parsed[2]
    txt_col  = _text_on(fade_col)

    f_title = get_font("SemiBold", int(38 * scale))
    f_feat  = get_font("Regular",  int(21 * scale))

    pad = int(40 * scale)
    y   = int(h * 0.73) + int(14 * scale)

    for line in textwrap.wrap(title.strip()[:80], width=28)[:2]:
        _shadow(draw, (pad, y), line, f_title, txt_col)
        y += int(48 * scale)

    y += int(10 * scale)

    feat_col = tuple(max(c - 20, 0) for c in txt_col) if txt_col[0] > 180 \
               else tuple(min(c + 20, 255) for c in txt_col)
    ar, ag, ab = accent
    for feat in features[:3]:
        clean = _clean(feat)[:55]
        if not clean:
            continue
        _shadow(draw, (pad, y), "·", f_feat, (ar, ag, ab))
        _shadow(draw, (pad + int(18 * scale), y), clean, f_feat, feat_col)
        y += int(33 * scale)


# ─────────────────────────────────────────────────────────────────────────────
#  5. MINIMAL PURE
#     Very light gradient (barely there). Small tracked title.
#     Almost nothing — maximum restraint.
# ─────────────────────────────────────────────────────────────────────────────

def _overlay_minimal(draw, canvas, w, h, title, features, parsed, scale):
    fade_col = _fade_color(parsed)
    accent   = parsed[2]
    txt_col  = _text_on(fade_col)

    f_title = get_font("SemiBold", int(28 * scale))   # deliberately small
    f_feat  = get_font("Light",    int(18 * scale))

    pad = int(44 * scale)
    y   = int(h * 0.77) + int(12 * scale)

    raw     = title.strip()[:40]
    tracked = _track(raw, 1) if len(raw) <= 15 else raw.upper()
    for line in textwrap.wrap(tracked, width=30)[:2]:
        _shadow(draw, (pad, y), line, f_title, txt_col)
        y += int(36 * scale)

    y += int(6 * scale)

    feat_col = tuple(max(c - 35, 0) for c in txt_col) if txt_col[0] > 180 \
               else tuple(min(c + 35, 255) for c in txt_col)
    for feat in features[:2]:
        clean = _clean(feat)[:50]
        if not clean:
            continue
        _shadow(draw, (pad, y), "—", f_feat, feat_col)
        _shadow(draw, (pad + int(20 * scale), y), clean, f_feat, feat_col)
        y += int(28 * scale)


# ─── Concept index → overlay params ──────────────────────────────────────────

_STYLES = {
    1: (_overlay_luxury,     0.71, 220, 1.7),   # fade_start, max_alpha, exponent
    2: (_overlay_editorial,  0.70, 215, 1.6),
    3: (_overlay_lifestyle,  0.72, 225, 1.5),
    4: (_overlay_natural,    0.73, 190, 1.4),
    5: (_overlay_minimal,    0.76, 155, 1.3),
}


def overlay_text_concept(
    base_bytes:    bytes,
    title:         str,
    features:      list[str],
    colors_str:    str,
    concept_index: int = 1,
) -> bytes:
    """
    Apply concept-specific text treatment to a card image.
    concept_index 1-5 selects the typographic style.
    """
    parsed = _parse_colors(colors_str)
    style  = (concept_index - 1) % 5 + 1
    fn, fade_ratio, max_alpha, exponent = _STYLES[style]

    base = Image.open(io.BytesIO(base_bytes)).convert("RGB")
    w, h = base.size

    fade_col = _fade_color(parsed)
    fade_y   = int(h * fade_ratio)
    canvas   = _gradient_fade(base, fade_y, fade_col, max_alpha, exponent)
    draw     = ImageDraw.Draw(canvas)

    scale = w / 1000
    fn(draw, canvas, w, h, title, features, parsed, scale)

    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ─── Legacy alias (used by fallback render_card_pillow) ───────────────────────

def overlay_text_premium(
    base_bytes: bytes,
    title:      str,
    features:   list[str],
    colors_str: str,
) -> bytes:
    """Backward-compatible alias: uses lifestyle (concept 3) treatment."""
    return overlay_text_concept(base_bytes, title, features, colors_str, concept_index=3)


# ─────────────────────────────────────────────────────────────────────────────
#  Pillow-only fallback card
# ─────────────────────────────────────────────────────────────────────────────

def render_card_pillow(
    background_bytes: bytes,
    product_bytes:    bytes,
    title:            str,
    features:         list[str],
    colors_str:       str,
    concept_index:    int = 3,
) -> bytes:
    """
    Full Pillow fallback card: background + product + concept text.
    Used when OpenAI API is not available.
    """
    from PIL import ImageFilter

    parsed = _parse_colors(colors_str)

    W, H = 1000, 1000
    ZONE = int(H * 0.72)

    bg   = Image.open(io.BytesIO(background_bytes)).convert("RGB").resize((W, H))

    # Composite product with soft ellipse shadow
    try:
        MAX_W, MAX_H = int(W * 0.70), int(ZONE * 0.85)
        prod = Image.open(io.BytesIO(product_bytes)).convert("RGBA")
        prod.thumbnail((MAX_W, MAX_H), Image.LANCZOS)

        px = (W - prod.width)  // 2
        py = max(20, (ZONE - prod.height) // 2 - 20)

        # Soft ellipse shadow under product
        shadow_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        s_draw       = ImageDraw.Draw(shadow_layer)
        s_draw.ellipse(
            [px + prod.width // 6, py + prod.height - 20,
             px + prod.width * 5 // 6, py + prod.height + 40],
            fill=(0, 0, 0, 65)
        )
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(20))
        bg_rgba      = bg.convert("RGBA")
        bg_rgba      = Image.alpha_composite(bg_rgba, shadow_layer)
        bg           = bg_rgba.convert("RGB")

        bg.paste(prod, (px, py), mask=prod.split()[3])
    except Exception:
        pass

    buf = io.BytesIO()
    bg.save(buf, "PNG")
    return overlay_text_concept(buf.getvalue(), title, features, colors_str, concept_index)
