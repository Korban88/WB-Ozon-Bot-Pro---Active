"""
Card renderer — design system for marketplace product cards.

Architecture:
  Canvas:        750 × 1000 px  (3:4 ratio — WB/Ozon marketplace standard)
  Scene zone:    750 × 750 px   (top 75% — AI-generated scene, scaled to square)
  Typography:    750 × 250 px   (bottom 25% — concept-specific designed panel)
  Blend:          60 px gradient transition at scene/panel boundary

Visual families (auto-selected from concept content + category):
  luxury_dark     — near-black panel, thin gold rule, tracked uppercase, em-dash features
  editorial       — strong color panel, thick accent bar, oversized single title, | separators
  lifestyle_hero  — warm dark panel, SemiBold headline, drawn circle bullets
  natural_artisan — earthy warm panel, Regular title, drawn diamond bullets
  minimal_pure    — extreme restraint, tracked caps, thin dash separators
"""

import io
import re
import textwrap

from PIL import Image, ImageDraw

from services.fonts import get_font

# ─── Canvas constants ─────────────────────────────────────────────────────────
CARD_W  = 750
CARD_H  = 1000
SCENE_H = 750   # top square zone: scene
TEXT_H  = 250   # bottom zone: typography panel
BLEND   = 60    # px gradient blend at boundary


# ─── Color utilities ──────────────────────────────────────────────────────────

def _parse_colors(s: str) -> list:
    hexes  = re.findall(r'#([0-9A-Fa-f]{6})', s)
    result = [tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) for h in hexes[:3]]
    while len(result) < 3:
        result.append((60, 60, 60))
    return result


def _lum(c: tuple) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _text_on(bg: tuple) -> tuple:
    return (255, 255, 255) if _lum(bg) < 145 else (18, 18, 22)


def _clean(feat: str) -> str:
    return re.sub(r'^[✅•▸✓➤→✦\-\s]+', '', feat).strip()


def _track(text: str, n: int = 1) -> str:
    """Simulate letter-tracking by inserting thin spaces between characters."""
    return (" " * n).join(text.upper())


# ─── Text rendering ───────────────────────────────────────────────────────────

def _text(draw, xy, text, font, fill, shadow_offset: int = 0):
    """Draw text, optionally with a drop shadow."""
    if shadow_offset:
        x, y = xy
        sc = (0, 0, 0) if fill[0] > 160 else (255, 255, 255)
        for dx, dy in ((shadow_offset, shadow_offset), (shadow_offset, 0)):
            draw.text((x + dx, y + dy), text, fill=sc, font=font)
    draw.text(xy, text, fill=fill, font=font)


# ─── Drawn design elements ────────────────────────────────────────────────────

def _hrule(draw, x1, x2, y, color, width: int = 1):
    """Horizontal rule."""
    draw.line([(x1, y), (x2, y)], fill=color, width=width)


def _vrule(draw, x, y1, y2, color, width: int = 3):
    """Vertical accent stripe."""
    draw.rectangle([x, y1, x + width - 1, y2], fill=color)


def _dot(draw, cx, cy, r, color):
    """Filled circle bullet."""
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


def _diamond(draw, cx, cy, size, color):
    """Filled diamond bullet."""
    h = size // 2
    draw.polygon([(cx, cy - h), (cx + h, cy), (cx, cy + h), (cx - h, cy)], fill=color)


def _dash(draw, x, y, length, color, width: int = 1):
    """Short horizontal dash before feature text."""
    mid = y + int(length * 0.55)
    draw.line([(x, mid), (x + length, mid)], fill=color, width=width)


# ─── Visual family analysis ───────────────────────────────────────────────────

_KW_LUXURY   = {"luxury", "premium", "gold", "dark", "exclusive", "elite",
                "velvet", "noir", "glamour", "opulent", "rich", "crystal",
                "silver", "metallic", "glossy", "deep", "bold"}
_KW_NATURAL  = {"natural", "eco", "organic", "wood", "warm", "artisan",
                "craft", "earth", "linen", "stone", "botanical", "cozy",
                "home", "handmade", "hygge", "woven", "wool", "cotton",
                "ceramic", "clay", "rustic", "autumn", "forest"}
_KW_EDITORIAL = {"editorial", "fashion", "bold", "graphic", "contrast",
                  "magazine", "stark", "urban", "street", "contemporary",
                  "dynamic", "sport", "tech", "modern", "powerful"}
