"""
Generate styled card backgrounds using OpenAI gpt-image-1.
Generates EMPTY BACKGROUND ONLY — product and text are added separately.

Fallback: Pillow gradient background when no API key.
"""

import base64
import io
import re
import time

import aiohttp
from PIL import Image, ImageDraw

import config
from logger_setup import log, log_ai_call

_OPENAI_GEN_URL = "https://api.openai.com/v1/images/generations"
_TIMEOUT = 90

_MARKETPLACE = {"wb": "Wildberries", "ozon": "Ozon"}
_CATEGORY = {
    "clothing":    "fashion & clothing",
    "electronics": "consumer electronics",
    "home":        "home goods & decor",
    "beauty":      "beauty & personal care",
    "accessories": "accessories",
    "other":       "consumer goods",
}


def _build_background_prompt(concept: dict, marketplace: str, category: str) -> str:
    mp  = _MARKETPLACE.get(marketplace, marketplace)
    cat = _CATEGORY.get(category, category)

    name        = concept.get("name",        "")
    colors      = concept.get("colors",      "")
    composition = concept.get("composition", "")

    return (
        f"Professional marketplace product card BACKGROUND for {mp}, {cat} category.\n"
        f"Design concept: «{name}»\n"
        f"Color palette: {colors}\n"
        f"Atmosphere: {composition}\n\n"
        f"STRICT RULES — follow exactly:\n"
        f"• This is a BACKGROUND SCENE ONLY — no product, no object, no person, nothing\n"
        f"• The central area (center 60%) must be clean and empty — product will be placed here\n"
        f"• Bottom third: slightly darker/atmospheric — text panel will overlay this area\n"
        f"• Decorative elements only at edges/corners: soft bokeh, light rays, texture, gradients\n"
        f"• ABSOLUTELY NO text, letters, numbers, logos, watermarks anywhere\n"
        f"• Quality: premium commercial photography, luxury brand aesthetics\n"
        f"• Style: modern marketplace top-seller card, clean, expensive-looking\n"
        f"• The background should make a product stand out beautifully when placed on top"
    )


async def generate_background(
    concept: dict,
    marketplace: str,
    category: str,
    user_id: int,
    username: str | None,
    concept_index: int = 0,
) -> bytes | None:
    """
    Generate a styled empty background via gpt-image-1.
    Returns PNG bytes, or None on failure.
    """
    if not config.OPENAI_API_KEY:
        return None

    prompt  = _build_background_prompt(concept, marketplace, category)
    service = f"openai_bg/concept_{concept_index}"
    start   = time.monotonic()

    try:
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type":  "application/json",
        }
        payload = {
            "model":  config.OPENAI_IMAGE_MODEL,
            "prompt": prompt,
            "n":      1,
            "size":   "1024x1024",
        }
        timeout = aiohttp.ClientTimeout(total=_TIMEOUT)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(_OPENAI_GEN_URL, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"OpenAI HTTP {resp.status}: {body[:200]}")
                data = await resp.json()

        item = data["data"][0]
        if "b64_json" in item:
            image_bytes = base64.b64decode(item["b64_json"])
        elif "url" in item:
            async with aiohttp.ClientSession() as session:
                async with session.get(item["url"]) as r:
                    image_bytes = await r.read()
        else:
            raise RuntimeError(f"Unexpected OpenAI response: {list(item.keys())}")

        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=True, duration_ms=elapsed)
        log.info("Background generated for concept %d (%dms)", concept_index, elapsed)
        return image_bytes

    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=False,
                    duration_ms=elapsed, error=str(exc))
        log.warning("Background generation failed for concept %d: %s", concept_index, exc)
        return None


def pillow_gradient_background(colors_str: str, w: int = 1000, h: int = 1000) -> bytes:
    """
    Fallback: create a gradient background from concept colors using Pillow.
    Result: vertical gradient + decorative accent stripe at top.
    """
    hexes  = re.findall(r'#([0-9A-Fa-f]{6})', colors_str)
    parsed = [tuple(int(hx[i:i+2], 16) for i in (0, 2, 4)) for hx in hexes[:3]]

    bg     = parsed[0] if parsed          else (240, 240, 248)
    dark   = parsed[1] if len(parsed) > 1 else tuple(max(0, c - 50) for c in bg)
    accent = parsed[2] if len(parsed) > 2 else (200, 150, 50)

    # Make "dark" end color: blend bg toward dark
    end = tuple(int(bg[i] * 0.7 + dark[i] * 0.3) for i in range(3))

    img  = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)

    # Vertical gradient
    for y in range(h):
        t = y / h
        color = tuple(int(bg[i] + (end[i] - bg[i]) * t) for i in range(3))
        draw.line([(0, y), (w, y)], fill=color)

    # Top accent stripe
    draw.rectangle([0, 0, w, 7], fill=accent)

    # Subtle vignette hint at bottom
    for y in range(h - 120, h):
        t = (y - (h - 120)) / 120
        alpha_color = tuple(max(0, int(c * (1 - t * 0.35))) for c in end)
        draw.line([(0, y), (w, y)], fill=alpha_color)

    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
