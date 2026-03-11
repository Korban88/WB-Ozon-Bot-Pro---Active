"""
Card renderer — premium visual-only cards, 800×1000 (4:5) canvas.

CORE RULE: NO text overlay. Cards are clean premium visuals.
Text (copy, headlines, features) is delivered separately as Ad Copy Pack.

Pipeline:
  1. Extract colors FROM product image
  2. Cut product background (Pillow / rembg)
  3. Build canvas from scene or gradient fallback (full-height)
  4. Composite product as immutable RGBA layer (scale/position/shadow only)
  5. Add contact shadow (ground anchoring) + ambient shadow

Product integrity:
  - Product pixels are NEVER modified after cutout
  - Only alpha channel, scale, position, and shadow are applied
  - Product is always the top layer

Visual compositing improvements:
  - Contact shadow: elliptical ground shadow anchors product to surface
  - Drop shadow: soft directional shadow for depth
  - Edge softening: slight blur on cutout edges for natural blending
  - Gradient vignette: subtle darkening at canvas edges for professional look
"""

import io

from PIL import Image, ImageDraw, ImageFilter

from services.card_types import CANVAS_LAYOUT
from services.color_extractor import extract_dominant_colors
from services.product_cutout import cutout_product

import logging
log = logging.getLogger(__name__)


# ─── Color helpers ────────────────────────────────────────────────────────────

def _lum(c: tuple) -> float:
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def _darkest(parsed: list) -> tuple:
    return sorted(parsed, key=_lum)[0]


# ─── Canvas assembly ──────────────────────────────────────────────────────────

