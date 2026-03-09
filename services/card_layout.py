"""
Card layout presets — 5 distinct professional marketplace card compositions.

Each layout:
  1. Accepts a background image (AI-generated or Pillow gradient)
  2. Places the product photo with a soft ellipse shadow
  3. Renders typography with Montserrat fonts

Usage:
    from services.card_layout import get_layout
    img_bytes = get_layout(concept_index).render(bg_bytes, product_bytes, title, features, colors_str)
"""

import io
import re
import textwrap

from PIL import Image, ImageDraw, ImageFilter

from services.fonts import get_font

W, H = 1000, 1000  # standard card size


# ─── Color helpers ────────────────────────────────────────────────────────────

def _parse_colors(s: str) -> list[tuple[int, int, int]]:
    hexes = re.findall(r'#([0-9A-Fa-f]{6})', s)
    result = [tuple(int(h[i:i+2], 16) for i in (0, 2, 4)) for h in hexes[:3]]
    while len(result) < 3:
        result.append((80, 80, 80))
    return result


def _lum(c: tuple) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _fade_color(parsed: list) -> tuple:
    """Return darkest color for gradient fade zones."""
    darks = sorted(parsed, key=_lum)
    return darks[0]


def _text_color(bg_color: tuple) -> tuple:
    return (255, 255, 255) if _lum(bg_color) < 140 else (15, 15, 20)


def _clean_feat(feat: str) -> str:
    return re.sub(r'^[✅•▸✓➤→✦\-\s]+', '', feat).strip()


# ─── Drawing helpers ──────────────────────────────────────────────────────────

def _shadow_text(draw, xy, text, font, fill):
    """Draw text with a drop shadow for readability."""
    x, y = xy
    if fill[0] > 180:  # light text → dark shadow
        for dx, dy in ((2, 2), (1, 2), (2, 1)):
            draw.text((x + dx, y + dy), text, fill=(0, 0, 0), font=font)
    else:              # dark text → light shadow
        draw.text((x + 1, y + 1), text, fill=(255, 255, 255), font=font)
    draw.text(xy, text, fill=fill, font=font)


def _gradient_fade(canvas: Image.Image, x0, y0, x1, y1, color,
                   max_alpha: int = 220) -> Image.Image:
    """Apply ease-in gradient fade from transparent → color over a rectangle."""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay)
    r, g, b = color
    region_h = y1 - y0
    for dy in range(region_h):
        t = dy / region_h
        alpha = int((t ** 1.5) * max_alpha)
        d.line([(x0, y0 + dy), (x1, y0 + dy)], fill=(r, g, b, alpha))
    return Image.alpha_composite(canvas.convert("RGBA"), overlay)


def _place_product(canvas: Image.Image, product_bytes: bytes,
                   center_x: int, center_y: int,
                   max_w: int, max_h: int,
                   shadow_opacity: int = 70) -> Image.Image:
    """Composite product onto canvas with a soft ellipse drop shadow."""
    try:
        prod = Image.open(io.BytesIO(product_bytes)).convert("RGBA")
        prod.thumbnail((max_w, max_h), Image.LANCZOS)

        px = center_x - prod.width  // 2
        py = center_y - prod.height // 2

        # Soft ellipse shadow
        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        s_d = ImageDraw.Draw(shadow)
        sx1 = px + prod.width  // 6
        sx2 = px + prod.width  * 5 // 6
        sy1 = py + prod.height - 15
        sy2 = py + prod.height + 45
        s_d.ellipse([sx1, sy1, sx2, sy2], fill=(0, 0, 0, shadow_opacity))
        shadow = shadow.filter(ImageFilter.GaussianBlur(22))

        canvas_rgba = canvas.convert("RGBA")
        canvas_rgba = Image.alpha_composite(canvas_rgba, shadow)

        if prod.mode == "RGBA":
            canvas_rgba.paste(prod, (px, py), mask=prod.split()[3])
        else:
            canvas_rgba.paste(prod, (px, py))

        return canvas_rgba.convert("RGB")
    except Exception:
        return canvas.convert("RGB")


def _bottom_text(canvas: Image.Image, title: str, features: list[str],
                 colors_str: str, fade_start: float = 0.70,
                 max_alpha: int = 225, max_features: int = 3) -> bytes:
    """Standard bottom text zone: gradient fade + title + bullet features."""
    parsed = _parse_colors(colors_str)
    fade_col = _fade_color(parsed)
    accent   = parsed[2]
    txt_col  = _text_color(fade_col)

    fade_y = int(H * fade_start)
    canvas = _gradient_fade(canvas, 0, fade_y, W, H, fade_col, max_alpha=max_alpha)
    draw   = ImageDraw.Draw(canvas)

    scale   = W / 1000
    f_title = get_font("Bold",    int(42 * scale))
    f_feat  = get_font("Regular", int(23 * scale))
    f_dot   = get_font("SemiBold", int(23 * scale))

    pad = int(40 * scale)
    y   = fade_y + int(16 * scale)

    # Title — up to 2 lines
    for line in textwrap.wrap(title.strip()[:80], width=26)[:2]:
        _shadow_text(draw, (pad, y), line, f_title, txt_col)
        y += int(52 * scale)

    y += int(8 * scale)

    # Feature bullets
    feat_col = tuple(max(c - 25, 0) for c in txt_col) if txt_col[0] > 180 \
               else tuple(min(c + 25, 255) for c in txt_col)

    for feat in features[:max_features]:
        clean = _clean_feat(feat)[:55]
        if not clean:
            continue
        _shadow_text(draw, (pad, y + 1), "•", f_dot, accent)
        _shadow_text(draw, (pad + int(28 * scale), y), clean, f_feat, feat_col)
        y += int(36 * scale)

    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    return buf.getvalue()