_KW_MINIMAL  = {"minimal", "pure", "clean", "white", "simple", "restrained",
                "zen", "nude", "quiet", "airy", "light", "elegant", "subtle",
                "refined", "sleek"}

_CAT_DEFAULTS = {
    "electronics": "editorial",
    "clothing":    "editorial",
    "beauty":      "natural_artisan",
    "home":        "natural_artisan",
    "accessories": "luxury_dark",
    "other":       "lifestyle_hero",
}


def get_visual_family(concept: dict, category: str = "other") -> str:
    """Select visual family from concept text content + category fallback."""
    text  = (concept.get("name", "") + " " + concept.get("composition", "")).lower()
    words = set(re.findall(r'\b\w+\b', text))

    scores = {
        "luxury_dark":     len(words & _KW_LUXURY),
        "natural_artisan": len(words & _KW_NATURAL),
        "editorial":       len(words & _KW_EDITORIAL),
        "minimal_pure":    len(words & _KW_MINIMAL),
    }
    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best
    return _CAT_DEFAULTS.get(category, "lifestyle_hero")


def _panel_color(family: str, parsed: list) -> tuple:
    dark = sorted(parsed, key=_lum)[0]
    if family == "minimal_pure":
        return (16, 16, 20) if _lum(dark) < 70 else (244, 244, 247)
    if family == "natural_artisan":
        r, g, b = dark
        return (min(255, r + 10), max(0, g + 5), max(0, b - 5))
    return dark


# ─── Typography zone renderers ────────────────────────────────────────────────

def _zone_luxury(canvas: Image.Image, title: str, features: list, parsed: list):
    """
    Luxury Dark:
    Very dark panel · thin gold rule · tracked uppercase title
    · horizontal rule separator · em-dash features in Light weight
    """
    dark   = sorted(parsed, key=_lum)[0]
    accent = parsed[2]
    bg     = tuple(max(0, c - 15) for c in dark)
    txt    = (235, 225, 210)          # warm white
    feat   = (165, 155, 140)          # muted warm

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, SCENE_H, CARD_W, CARD_H], fill=bg)

    ar, ag, ab = accent
    _hrule(draw, 0, CARD_W, SCENE_H, (ar, ag, ab), width=2)

    pad = 42
    y   = SCENE_H + 26

    f_h = get_font("Bold",  40)
    f_f = get_font("Light", 19)

    raw     = title.strip().upper()[:42]
    tracked = _track(raw, 1) if len(raw) <= 18 else raw
    draw.text((pad, y), tracked, fill=txt, font=f_h)
    y += 50

    _hrule(draw, pad, CARD_W - pad, y, (ar, ag, ab, 160), width=1)
    y += 16

    for feat_txt in features[:3]:
        clean = _clean(feat_txt)[:60]
        if not clean:
            continue
        draw.text((pad,       y), "—", fill=(ar, ag, ab), font=f_f)
        draw.text((pad + 24,  y), clean,  fill=feat,       font=f_f)
        y += 30


def _zone_editorial(canvas: Image.Image, title: str, features: list, parsed: list):
    """
    Editorial:
    Strong panel · thick accent bar · huge single-line title
    · features in one row with vertical | separators
    """
    dark   = sorted(parsed, key=_lum)[0]
    accent = parsed[2]
    bg     = tuple(max(0, c - 10) for c in dark)
    txt    = (252, 252, 252)
    ar, ag, ab = accent

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, SCENE_H, CARD_W, CARD_H], fill=bg)
    draw.rectangle([0, SCENE_H, CARD_W, SCENE_H + 5], fill=(ar, ag, ab))

    pad = 36
    y   = SCENE_H + 20

    f_h = get_font("Bold",  50)
    f_f = get_font("Light", 17)

    title_line = title.strip()[:30]
    draw.text((pad, y), title_line, fill=txt, font=f_h)
    y += 64

    cleans = [_clean(f)[:24] for f in features[:3] if _clean(f)]
    if cleans:
        sep_str = "   |   ".join(cleans)
        draw.text((pad, y), sep_str, fill=(ar, ag, ab), font=f_f)
        y += 30

    _hrule(draw, pad, pad + 70, y + 14, (ar, ag, ab), width=1)