def _resize_fill(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Resize and center-crop to fill target dimensions."""
    sw, sh = img.size
    scale = max(target_w / sw, target_h / sh)
    nw, nh = int(sw * scale), int(sh * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    x = (nw - target_w) // 2
    y = (nh - target_h) // 2
    return img.crop((x, y, x + target_w, y + target_h))


def _make_canvas(scene_img: Image.Image, card_type: str) -> Image.Image:
    """
    Build 800×1000 full-height canvas from scene image.
    Scene fills the entire canvas — no text panel.
    """
    cw, ch, scene_h, _ = CANVAS_LAYOUT[card_type]
    scene = scene_img.convert("RGB")
    scene = _resize_fill(scene, cw, ch)
    return scene


def _gradient_from_palette(palette: list, w: int, h: int) -> Image.Image:
    """Create gradient image from product color palette (fallback when no scene)."""
    dark  = _darkest(palette)

    top = tuple(min(255, int(c * 1.25)) for c in dark)
    mid = dark
    bot = tuple(max(0, int(c * 0.65)) for c in dark)

    img  = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        if t < 0.5:
            t2 = t * 2
            color = tuple(int(top[i] + (mid[i] - top[i]) * t2) for i in range(3))
        else:
            t2 = (t - 0.5) * 2
            color = tuple(int(mid[i] + (bot[i] - mid[i]) * t2) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)
    return img


# ─── Shadow helpers ───────────────────────────────────────────────────────────

def _add_contact_shadow(
    canvas_rgba: Image.Image,
    px: int,
    py: int,
    prod_w: int,
    prod_h: int,
) -> Image.Image:
    """
    Add elliptical contact shadow on the surface directly below product.
    Creates a realistic 'ground anchoring' effect — product looks placed, not floating.
    """
    sh_w = int(prod_w * 0.72)
    sh_h = int(prod_h * 0.06)
    sh_h = max(sh_h, 12)

    # Shadow center: bottom of product, slightly inside
    sh_x = px + (prod_w - sh_w) // 2
    sh_y = py + prod_h - sh_h // 2

    shadow = Image.new("RGBA", canvas_rgba.size, (0, 0, 0, 0))
    draw   = ImageDraw.Draw(shadow)
    draw.ellipse(
        [sh_x, sh_y, sh_x + sh_w, sh_y + sh_h],
        fill=(0, 0, 0, 90),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    return Image.alpha_composite(canvas_rgba, shadow)


def _add_drop_shadow(
    canvas_rgba: Image.Image,
    product: Image.Image,
    px: int,
    py: int,
) -> Image.Image:
    """
    Soft directional drop shadow behind product (derived from product alpha).
    Gives depth and lifts product off the background.
    """
    if product.mode != "RGBA":
        return canvas_rgba

    alpha = product.split()[3]
    # Reduce shadow opacity for subtlety
    shadow_alpha = alpha.point(lambda p: int(p * 55 / 255))

    dark = Image.new("RGBA", product.size, (5, 5, 15, 0))
    dark.putalpha(shadow_alpha)

    # Blur and offset for directional shadow
    dark_blurred = dark.filter(ImageFilter.GaussianBlur(radius=20))

    shadow_layer = Image.new("RGBA", canvas_rgba.size, (0, 0, 0, 0))
    shadow_layer.paste(dark_blurred, (px + 16, py + 20), dark_blurred)

    return Image.alpha_composite(canvas_rgba, shadow_layer)


def _soften_cutout_edges(cutout: Image.Image, radius: float = 1.2) -> Image.Image:
    """
    Slightly blur the alpha channel edges of a cutout for natural blending.
    Product RGB pixels remain unchanged — only alpha edge is softened.
    """
    if cutout.mode != "RGBA":
        return cutout
    r, g, b, a = cutout.split()
    a_soft = a.filter(ImageFilter.GaussianBlur(radius=radius))
    return Image.merge("RGBA", (r, g, b, a_soft))


def _add_vignette(canvas: Image.Image, strength: float = 0.18) -> Image.Image:
    """
    Subtle vignette (dark edges) for professional look.
    Strength 0.0–1.0, default 0.18 is barely noticeable but adds polish.
    """
    w, h = canvas.size
    vig  = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(vig)

    steps = 40
    for i in range(steps):
        t       = i / steps
        alpha   = int(255 * strength * (1 - t) ** 2.5)
        margin  = int(min(w, h) * 0.5 * t)
        draw.rectangle([margin, margin, w - margin, h - margin], fill=(0, 0, 0, 0))

    # Radial vignette via ellipse layers from outside in
    vig2 = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw2 = ImageDraw.Draw(vig2)
    for i in range(steps):
        t     = i / steps
        alpha = int(255 * strength * (1 - t) ** 2.2)
        pad   = int(max(w, h) * 0.5 * t)
        draw2.ellipse([-pad, -pad, w + pad, h + pad], fill=(0, 0, 0, alpha))

    vig2 = vig2.filter(ImageFilter.GaussianBlur(radius=30))

    c_rgba = canvas.convert("RGBA")
    c_rgba = Image.alpha_composite(c_rgba, vig2)
    return c_rgba.convert("RGB")


# ─── Product compositing ──────────────────────────────────────────────────────

def _place_product_cutout(
    canvas: Image.Image,
    cutout: Image.Image,
    card_type: str,
) -> Image.Image:
    """
    Composite product cutout (RGBA) onto full-height canvas.
    Product pixels are NEVER modified — only scaled and positioned.

    Shadow layers (contact + drop) are derived from product alpha.
    Vertical position varies by card type for optimal composition.
    """
    cw, ch = canvas.size

    # Size limits by card type
    size_limits = {
        "hero":      (0.65, 0.78),
        "lifestyle": (0.60, 0.72),
        "social":    (0.62, 0.74),
        "editorial": (0.58, 0.76),
        "detail":    (0.72, 0.88),
    }
    max_w_frac, max_h_frac = size_limits.get(card_type, (0.65, 0.78))

    MAX_W = int(cw * max_w_frac)
    MAX_H = int(ch * max_h_frac)

    prod = cutout.copy()
    prod.thumbnail((MAX_W, MAX_H), Image.LANCZOS)

    # Soften cutout edges for natural blending
    prod = _soften_cutout_edges(prod, radius=1.0)

    # Horizontal: always centered
    px = (cw - prod.width) // 2

    # Vertical offset by card type
    v_offsets = {
        "hero":      -55,
        "lifestyle":   0,
        "social":     25,
        "editorial": -75,
        "detail":      0,
    }
    v_off = v_offsets.get(card_type, 0)
    py = max(20, (ch - prod.height) // 2 + v_off)

    c_rgba = canvas.convert("RGBA")

    # 1. Drop shadow (directional, behind product)
    c_rgba = _add_drop_shadow(c_rgba, prod, px, py)

    # 2. Contact shadow (ground anchoring, below product)
    c_rgba = _add_contact_shadow(c_rgba, px, py, prod.width, prod.height)

    # 3. Paste product on top — immutable pixels
    if prod.mode == "RGBA":
        c_rgba.paste(prod, (px, py), mask=prod.split()[3])
    else:
        c_rgba.paste(prod, (px, py))

    return c_rgba.convert("RGB")


def _place_product_fallback(canvas: Image.Image, product_bytes: bytes,
                            card_type: str) -> Image.Image:
    """Fallback: place raw product photo (with background) when cutout fails."""
    cw, ch = canvas.size
    try:
        prod = Image.open(io.BytesIO(product_bytes)).convert("RGBA")
        prod.thumbnail((int(cw * 0.65), int(ch * 0.78)), Image.LANCZOS)

        px = (cw - prod.width) // 2
        py = max(20, (ch - prod.height) // 2 - 40)

        c_rgba = canvas.convert("RGBA")

        # Contact shadow для fallback тоже
        c_rgba = _add_contact_shadow(c_rgba, px, py, prod.width, prod.height)

        c_rgba.paste(prod, (px, py), mask=prod.split()[3])
        return c_rgba.convert("RGB")
    except Exception:
        return canvas


# ─── Public API ───────────────────────────────────────────────────────────────

def render_card(
    card_type:     str,
    scene_bytes:   bytes | None,
    product_bytes: bytes,
    **kwargs,
) -> bytes:
    """
    Assemble a premium 800×1000 (4:5) visual card — NO text overlay.

    Pipeline:
      1. Extract colors FROM product image
      2. Build full-height canvas (AI scene or gradient fallback)
      3. Composite product as immutable layer (scale/position/shadow only)
      4. Contact shadow + drop shadow for realistic placement
      5. Subtle vignette for professional polish

    scene_bytes  — AI-generated empty scene or None (gradient fallback).
    product_bytes — original product photo (source of truth, never regenerated).

    All extra kwargs are accepted but intentionally not used —
    text lives in the Ad Copy Pack, not on images.
    """
    # 1. Extract colors from product for gradient fallback
    try:
        palette = extract_dominant_colors(product_bytes, n_colors=3)
    except Exception:
        palette = [(60, 60, 80), (40, 40, 55), (100, 80, 60)]

    cw, ch, _, _ = CANVAS_LAYOUT.get(card_type, CANVAS_LAYOUT["hero"])

    # 2. Build canvas
    if scene_bytes:
        try:
            scene_img = Image.open(io.BytesIO(scene_bytes))
        except Exception as e:
            log.warning("Scene load failed: %s, using gradient", e)
            scene_img = _gradient_from_palette(palette, cw * 2, ch * 2)
    else:
        scene_img = _gradient_from_palette(palette, cw * 2, ch * 2)

    canvas = _make_canvas(scene_img, card_type)

    # 3. Composite product (pixels immutable) + shadows
    try:
        cutout = cutout_product(product_bytes)
        canvas = _place_product_cutout(canvas, cutout, card_type)
    except Exception as e:
        log.warning("Cutout composite failed: %s, using fallback", e)
        canvas = _place_product_fallback(canvas, product_bytes, card_type)

    # 4. Subtle vignette
    try:
        canvas = _add_vignette(canvas, strength=0.15)
    except Exception:
        pass

    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    return buf.getvalue()
