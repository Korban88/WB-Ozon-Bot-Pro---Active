"""
Marketplace card visual generation via OpenAI gpt-image-1.

Generates VISUAL ONLY (no text) — text is overlaid by card_renderer.overlay_text_on_image().

Uses /v1/images/edits endpoint:
  - takes original product photo as input
  - applies TZ concept style (colors, background, lighting, composition)
  - returns PNG bytes of the styled visual

Falls back gracefully if OPENAI_API_KEY is not set (returns None → Pillow fallback).
"""

import base64
import io
import time

import aiohttp

import config
from logger_setup import log, log_ai_call

TIMEOUT_SECONDS = 120


def build_image_prompt(
    concept: dict,
    title: str,
    features: list[str],
    marketplace: str,
    category: str,
) -> str:
    """
    Build a VISUAL-ONLY prompt for gpt-image-1.
    Text is NOT requested here — it will be overlaid separately by Pillow.
    """
    _mp  = {"wb": "Wildberries", "ozon": "Ozon"}
    _cat = {
        "clothing":    "одежда",
        "electronics": "электроника",
        "home":        "товары для дома",
        "beauty":      "красота и уход",
        "accessories": "аксессуары",
        "other":       "товары",
    }
    mp_name  = _mp.get(marketplace,  marketplace)
    cat_name = _cat.get(category, category)

    name        = concept.get("name",        "")
    colors      = concept.get("colors",      "")
    typography  = concept.get("typography",  "")
    composition = concept.get("composition", "")

    return (
        f"Create a professional marketplace product card visual for {mp_name}, "
        f"category: {cat_name}.\n"
        f"Design style: «{name}»\n\n"
        f"PRODUCT: Use the attached photo of the product as the hero element. "
        f"Place it prominently in the upper-center area. "
        f"Keep the product appearance exactly as in the photo — do not alter the product itself.\n\n"
        f"COLOR SCHEME: {colors}\n"
        f"VISUAL STYLE & ATMOSPHERE: {composition}\n\n"
        f"CRITICAL RULES:\n"
        f"- Do NOT add any text, letters, numbers, or writing anywhere on the image\n"
        f"- Do NOT add logos or watermarks\n"
        f"- Leave the bottom 35% of the image darker and relatively uncluttered "
        f"(text will be added there separately)\n"
        f"- Focus on: background style, lighting, atmosphere, product placement, "
        f"decorative elements matching the concept\n\n"
        f"Quality: professional commercial photography, {mp_name} top-seller card style, "
        f"high-end product photography, studio lighting, sharp details."
    )


async def generate_card_image(
    user_id: int,
    username: str | None,
    prompt: str,
    photo_bytes: bytes,
    concept_index: int = 0,
) -> bytes | None:
    """
    Generate a styled product card visual using OpenAI gpt-image-1.
    Returns PNG bytes (visual only, no text). Returns None on failure.
    """
    if not config.OPENAI_API_KEY:
        log.warning("OPENAI_API_KEY not set — skipping OpenAI image generation")
        return None

    service = f"openai_image/concept_{concept_index}"
    start   = time.monotonic()

    try:
        form = aiohttp.FormData()
        form.add_field("model",  config.OPENAI_IMAGE_MODEL)
        form.add_field("prompt", prompt)
        form.add_field("n",      "1")
        form.add_field("size",   "1024x1024")
        form.add_field(
            "image",
            io.BytesIO(photo_bytes),
            filename     = "product.jpg",
            content_type = "image/jpeg",
        )

        headers = {"Authorization": f"Bearer {config.OPENAI_API_KEY}"}
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                config.OPENAI_IMAGE_URL, headers=headers, data=form
            ) as resp:
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
            raise RuntimeError(f"Unexpected response keys: {list(item.keys())}")

        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=True, duration_ms=elapsed)
        log.info("OpenAI visual generated for concept %d (%dms)", concept_index, elapsed)
        return image_bytes

    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=False,
                    duration_ms=elapsed, error=str(exc))
        log.warning("OpenAI image gen failed for concept %d: %s", concept_index, exc)
        return None
