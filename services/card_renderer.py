"""
Card renderer — premium visual-only cards, 800×1000 (4:5) canvas.

CORE RULE: NO text overlay. Cards are clean premium visuals.
Text (copy, headlines, features) is delivered separately as Ad Copy Pack.

Pipeline:
  1. Extract colors FROM product image
  2. Cut product background (Pillow / rembg)
  3. Build canvas from scene or gradient fallback (full-height)
  4. Composite product as immutable RGBA layer (scale/position/shadow only)

Product integrity:
  - Product pixels are NEVER modified after cutout
  - Only alpha channel, scale, position, and shadow are applied
  - Product is always the top layer
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

    # Rich gradient: darker variant at bottom
    top = tuple(min(255, int(c * 1.25)) for c in dark)
    mid = dark
    bot = tuple(max(0, int(c * 0.70)) for c in dark)

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


# ─── Product compositing ──────────────────────────────────────────────────────

def _place_product_cutout(
    canvas: Image.Image,
    cutout: Image.Image,
    card_type: str,
) -> Image.Image:
    """
    Composite product cutout (RGBA) onto full-height canvas.
    Product pixels are NEVER modified — only scaled and positioned.
    Shadow is derived from product alpha.

    Vertical position varies by card type for optimal composition:
      hero      — slightly above center (premium look)
      lifestyle — center, scene breathes around it
      social    — slightly below center (ground feeling)
      editorial — above center, dramatic
      detail    — center-large fill
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

    # Horizontal: always centered
    px = (cw - prod.width) // 2

    # Vertical: offset by card type (negative = up from canvas center)
    v_offsets = {
        "hero":      -60,
        "lifestyle":   0,
        "social":     30,
        "editorial": -80,
        "detail":      0,
    }
    v_off = v_offsets.get(card_type, 0)
    py = max(20, (ch - prod.height) // 2 + v_off)

    # Shadow from alpha channel (product pixels immutable)
    shadow_layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    if prod.mode == "RGBA":
        alpha = prod.split()[3]
        shadow_alpha = alpha.point(lambda p: int(p * 65 / 255))
        dark = Image.new("RGBA", prod.size, (10, 10, 15, 0))
        dark.putalpha(shadow_alpha)
        dark_blurred = dark.filter(ImageFilter.GaussianBlur(radius=22))
        shadow_layer.paste(dark_blurred, (px + 18, py + 22), dark_blurred)

    c_rgba = canvas.convert("RGBA")
    c_rgba = Image.alpha_composite(c_rgba, shadow_layer)

    # Paste product — always on top
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

        shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        s_d    = ImageDraw.Draw(shadow)
        s_d.ellipse(
            [px + prod.width // 6,     py + prod.height - 10,
             px + prod.width * 5 // 6, py + prod.height + 35],
            fill=(0, 0, 0, 50)
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(18))

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
    **kwargs,
) -> bytes:
    """
    Assemble a premium 800×1000 (4:5) visual card — NO text overlay.

    Pipeline:
      1. Extract colors FROM product image
      2. Build full-height canvas (AI scene or gradient fallback)
      3. Composite product as immutable layer (scale/position/shadow only)

    scene_bytes  — AI-generated empty scene or None (gradient fallback).
    product_bytes — original product photo (source of truth, never regenerated).

    All extra kwargs (title, features, subtitle, colors_str) are accepted but
    intentionally not used — text lives in the Ad Copy Pack, not on images.
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

    # 3. Composite product (pixels immutable)
    try:
        cutout = cutout_product(product_bytes)
        canvas = _place_product_cutout(canvas, cutout, card_type)
    except Exception as e:
        log.warning("Cutout composite failed: %s, using fallback", e)
        canvas = _place_product_fallback(canvas, product_bytes, card_type)

    buf = io.BytesIO()
    canvas.save(buf, "PNG", optimize=True)
    return buf.getvalue()
