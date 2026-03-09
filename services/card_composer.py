"""
Card composer: assembles the final product card from 3 layers.

Layer 1 — Background (background_gen.py):
    Styled empty scene from gpt-image-1 or Pillow gradient fallback.

Layer 2 — Product (this module):
    - Remove product background using rembg (if available)
    - Add realistic drop shadow
    - Composite product onto background in the hero zone

Layer 3 — Text overlay (card_renderer.py):
    - Semi-transparent panel with concept colors
    - Title, feature bullets, accent elements via Pillow
"""

import io

from PIL import Image, ImageFilter

from logger_setup import log
from services.card_renderer import overlay_text_on_image

# ── rembg: background removal ─────────────────────────────────────────────────
try:
    from rembg import remove as _rembg_remove
    REMBG_AVAILABLE = True
    log.info("rembg available — product background removal enabled")
except ImportError:
    REMBG_AVAILABLE = False
    log.warning("rembg not installed — using original product photo without cutout")

CARD_W = 1000
CARD_H = 1000

# Product occupies top 62% of card (bottom 38% is reserved for text panel)
_TEXT_PANEL_RATIO = 0.38
_PRODUCT_ZONE_H   = int(CARD_H * (1 - _TEXT_PANEL_RATIO))  # 620px
_MAX_PRODUCT_W    = int(CARD_W * 0.72)                      # 720px
_MAX_PRODUCT_H    = int(_PRODUCT_ZONE_H * 0.88)             # 545px


def _cut_background(photo_bytes: bytes) -> Image.Image | None:
    """
    Remove product background using rembg.
    Returns RGBA Image with transparent background, or None if unavailable/failed.
    """
    if not REMBG_AVAILABLE:
        return None
    try:
        out = _rembg_remove(photo_bytes)
        return Image.open(io.BytesIO(out)).convert("RGBA")
    except Exception as exc:
        log.warning("rembg background removal failed: %s", exc)
        return None


def _add_drop_shadow(
    product: Image.Image,
    offset: tuple[int, int] = (14, 18),
    blur:   int = 30,
    opacity: int = 100,
) -> Image.Image:
    """
    Add a realistic drop shadow behind a cutout RGBA product image.
    Returns a new RGBA image (larger) with shadow + product composited.
    """
    pad = blur + max(abs(offset[0]), abs(offset[1])) + 8
    canvas_w = product.width  + pad * 2
    canvas_h = product.height + pad * 2

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))

    # Shadow: fill product shape with dark color, then blur
    shadow = Image.new("RGBA", product.size, (0, 0, 0, opacity))
    shadow.putalpha(product.split()[3])  # use product alpha as shadow mask
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))

    shadow_pos  = (pad + offset[0], pad + offset[1])
    product_pos = (pad, pad)

    canvas.paste(shadow,  shadow_pos,  shadow)
    canvas.paste(product, product_pos, product)

    return canvas


def _soft_frame(product_img: Image.Image, radius: int = 12) -> Image.Image:
    """
    Add a soft white rounded frame behind the product (used when no cutout).
    Makes the product look clean on any background.
    """
    try:
        from PIL import ImageDraw
        pad = 16
        frame_w = product_img.width  + pad * 2
        frame_h = product_img.height + pad * 2
        frame = Image.new("RGBA", (frame_w, frame_h), (0, 0, 0, 0))
        draw  = ImageDraw.Draw(frame)
        draw.rounded_rectangle([0, 0, frame_w - 1, frame_h - 1], radius=radius, fill=(255, 255, 255, 230))
        frame.paste(product_img.convert("RGBA"), (pad, pad))
        return frame
    except Exception:
        return product_img.convert("RGBA")


def compose_card(
    background_bytes: bytes,
    product_bytes:    bytes,
    title:            str,
    features:         list[str],
    colors_str:       str,
) -> bytes:
    """
    Assemble the final product card from 3 layers.

    Args:
        background_bytes: styled background PNG (from background_gen)
        product_bytes:    original product photo from Telegram
        title:            product title (from generated card)
        features:         list of feature strings
        colors_str:       concept color palette string with hex codes

    Returns:
        Final card PNG as bytes (1000×1000)
    """
    # ── Layer 1: Background ──────────────────────────────────────────────────
    bg = Image.open(io.BytesIO(background_bytes)).convert("RGBA")
    bg = bg.resize((CARD_W, CARD_H), Image.LANCZOS)

    # ── Layer 2: Product compositing ─────────────────────────────────────────
    product_rgba = _cut_background(product_bytes)
    has_cutout   = product_rgba is not None

    if not has_cutout:
        # No rembg — use original photo with a soft white frame
        product_rgba = Image.open(io.BytesIO(product_bytes)).convert("RGBA")
        product_rgba.thumbnail((_MAX_PRODUCT_W, _MAX_PRODUCT_H), Image.LANCZOS)
        product_layer = _soft_frame(product_rgba)
        product_layer = _add_drop_shadow(product_layer, offset=(8, 10), blur=20, opacity=60)
    else:
        # Have cutout — resize and add proper drop shadow
        product_rgba.thumbnail((_MAX_PRODUCT_W, _MAX_PRODUCT_H), Image.LANCZOS)
        product_layer = _add_drop_shadow(product_rgba)

    # Center horizontally; place in upper portion of product zone
    px = (CARD_W - product_layer.width) // 2
    py = max(15, (_PRODUCT_ZONE_H - product_layer.height) // 2 - 15)

    canvas = bg.copy()
    canvas.paste(product_layer, (px, py), product_layer)

    # ── Layer 3: Text overlay ────────────────────────────────────────────────
    buf = io.BytesIO()
    canvas.convert("RGB").save(buf, "PNG")
    composed_bytes = buf.getvalue()

    return overlay_text_on_image(composed_bytes, title, features, colors_str)