def _zone_lifestyle(canvas: Image.Image, title: str, features: list, parsed: list):
    """
    Lifestyle Hero:
    Warm dark panel · SemiBold headline · drawn circle bullets
    """
    dark   = sorted(parsed, key=_lum)[0]
    accent = parsed[2]
    r0, g0, b0 = dark
    bg     = (min(255, r0 + 5), max(0, g0 - 3), max(0, b0 - 8))
    bg     = tuple(max(0, min(255, c)) for c in bg)
    txt    = _text_on(bg)
    feat   = tuple(max(c - 22, 0) for c in txt) if txt[0] > 160 \
             else tuple(min(c + 22, 255) for c in txt)
    ar, ag, ab = accent

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, SCENE_H, CARD_W, CARD_H], fill=bg)

    pad  = 38
    y    = SCENE_H + 22

    f_h = get_font("SemiBold", 44)
    f_f = get_font("Regular",  22)

    for line in textwrap.wrap(title.strip()[:72], width=25)[:2]:
        _text(draw, (pad, y), line, f_h, txt, shadow_offset=1)
        y += 52
    y += 4

    bx = pad + 5
    tx = pad + 22
    for feat_txt in features[:3]:
        clean = _clean(feat_txt)[:56]
        if not clean:
            continue
        _dot(draw, bx, y + 11, 4, (ar, ag, ab))
        draw.text((tx, y), clean, fill=feat, font=f_f)
        y += 34


def _zone_natural(canvas: Image.Image, title: str, features: list, parsed: list):
    """
    Natural Artisan:
    Earthy warm panel · Regular-weight headline (warmth)
    · drawn diamond bullets · generous spacing
    """
    dark   = sorted(parsed, key=_lum)[0]
    accent = parsed[2]
    r0, g0, b0 = dark
    bg     = (min(255, r0 + 12), max(0, g0 + 6), max(0, b0 - 6))
    bg     = tuple(max(0, min(255, c)) for c in bg)
    txt    = _text_on(bg)
    feat   = tuple(max(c - 18, 0) for c in txt) if txt[0] > 160 \
             else tuple(min(c + 18, 255) for c in txt)
    ar, ag, ab = accent

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, SCENE_H, CARD_W, CARD_H], fill=bg)
    _hrule(draw, 0, CARD_W, SCENE_H, (ar, ag, ab), width=1)

    pad = 38
    y   = SCENE_H + 22

    f_h = get_font("Regular", 38)
    f_f = get_font("Regular", 20)

    for line in textwrap.wrap(title.strip()[:80], width=28)[:2]:
        draw.text((pad, y), line, fill=txt, font=f_h)
        y += 46
    y += 10

    bx = pad + 5
    tx = pad + 20
    for feat_txt in features[:3]:
        clean = _clean(feat_txt)[:58]
        if not clean:
            continue
        _diamond(draw, bx, y + 11, 9, (ar, ag, ab))
        draw.text((tx, y), clean, fill=feat, font=f_f)
        y += 31


def _zone_minimal(canvas: Image.Image, title: str, features: list, parsed: list):
    """
    Minimal Pure:
    Very light or very dark panel · tracked caps · thin rules · max restraint
    """
    dark  = sorted(parsed, key=_lum)[0]
    accent = parsed[2]

    if _lum(dark) < 70:
        bg   = (16, 16, 20)
        txt  = (215, 215, 215)
        feat = (135, 135, 140)
    else:
        bg   = (244, 244, 247)
        txt  = (18, 18, 22)
        feat = (100, 100, 105)
    ar, ag, ab = accent

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, SCENE_H, CARD_W, CARD_H], fill=bg)
    _hrule(draw, 0, CARD_W, SCENE_H, (ar, ag, ab), width=1)

    pad = 46
    y   = SCENE_H + 34

    f_h = get_font("SemiBold", 30)
    f_f = get_font("Light",    17)

    raw     = title.strip().upper()[:36]
    tracked = _track(raw, 2) if len(raw) <= 13 else _track(raw, 1)
    draw.text((pad, y), tracked, fill=txt, font=f_h)
    y += 42

    _hrule(draw, pad, pad + 90, y, (ar, ag, ab), width=1)
    y += 16

    for feat_txt in features[:2]:
        clean = _clean(feat_txt)[:54]
        if not clean:
            continue
        _dash(draw, pad, y, 12, (ar, ag, ab), width=1)
        draw.text((pad + 20, y), clean, fill=feat, font=f_f)
        y += 28


_ZONE_FN = {
    "luxury_dark":     _zone_luxury,
    "editorial":       _zone_editorial,
    "lifestyle_hero":  _zone_lifestyle,
    "natural_artisan": _zone_natural,
    "minimal_pure":    _zone_minimal,
}


