"""
Scene generator: gpt-image-1 /edits with product photo.

Unlike /generations (text-to-image), /edits receives the actual product photo
and generates a complete styled scene with the product naturally integrated —
unified lighting, coherent composition, product as part of the scene, not pasted on.

Text is added separately by card_renderer.overlay_text_premium().
"""

import base64
import io
import time

import aiohttp

import config
from logger_setup import log, log_ai_call

_EDITS_URL  = "https://api.openai.com/v1/images/edits"
_TIMEOUT    = 120

_MP = {"wb": "Wildberries", "ozon": "Ozon"}
_CAT = {
    "clothing":    "fashion & clothing",
    "electronics": "consumer electronics",
    "home":        "home goods & interior",
    "beauty":      "beauty & personal care",
    "accessories": "accessories & lifestyle",
    "other":       "consumer goods",
}


def _build_scene_prompt(concept: dict, marketplace: str, category: str) -> str:
    mp  = _MP.get(marketplace,  marketplace)
    cat = _CAT.get(category, category)

    name        = concept.get("name",        "")
    colors      = concept.get("colors",      "")
    composition = concept.get("composition", "")

    return (
        f"Create a professional marketplace product card for {mp}, {cat} category.\n"
        f"Design style: «{name}»\n"
        f"Color palette: {colors}\n"
        f"Visual concept: {composition}\n\n"

        f"PRODUCT INTEGRATION (most important rule):\n"
        f"• The product in the attached photo is the HERO of this card\n"
        f"• Render it naturally inside a {name.lower()} styled environment\n"
        f"• Unified lighting — the product and scene share the same light source\n"
        f"• The product must feel like it belongs in the scene, not placed on top\n"
        f"• Product: sharp, well-lit, prominent — upper-center of the composition\n\n"

        f"LAYOUT:\n"
        f"• Product + scene: upper ~75% of the image\n"
        f"• Bottom 22%: calm, slightly darker area — keep it clean (text will be added)\n"
        f"• Balanced negative space around the product\n\n"

        f"STRICT RULES:\n"
        f"• NO text, NO letters, NO numbers, NO logos, NO watermarks\n"
        f"• NO frames or borders around the product\n"
        f"• NO 'product sticker on background' effect\n"
        f"• Quality: luxury commercial photography, editorial level\n"
        f"• Must look like the work of a professional product photographer"
    )


async def generate_scene(
    concept:       dict,
    product_bytes: bytes,
    marketplace:   str,
    category:      str,
    user_id:       int,
    username:      str | None,
    concept_index: int = 0,
) -> bytes | None:
    """
    Generate a complete product card scene via gpt-image-1 /edits.
    Product photo is passed as input — integrated naturally into the scene.
    Returns PNG bytes or None on failure/unavailable.
    """
    if not config.OPENAI_API_KEY:
        return None

    prompt  = _build_scene_prompt(concept, marketplace, category)
    service = f"openai_scene/concept_{concept_index}"
    start   = time.monotonic()

    try:
        form = aiohttp.FormData()
        form.add_field("model",  config.OPENAI_IMAGE_MODEL)
        form.add_field("prompt", prompt)
        form.add_field("n",      "1")
        form.add_field("size",   "1024x1024")
        form.add_field(
            "image",
            io.BytesIO(product_bytes),
            filename     = "product.jpg",
            content_type = "image/jpeg",
        )

        headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
        timeout = aiohttp.ClientTimeout(total=_TIMEOUT)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(_EDITS_URL, headers=headers, data=form) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"OpenAI HTTP {resp.status}: {body[:300]}")
                data = await resp.json()

        item = data["data"][0]
        if "b64_json" in item:
            image_bytes = base64.b64decode(item["b64_json"])
        elif "url" in item:
            async with aiohttp.ClientSession() as session:
                async with session.get(item["url"]) as r:
                    image_bytes = await r.read()
        else:
            raise RuntimeError(f"Unexpected OpenAI response keys: {list(item.keys())}")

        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=True, duration_ms=elapsed)
        log.info("Scene generated for concept %d (%dms)", concept_index, elapsed)
        return image_bytes

    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=False,
                    duration_ms=elapsed, error=str(exc))
        log.warning("Scene generation failed for concept %d: %s", concept_index, exc)
        return None