# ─── Layout base class ────────────────────────────────────────────────────────

class _Layout:
    name: str

    def render(self, bg_bytes: bytes, product_bytes: bytes,
               title: str, features: list[str], colors_str: str) -> bytes:
        raise NotImplementedError


# ─── 1. Luxury Dark ───────────────────────────────────────────────────────────

class LuxuryDark(_Layout):
    """
    Dark cinematic overlay, product upper-center.
    Bold title + gold accent bullets. Maximum drama.
    """
    name = "luxury_dark"

    def render(self, bg_bytes, product_bytes, title, features, colors_str):
        parsed   = _parse_colors(colors_str)
        dark_col = _fade_color(parsed)

        bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB").resize((W, H))

        # Dark tint over entire image (drama boost)
        r, g, b = dark_col
        tint    = Image.new("RGBA", (W, H), (r, g, b, 95))
        canvas  = Image.alpha_composite(bg.convert("RGBA"), tint).convert("RGB")

        # Product — upper-center
        canvas = _place_product(canvas, product_bytes,
                                center_x=W // 2, center_y=int(H * 0.37),
                                max_w=int(W * 0.72), max_h=int(H * 0.58),
                                shadow_opacity=85)

        return _bottom_text(canvas, title, features, colors_str,
                            fade_start=0.69, max_alpha=232)


# ─── 2. Editorial Split ───────────────────────────────────────────────────────

class EditorialSplit(_Layout):
    """
    Left panel (text) + right zone (product). Magazine editorial feel.
    Accent vertical stripe on the left edge.
    """
    name = "editorial_split"

    def render(self, bg_bytes, product_bytes, title, features, colors_str):
        parsed   = _parse_colors(colors_str)
        dark_col = _fade_color(parsed)
        accent   = parsed[2]
        txt_col  = _text_color(dark_col)

        bg     = Image.open(io.BytesIO(bg_bytes)).convert("RGB").resize((W, H))
        canvas = bg

        # Left text panel (semi-transparent dark)
        panel = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d     = ImageDraw.Draw(panel)
        r, g, b = dark_col
        d.rectangle([0, 0, int(W * 0.47), H], fill=(r, g, b, 185))
        canvas = Image.alpha_composite(canvas.convert("RGBA"), panel).convert("RGB")

        # Product — right side, vertically centered
        canvas = _place_product(canvas, product_bytes,
                                center_x=int(W * 0.73), center_y=int(H * 0.45),
                                max_w=int(W * 0.50), max_h=int(H * 0.78),
                                shadow_opacity=60)

        # Accent vertical stripe
        draw = ImageDraw.Draw(canvas)
        ar, ag, ab = accent
        for i in range(5):
            frac = 1.0 - abs(i - 2) / 3.0
            c    = tuple(int(ch * frac) for ch in (ar, ag, ab))
            draw.line([(18 + i, 55), (18 + i, H - 55)], fill=c, width=1)

        # Left text
        scale   = W / 1000
        f_title = get_font("Bold",    int(36 * scale))
        f_feat  = get_font("Regular", int(21 * scale))
        f_dot   = get_font("SemiBold", int(21 * scale))

        pad = int(44 * scale)
        y   = int(H * 0.24)

        feat_col = tuple(max(c - 20, 0) for c in txt_col) if txt_col[0] > 180 \
                   else tuple(min(c + 20, 255) for c in txt_col)

        for line in textwrap.wrap(title.strip()[:80], width=17)[:3]:
            _shadow_text(draw, (pad, y), line, f_title, txt_col)
            y += int(46 * scale)

        y += int(22 * scale)

        for feat in features[:3]:
            clean = _clean_feat(feat)[:40]
            if not clean:
                continue
            _shadow_text(draw, (pad, y + 1),              "•",   f_dot, accent)
            _shadow_text(draw, (pad + int(24 * scale), y), clean, f_feat, feat_col)
            y += int(34 * scale)

        buf = io.BytesIO()
        canvas.save(buf, "PNG", optimize=True)
        return buf.getvalue()


# ─── 3. Hero Center ───────────────────────────────────────────────────────────

