"""
Product background removal.

Product pixels are NEVER modified — only background becomes transparent.

Primary: Pillow flood-fill + edge softening (no memory overhead, VPS-safe).
Optional: rembg for cleaner cutouts (requires ~500MB RAM).

Flood-fill approach (improved over corner-sampling):
  1. Sample background color from all 4 corners + edge midpoints
  2. Create distance map for each pixel vs background color
  3. Apply threshold to get initial alpha mask
  4. Refine edges with soft blur for natural blending
"""
import io
import logging

from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

try:
    from rembg import remove as _rembg_remove
    _REMBG = True
    logger.info("rembg available for background removal")
except ImportError:
    _REMBG = False
    logger.info("rembg not installed — using Pillow flood-fill (VPS mode)")


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
    Improved background removal:
      1. Sample background from multiple edge points (not just corners)
      2. Build per-pixel distance to background color
      3. Apply adaptive threshold
      4. Soften edges for natural compositing
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = img.size

    # Sample from 12 edge points for more reliable background detection
    sample_pts = [
        (0, 0),          (w // 4, 0),     (w // 2, 0),    (w * 3 // 4, 0),    (w - 1, 0),
        (0, h // 2),                                                             (w - 1, h // 2),
        (0, h - 1),      (w // 4, h - 1), (w // 2, h - 1),(w * 3 // 4, h - 1),(w - 1, h - 1),
    ]
    samples = [img.getpixel(p)[:3] for p in sample_pts]

    # Background color = weighted average (corner points get more weight)
    corner_pts = [(0,0), (w-1,0), (0,h-1), (w-1,h-1)]
    corners = [img.getpixel(p)[:3] for p in corner_pts]

    # If corners are consistent (all similar), use corner average
    def _color_spread(colors):
        diffs = []
        for i in range(3):
            vals = [c[i] for c in colors]
            diffs.append(max(vals) - min(vals))
        return max(diffs)

    if _color_spread(corners) < 30:
        # Consistent corners — probably uniform studio background
        bg = tuple(sum(c[i] for c in corners) // 4 for i in range(3))
    else:
        # Mixed corners — use all edge samples
        bg = tuple(sum(c[i] for c in samples) // len(samples) for i in range(3))

    # Build alpha mask
    threshold = 40
    data = list(img.getdata())
    alpha_data = []
    for r, g, b, a in data:
        dist = ((r - bg[0])**2 + (g - bg[1])**2 + (b - bg[2])**2) ** 0.5
        if dist < threshold:
            alpha_data.append(0)
        elif dist < threshold * 1.8:
            # Transition zone — partial transparency for smooth edges
            t = (dist - threshold) / (threshold * 0.8)
            alpha_data.append(int(255 * min(1.0, t)))
        else:
            alpha_data.append(255)

    # Apply alpha mask
    alpha_img = Image.new("L", (w, h))
    alpha_img.putdata(alpha_data)

    # Soften edges slightly for natural blending with any background
    alpha_soft = alpha_img.filter(ImageFilter.GaussianBlur(radius=1.0))

    result = img.copy()
    result.putalpha(alpha_soft)
    return result
