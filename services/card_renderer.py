"""
Card renderer — 5 distinct card type layouts for 800×1000 (4:5) canvas.

Each type has its own:
  - Canvas split (scene zone : text zone)
  - Typography treatment
  - Layout logic

Types:
  hero      740px scene / 260px panel — large scene, product name, minimal
  lifestyle 850px scene / 150px strip — atmospheric, single title line
  features  380px scene / 620px panel — infographic with drawn icons
  editorial 650px scene / 350px panel — oversized typographic statement
  detail    800px scene / 200px panel — material focus, quiet type
"""

import io
import math
import re
import textwrap

from PIL import Image, ImageDraw, ImageFilter

from services.fonts import get_font
from services.card_types import CANVAS_LAYOUT


# ─── Color helpers ────────────────────────────────────────────────────────────

def _parse_colors(s: str) -> list:
    hexes  = re.findall(r'#([0-9A-Fa-f]{6})', s)
    result = [tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) for h in hexes[:3]]
    while len(result) < 3:
        result.append((60, 60, 60))
    return result


def _lum(c: tuple) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _darkest(parsed: list) -> tuple:
    return sorted(parsed, key=_lum)[0]


def _lightest(parsed: list) -> tuple:
    return sorted(parsed, key=_lum)[-1]


def _on(bg: tuple) -> tuple:
    return (250, 250, 250) if _lum(bg) < 140 else (16, 16, 20)


def _clean(feat: str) -> str:
    return re.sub(r'^[✅•▸✓➤→✦\-\s]+', '', feat).strip()


def _track(s: str, n: int = 1) -> str:
    return (" " * n).join(s.upper())


# ─── Text rendering ───────────────────────────────────────────────────────────

def _t(draw, xy, text, font, fill, shadow: int = 0):
    if shadow:
        x, y = xy
        sc = (0, 0, 0) if fill[0] > 160 else (255, 255, 255)
        for dx, dy in ((shadow, shadow), (shadow, 0)):
            draw.text((x + dx, y + dy), text, fill=sc, font=font)
    draw.text(xy, text, fill=fill, font=font)


def _hrule(draw, x1, x2, y, color, w: int = 1):
    draw.line([(x1, y), (x2, y)], fill=color, width=w)


# ─── Canvas assembly ──────────────────────────────────────────────────────────

def _make_canvas(scene_img: Image.Image, card_type: str, panel_col: tuple) -> Image.Image:
    """
    Build 800×1000 canvas.
    Scene is scaled to (800 × scene_h), panel_col fills the rest.
    Gradient blend at the boundary.
    """
    cw, ch, scene_h, blend = CANVAS_LAYOUT[card_type]

    scene = scene_img.convert("RGB").resize((cw, scene_h), Image.LANCZOS)

    canvas = Image.new("RGB", (cw, ch), panel_col)
    canvas.paste(scene, (0, 0))

    # Ease-in gradient blend from scene into panel
    r, g, b = panel_col
    overlay = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    for dy in range(blend):
        t     = dy / blend
        alpha = int((t ** 1.6) * 255)
        ypos  = scene_h - blend + dy
        d.line([(0, ypos), (cw, ypos)], fill=(r, g, b, alpha))

    return Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")


def _panel_col_for_type(card_type: str, parsed: list) -> tuple:
    dark  = _darkest(parsed)
    light = _lightest(parsed)
    if card_type == "lifestyle":
        return dark
    if card_type == "detail":
        return tuple(max(0, c - 20) for c in dark)
    if card_type == "editorial":
        return dark
    if card_type == "hero":
        # Slight lightening toward neutral
        return tuple(min(255, max(0, c - 10)) for c in dark)
    # features — clean neutral or dark depending on lightness
    if _lum(dark) < 80:
        return (20, 20, 25)
    return dark


# ─── Drawn icons for FEATURES card ───────────────────────────────────────────

def _icon_star(draw, cx, cy, sz, color):
    """5-pointed star — quality/premium."""
    ro, ri = sz // 2, int(sz * 0.21)
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        r   = ro if i % 2 == 0 else ri
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    draw.polygon(pts, fill=color)