class HeroCenter(_Layout):
    """
    Maximally large product, thin gradient at bottom, minimal text.
    Let the product breathe.
    """
    name = "hero_center"

    def render(self, bg_bytes, product_bytes, title, features, colors_str):
        bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB").resize((W, H))

        # Product — very large, slightly above center
        canvas = _place_product(bg, product_bytes,
                                center_x=W // 2, center_y=int(H * 0.42),
                                max_w=int(W * 0.84), max_h=int(H * 0.70),
                                shadow_opacity=55)

        return _bottom_text(canvas, title, features[:2], colors_str,
                            fade_start=0.76, max_alpha=210, max_features=2)


# ─── 4. Premium Asymmetric ────────────────────────────────────────────────────

class PremiumAsymmetric(_Layout):
    """
    Product upper-right, bold title + features bottom-left.
    Diagonal gradient overlay — dynamic, modern composition.
    """
    name = "premium_asymmetric"

    def render(self, bg_bytes, product_bytes, title, features, colors_str):
        parsed   = _parse_colors(colors_str)
        dark_col = _fade_color(parsed)
        accent   = parsed[2]
        txt_col  = _text_color(dark_col)

        bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB").resize((W, H))

        # Diagonal overlay — stronger at bottom-left
        overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d       = ImageDraw.Draw(overlay)
        r, g, b = dark_col
        for y in range(H):
            # Heavier toward bottom, fades to right
            t     = y / H
            alpha = int((0.4 + t * 0.5) * 155)
            d.line([(0, y), (int(W * 0.58), y)], fill=(r, g, b, alpha))
        canvas = Image.alpha_composite(bg.convert("RGBA"), overlay).convert("RGB")

        # Product — upper-right
        canvas = _place_product(canvas, product_bytes,
                                center_x=int(W * 0.65), center_y=int(H * 0.36),
                                max_w=int(W * 0.58), max_h=int(H * 0.57),
                                shadow_opacity=65)

        # Text — lower-left
        draw = ImageDraw.Draw(canvas)
        scale   = W / 1000
        f_title = get_font("Bold",    int(40 * scale))
        f_feat  = get_font("Regular", int(22 * scale))
        f_dot   = get_font("SemiBold", int(22 * scale))

        pad = int(38 * scale)
        y   = int(H * 0.60)

        feat_col = tuple(max(c - 22, 0) for c in txt_col) if txt_col[0] > 180 \
                   else tuple(min(c + 22, 255) for c in txt_col)

        for line in textwrap.wrap(title.strip()[:80], width=22)[:2]:
            _shadow_text(draw, (pad, y), line, f_title, txt_col)
            y += int(50 * scale)

        y += int(10 * scale)

        for feat in features[:3]:
            clean = _clean_feat(feat)[:50]
            if not clean:
                continue
            _shadow_text(draw, (pad, y + 1),               "•",   f_dot, accent)
            _shadow_text(draw, (pad + int(26 * scale), y), clean,  f_feat, feat_col)
            y += int(35 * scale)

        buf = io.BytesIO()
        canvas.save(buf, "PNG", optimize=True)
        return buf.getvalue()


# ─── 5. Minimal Clean ────────────────────────────────────────────────────────

class MinimalClean(_Layout):
    """
    Bright/neutral background, centered product, clean bottom zone with
    a subtle separator line. Elegant, works best for beauty and accessories.
    """
    name = "minimal_clean"

    def render(self, bg_bytes, product_bytes, title, features, colors_str):
        parsed  = _parse_colors(colors_str)
        # Use the lightest color for the overlay
        light   = max(parsed, key=_lum)
        accent  = parsed[2]

        bg = Image.open(io.BytesIO(bg_bytes)).convert("RGB").resize((W, H))

        # Soft bright overlay to unify colors
        r, g, b = light
        mix     = tuple(min(255, int(c + (255 - c) * 0.30)) for c in (r, g, b))
        bright  = Image.new("RGBA", (W, H), (*mix, 70))
        canvas  = Image.alpha_composite(bg.convert("RGBA"), bright).convert("RGB")

        # Product — upper-center
        canvas = _place_product(canvas, product_bytes,
                                center_x=W // 2, center_y=int(H * 0.39),
                                max_w=int(W * 0.68), max_h=int(H * 0.62),
                                shadow_opacity=50)

        # Thin accent separator line
        draw  = ImageDraw.Draw(canvas)
        sep_y = int(H * 0.72)
        ar, ag, ab = accent
        draw.line([(38, sep_y), (W - 38, sep_y)], fill=(ar, ag, ab), width=2)

        return _bottom_text(canvas, title, features, colors_str,
                            fade_start=0.73, max_alpha=195)


# ─── Registry ─────────────────────────────────────────────────────────────────

_LAYOUTS = [
    LuxuryDark(),
    EditorialSplit(),
    HeroCenter(),
    PremiumAsymmetric(),
    MinimalClean(),
]


def get_layout(index: int) -> _Layout:
    """Return layout for concept index 1-5. Cycles if out of range."""
    return _LAYOUTS[(index - 1) % len(_LAYOUTS)]