# ─── Canvas assembly ──────────────────────────────────────────────────────────

def _make_canvas(scene_bytes: bytes, panel_col: tuple) -> Image.Image:
    """
    Build 750×1000 canvas:
      Top 750px  — scene (1024×1024 AI output scaled to 750×750)
      Bottom 250px — panel base color
      60px gradient blend at boundary
    """
    scene = Image.open(io.BytesIO(scene_bytes)).convert("RGB")
    scene = scene.resize((CARD_W, SCENE_H), Image.LANCZOS)

    canvas = Image.new("RGB", (CARD_W, CARD_H), panel_col)
    canvas.paste(scene, (0, 0))

    # Ease-in gradient blend from scene into panel
    r, g, b = panel_col
    overlay = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for dy in range(BLEND):
        t     = dy / BLEND
        alpha = int((t ** 1.5) * 255)
        ypos  = SCENE_H - BLEND + dy
        d.line([(0, ypos), (CARD_W, ypos)], fill=(r, g, b, alpha))

    return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")


# ─── Public API ───────────────────────────────────────────────────────────────

def overlay_text_concept(
    base_bytes:    bytes,
    title:         str,
    features:      list[str],
    colors_str:    str,
    concept_index: int = 1,
    concept:       dict | None = None,
    category:      str = "other",
) -> bytes:
    """
    Assemble final card: 750×1000 (3:4) with designed typography panel.

    Visual family is chosen from concept content (name + composition keywords),
    falling back to category default.
    """
    parsed     = _parse_colors(colors_str)
    family     = get_visual_family(concept or {}, category) if concept \
                 else ["luxury_dark", "editorial", "lifestyle_hero",
                        "natural_artisan", "minimal_pure"][(concept_index - 1) % 5]

    panel_col  = _panel_color(family, parsed)
    canvas     = _make_canvas(base_bytes, panel_col)

    _ZONE_FN.get(family, _zone_lifestyle)(canvas, title, features, parsed)

    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def overlay_text_premium(
    base_bytes: bytes,
    title:      str,
    features:   list[str],
    colors_str: str,
) -> bytes:
    """Backward-compatible alias — lifestyle treatment."""
    return overlay_text_concept(base_bytes, title, features, colors_str, concept_index=3)


def render_card_pillow(
    background_bytes: bytes,
    product_bytes:    bytes,
    title:            str,
    features:         list[str],
    colors_str:       str,
    concept_index:    int = 3,
    concept:          dict | None = None,
    category:         str = "other",
) -> bytes:
    """
    Full Pillow fallback card at 750×1000 (3:4).
    Background resized to scene zone + product with shadow + designed panel.
    """
    from PIL import ImageFilter

    parsed    = _parse_colors(colors_str)
    family    = get_visual_family(concept or {}, category) if concept \
                else ["luxury_dark", "editorial", "lifestyle_hero",
                       "natural_artisan", "minimal_pure"][(concept_index - 1) % 5]
    panel_col = _panel_color(family, parsed)

    # Build scene zone from background
    bg_img = Image.open(io.BytesIO(background_bytes)).convert("RGB")
    bg_img = bg_img.resize((CARD_W, SCENE_H), Image.LANCZOS)

    scene_buf = io.BytesIO()
    bg_img.save(scene_buf, "PNG")

    canvas = _make_canvas(scene_buf.getvalue(), panel_col)

    # Composite product with ellipse shadow into scene zone
    try:
        MAX_W = int(CARD_W * 0.68)
        MAX_H = int(SCENE_H * 0.80)
        prod  = Image.open(io.BytesIO(product_bytes)).convert("RGBA")
        prod.thumbnail((MAX_W, MAX_H), Image.LANCZOS)

        px = (CARD_W - prod.width)  // 2
        py = max(16, (SCENE_H - prod.height) // 2 - 16)

        shadow = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
        s_d    = ImageDraw.Draw(shadow)
        s_d.ellipse(
            [px + prod.width // 6,     py + prod.height - 12,
             px + prod.width * 5 // 6, py + prod.height + 36],
            fill=(0, 0, 0, 60)
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))

        c_rgba = canvas.convert("RGBA")
        c_rgba = Image.alpha_composite(c_rgba, shadow)
        c_rgba.paste(prod, (px, py), mask=prod.split()[3])
        canvas = c_rgba.convert("RGB")
    except Exception:
        pass

    _ZONE_FN.get(family, _zone_lifestyle)(canvas, title, features, parsed)

    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    return buf.getvalue()