def _icon_shield(draw, cx, cy, sz, color):
    """Shield — durability/protection."""
    w, h = int(sz * 0.8), sz
    pts  = [
        (cx - w // 2, cy - h // 2),
        (cx + w // 2, cy - h // 2),
        (cx + w // 2, cy + h // 5),
        (cx,          cy + h // 2),
        (cx - w // 2, cy + h // 5),
    ]
    draw.polygon(pts, fill=color)


def _icon_diamond(draw, cx, cy, sz, color):
    """Diamond — style/design."""
    h = sz // 2
    w = int(sz * 0.62)
    draw.polygon([(cx, cy - h), (cx + w, cy), (cx, cy + h), (cx - w, cy)], fill=color)


def _icon_wave(draw, cx, cy, sz, color):
    """Wavy lines — material/textile."""
    for off in (-4, 4):
        pts = []
        steps = 10
        for i in range(steps + 1):
            x = cx - sz // 2 + i * sz // steps
            y = cy + off + int(3.5 * math.sin(i * math.pi * 1.8 / steps * 2))
            pts.append((x, y))
        for i in range(len(pts) - 1):
            draw.line([pts[i], pts[i + 1]], fill=color, width=2)


def _icon_leaf(draw, cx, cy, sz, color):
    """Concentric arcs — comfort/softness."""
    for r in (sz // 4, sz // 2, int(sz * 0.72)):
        draw.arc([cx - r, cy - r, cx + r, cy + r], start=210, end=330, fill=color, width=2)


def _pick_icon(feat: str):
    t = feat.lower()
    if any(w in t for w in ["материал", "ткань", "wool", "cotton", "шерст", "велюр", "fabric"]):
        return _icon_wave
    if any(w in t for w in ["комфорт", "удобн", "мягк", "soft", "comfort", "ergon"]):
        return _icon_leaf
    if any(w in t for w in ["качеств", "premium", "высок", "quality", "надежн", "надёжн"]):
        return _icon_star
    if any(w in t for w in ["прочн", "долговечн", "durabl", "protect", "защит", "resist"]):
        return _icon_shield
    return _icon_diamond


# ─── Typography zone renderers ────────────────────────────────────────────────

def _zone_hero(canvas: Image.Image, title: str, features: list, parsed: list):
    """
    HERO — 260px panel.
    Product name large + centered. One optional tagline. Clean.
    """
    _, ch, scene_h, _ = CANVAS_LAYOUT["hero"]
    cw = canvas.width
    dark   = _darkest(parsed)
    accent = parsed[2]
    bg     = tuple(max(0, c - 15) for c in dark)
    txt    = _on(bg)
    ar, ag, ab = accent

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, scene_h, cw, ch], fill=bg)
    _hrule(draw, 0, cw, scene_h, (ar, ag, ab), w=2)

    pad = 44
    y   = scene_h + 30

    f_h = get_font("Bold", 48)
    raw = title.strip()[:38]
    # Try single line; wrap only if necessary
    lines = textwrap.wrap(raw, width=22)[:2]
    for line in lines:
        _t(draw, (pad, y), line, f_h, txt, shadow=1)
        y += 58

    y += 8
    if features:
        f_sub = get_font("Light", 20)
        sub   = _clean(features[0])[:60]
        if sub:
            _t(draw, (pad, y), sub, f_sub, tuple(max(c - 40, 0) for c in txt), shadow=0)


def _zone_lifestyle(canvas: Image.Image, title: str, features: list, parsed: list):
    """
    LIFESTYLE — 150px strip.
    Single product name in elegant type. Almost nothing.
    """
    _, ch, scene_h, _ = CANVAS_LAYOUT["lifestyle"]
    cw = canvas.width
    dark   = _darkest(parsed)
    accent = parsed[2]
    bg     = dark
    txt    = _on(bg)
    ar, ag, ab = accent

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, scene_h, cw, ch], fill=bg)
    _hrule(draw, 0, cw, scene_h, (ar, ag, ab), w=1)

    pad = 42
    y   = scene_h + 22

    f_h  = get_font("SemiBold", 40)
    f_sub = get_font("Light",   18)

    raw = title.strip()[:34]
    _t(draw, (pad, y), raw, f_h, txt, shadow=1)
    y += 50

    if features:
        sub = _clean(features[0])[:55]
        if sub:
            feat_col = tuple(max(c - 35, 0) for c in txt) if txt[0] > 160 \
                       else tuple(min(c + 35, 255) for c in txt)
            _t(draw, (pad, y), sub, f_sub, feat_col)


def _zone_features(canvas: Image.Image, title: str, features: list, parsed: list,
                   product_bytes: bytes):
    """
    FEATURES — 620px panel.
    Short title + up to 4 feature blocks (drawn icon + name).
    """
    _, ch, scene_h, _ = CANVAS_LAYOUT["features"]
    cw = canvas.width
    dark   = _darkest(parsed)
    accent = parsed[2]
    ar, ag, ab = accent

    # Panel background — dark but not as dark as scene
    bg = tuple(min(255, max(0, c + 15)) for c in dark) if _lum(dark) < 60 \
         else tuple(max(0, c - 20) for c in dark)
    txt  = _on(bg)
    muted = tuple(max(c - 40, 0) for c in txt) if txt[0] > 160 \
            else tuple(min(c + 40, 255) for c in txt)

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, scene_h, cw, ch], fill=bg)
    _hrule(draw, 0, cw, scene_h, (ar, ag, ab), w=3)

    pad = 42
    y   = scene_h + 24

    f_title = get_font("Bold",    34)
    f_feat  = get_font("SemiBold", 21)
    f_desc  = get_font("Regular",  17)

    # Product title
    raw = title.strip()[:40]
    lines = textwrap.wrap(raw, width=28)[:1]
    for line in lines:
        _t(draw, (pad, y), line, f_title, txt)
        y += 44

    _hrule(draw, pad, cw - pad, y, (ar, ag, ab), w=1)
    y += 20

    # Feature blocks: icon (40×40) + text
    icon_size = 36
    icon_col  = (ar, ag, ab)
    text_x    = pad + icon_size + 20

    for feat in features[:4]:
        clean = _clean(feat)[:65]
        if not clean:
            continue

        icon_cx = pad + icon_size // 2
        icon_cy = y + icon_size // 2

        icon_fn = _pick_icon(clean)
        icon_fn(draw, icon_cx, icon_cy, icon_size, icon_col)

        # Feature label (first 3 words as title, rest as description)
        words = clean.split()
        if len(words) > 4:
            feat_title = " ".join(words[:4])
            feat_desc  = " ".join(words[4:])[:48]
        else:
            feat_title = clean
            feat_desc  = ""

        _t(draw, (text_x, y + 2), feat_title, f_feat, txt)
        if feat_desc:
            _t(draw, (text_x, y + 26), feat_desc, f_desc, muted)

        y += icon_size + 20

    # Product placed in scene zone by _place_product_in_scene


