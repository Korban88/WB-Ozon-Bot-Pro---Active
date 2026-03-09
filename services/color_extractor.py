"""Extract dominant colors from product image.
Colors come from the product — never random or AI-generated."""

import io
from collections import Counter

from PIL import Image


def extract_dominant_colors(
    image_bytes: bytes, n_colors: int = 3
) -> list[tuple[int, int, int]]:
    """
    Extract n dominant colors from product image.
    Ignores near-white/near-black backgrounds.
    Returns list of (R, G, B) tuples.
    """
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize((80, 80), Image.LANCZOS)
    pixels = list(img.getdata())

    # Quantize to 24-step grid to reduce noise
    quantized = [(r // 24 * 24, g // 24 * 24, b // 24 * 24) for r, g, b in pixels]
    counter = Counter(quantized)

    # Filter near-white (background) and near-black
    filtered = [
        (color, count) for color, count in counter.items()
        if not (all(c > 215 for c in color) or all(c < 40 for c in color))
    ]
    if not filtered:
        filtered = list(counter.most_common(n_colors * 3))

    filtered.sort(key=lambda x: -x[1])
    colors = [color for color, _ in filtered[:n_colors]]

    while len(colors) < n_colors:
        colors.append((128, 128, 128))

    return colors


def get_color_description(colors: list[tuple[int, int, int]]) -> str:
    """Natural language description for scene generation prompts."""
    descriptions = []
    for c in colors[:2]:
        d = _describe_rgb(*c)
        if d not in descriptions:
            descriptions.append(d)
    return " and ".join(descriptions)


def _describe_rgb(r: int, g: int, b: int) -> str:
    rf, gf, bf = r / 255, g / 255, b / 255
    mx, mn = max(rf, gf, bf), min(rf, gf, bf)
    df = mx - mn
    s = 0 if mx == 0 else df / mx
    v = mx

    if s < 0.15:
        if v > 0.85: return "light neutral"
        if v < 0.20: return "deep dark"
        return "neutral gray"

    if df == 0:    h = 0
    elif mx == rf: h = 60 * (((gf - bf) / df) % 6)
    elif mx == gf: h = 60 * ((bf - rf) / df + 2)
    else:          h = 60 * ((rf - gf) / df + 4)

    if h < 20:  return "warm red"
    if h < 45:  return "warm orange"
    if h < 70:  return "golden yellow"
    if h < 150: return "fresh green"
    if h < 200: return "cool teal"
    if h < 260: return "cool blue"
    if h < 300: return "purple violet"
    if h < 340: return "warm pink"
    return "warm red"
