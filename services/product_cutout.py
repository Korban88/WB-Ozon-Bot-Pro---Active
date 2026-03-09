"""
Product background removal.

Product pixels are NEVER modified — only background becomes transparent.
Primary: Pillow corner-sampling (no memory overhead, VPS-safe).
Optional: rembg for cleaner cutouts (requires ~500MB RAM).
"""
import io
import logging

from PIL import Image

logger = logging.getLogger(__name__)

try:
    from rembg import remove as _rembg_remove
    _REMBG = True
    logger.info("rembg available for background removal")
except ImportError:
    _REMBG = False
    logger.info("rembg not installed — using Pillow corner-sampling (VPS mode)")


def cutout_product(image_bytes: bytes) -> Image.Image:
    """
    Remove background from product photo.
    Returns RGBA Image with transparent background.
    Product pixels are read-only — only alpha channel is modified.
    """
    if _REMBG:
        try:
            result = _rembg_remove(image_bytes)
            return Image.open(io.BytesIO(result)).convert("RGBA")
        except Exception as e:
            logger.warning(f"rembg failed: {e}, falling back to Pillow")

    return _pillow_cutout(image_bytes)


def _pillow_cutout(image_bytes: bytes) -> Image.Image:
    """
    Sample background color from 8 edge points, make matching pixels transparent.
    Works well for studio (white/gray/uniform) backgrounds.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size

    sample_pts = [
        (0, 0),      (w // 2, 0),      (w - 1, 0),
        (0, h // 2),                    (w - 1, h // 2),
        (0, h - 1),  (w // 2, h - 1),  (w - 1, h - 1),
    ]
    samples = [img.getpixel(p)[:3] for p in sample_pts]
    bg = tuple(sum(c[i] for c in samples) // len(samples) for i in range(3))

    threshold = 45
    data = img.getdata()
    new_data = [
        (r, g, b, 0)
        if ((r - bg[0])**2 + (g - bg[1])**2 + (b - bg[2])**2) ** 0.5 < threshold
        else (r, g, b, a)
        for r, g, b, a in data
    ]
    img.putdata(new_data)
    return img