def _zone_editorial(canvas: Image.Image, title: str, features: list, parsed: list):
    """
    EDITORIAL — 350px panel.
    Oversized tracked uppercase headline + features in one restrained row.
    """
    _, ch, scene_h, _ = CANVAS_LAYOUT["editorial"]
    cw = canvas.width
    dark   = _darkest(parsed)
    accent = parsed[2]
    bg     = dark
    txt    = _on(bg)
    ar, ag, ab = accent

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, scene_h, cw, ch], fill=bg)
    draw.rectangle([0, scene_h, cw, scene_h + 5], fill=(ar, ag, ab))  # thick bar

    pad = 38
    y   = scene_h + 24

    f_h  = get_font("Bold",  60)
    f_sub = get_font("Light", 19)

    raw     = title.strip().upper()[:28]
    tracked = _track(raw, 1) if len(raw) <= 14 else raw
    lines   = textwrap.wrap(tracked, width=20)[:2]
    for line in lines:
        _t(draw, (pad, y), line, f_h, txt, shadow=1)
        y += 72

    y += 8

    cleans = [_clean(f)[:26] for f in features[:3] if _clean(f)]
    if cleans:
        row  = "   ·   ".join(cleans)
        feat_col = tuple(max(c - 35, 0) for c in txt) if txt[0] > 160 \
                   else tuple(min(c + 35, 255) for c in txt)
        _t(draw, (pad, y), row, f_sub, feat_col)
        y += 32

    _hrule(draw, pad, pad + 80, y, (ar, ag, ab), w=1)


def _zone_detail(canvas: Image.Image, title: str, features: list, parsed: list):
    """
    DETAIL — 200px panel.
    Material/specification name + one key property. Maximum restraint.
    """
    _, ch, scene_h, _ = CANVAS_LAYOUT["detail"]
    cw = canvas.width
    dark   = _darkest(parsed)
    accent = parsed[2]
    bg     = tuple(max(0, c - 20) for c in dark)
    txt    = _on(bg)
    ar, ag, ab = accent

    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, scene_h, cw, ch], fill=bg)
    _hrule(draw, 0, cw, scene_h, (ar, ag, ab), w=1)

    pad = 46
    y   = scene_h + 30

    f_h  = get_font("SemiBold", 32)
    f_sub = get_font("Light",   19)

    raw     = title.strip().upper()[:32]
    tracked = _track(raw, 1) if len(raw) <= 14 else raw
    _t(draw, (pad, y), tracked, f_h, txt)
    y += 44

    _hrule(draw, pad, pad + 70, y, (ar, ag, ab), w=1)
    y += 14

    if features:
        sub = _clean(features[0])[:58]
        if sub:
            feat_col = tuple(max(c - 35, 0) for c in txt) if txt[0] > 160 \
                       else tuple(min(c + 35, 255) for c in txt)
            _t(draw, (pad, y), sub, f_sub, feat_col)


# ─── Product placement helper (for features fallback) ────────────────────────

def _place_product(canvas: Image.Image, product_bytes: bytes,
                   scene_h: int) -> Image.Image:
    """Place product with ellipse shadow into scene zone (for FEATURES card)."""
    cw = canvas.width
    try:
        MAX_W = int(cw * 0.60)
        MAX_H = int(scene_h * 0.82)
        prod  = Image.open(io.BytesIO(product_bytes)).convert("RGBA")
        prod.thumbnail((MAX_W, MAX_H), Image.LANCZOS)

        px = (cw - prod.width)  // 2
        py = max(12, (scene_h - prod.height) // 2 - 10)

        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        s_d    = ImageDraw.Draw(shadow)
        s_d.ellipse(
            [px + prod.width // 6,     py + prod.height - 10,
             px + prod.width * 5 // 6, py + prod.height + 32],
            fill=(0, 0, 0, 55)
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(16))

        c_rgba = canvas.convert("RGBA")
        c_rgba = Image.alpha_composite(c_rgba, shadow)
        c_rgba.paste(prod, (px, py), mask=prod.split()[3])
        return c_rgba.convert("RGB")
    except Exception:
        return canvas


# ─── Public API ───────────────────────────────────────────────────────────────

def render_card(
    card_type:     str,
    scene_bytes:   bytes | None,
    product_bytes: bytes,
    title:         str,
    features:      list[str],
    colors_str:    str,
) -> bytes:
    """
    Assemble a finished 800×1000 (4:5) product card.

    scene_bytes — AI-generated scene or None (falls back to gradient).
    card_type   — determines layout, typography, and composition.
    """
    from services.background_gen import pillow_gradient_background

    parsed    = _parse_colors(colors_str)
    panel_col = _panel_col_for_type(card_type, parsed)
    cw, ch, scene_h, _ = CANVAS_LAYOUT[card_type]

    # ── Build scene image ─────────────────────────────────────────────────────
    if scene_bytes:
        scene_img = Image.open(io.BytesIO(scene_bytes))
    else:
        # Pillow gradient background, product composited on top
        bg_bytes  = pillow_gradient_background(colors_str, w=1024, h=1024)
        scene_img = Image.open(io.BytesIO(bg_bytes))

    canvas = _make_canvas(scene_img, card_type, panel_col)

    # For features card (or any without AI scene), place product in scene zone
    if scene_bytes is None:
        canvas = _place_product(canvas, product_bytes, scene_h)

    # ── Apply typography zone ─────────────────────────────────────────────────
    if card_type == "hero":
        _zone_hero(canvas, title, features, parsed)
    elif card_type == "lifestyle":
        _zone_lifestyle(canvas, title, features, parsed)
    elif card_type == "features":
        _zone_features(canvas, title, features, parsed, product_bytes)
    elif card_type == "editorial":
        _zone_editorial(canvas, title, features, parsed)
    elif card_type == "detail":
        _zone_detail(canvas, title, features, parsed)

    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ─── Legacy aliases ───────────────────────────────────────────────────────────

def overlay_text_concept(base_bytes, title, features, colors_str,
                          concept_index=1, concept=None, category="other"):
    """Legacy alias — routes to hero layout."""
    return render_card("hero", base_bytes, b"", title, features, colors_str)


def overlay_text_premium(base_bytes, title, features, colors_str):
    """Legacy alias."""
    return render_card("hero", base_bytes, b"", title, features, colors_str)


def render_card_pillow(background_bytes, product_bytes, title, features,
                       colors_str, concept_index=3, concept=None, category="other"):
    """Legacy alias — routes to features fallback layout."""
    return render_card("features", None, product_bytes, title, features, colors_str)
