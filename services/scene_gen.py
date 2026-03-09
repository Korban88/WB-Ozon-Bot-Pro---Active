"""
Scene generator: gpt-image-1 /edits with product photo.

Card type drives the scene prompt:
  hero      — clean studio, product as sole subject
  lifestyle — atmospheric lifestyle context
  editorial — dramatic art-directed photography
  detail    — close-up material/craft focus
  features  — returns None (uses Pillow gradient background instead)

Text is added separately by card_renderer.render_card().
"""

import base64
import io
import time

import aiohttp

import config
from logger_setup import log, log_ai_call
from services.card_types import build_scene_prompt

_EDITS_URL = "https://api.openai.com/v1/images/edits"
_TIMEOUT   = 120


async def generate_scene(
    concept:       dict,
    product_bytes: bytes,
    marketplace:   str,
    category:      str,
    user_id:       int,
    username:      str | None,
    concept_index: int = 1,
    card_type:     str = "hero",
) -> bytes | None:
    """
    Generate a scene via gpt-image-1 /edits.
    Returns PNG bytes, or None for 'features' type or on failure.
    """
    if not config.OPENAI_API_KEY:
        return None

    # Features card uses a clean Pillow background — no AI scene needed
    if card_type == "features":
        return None

    prompt  = build_scene_prompt(card_type, concept, marketplace, category)
    service = f"openai_scene/{card_type}_{concept_index}"
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
            filename     = "product.png",
            content_type = "image/png",
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
            raise RuntimeError(f"Unexpected OpenAI response: {list(item.keys())}")

        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=True, duration_ms=elapsed)
        log.info("Scene generated: type=%s concept=%d (%dms)", card_type, concept_index, elapsed)
        return image_bytes

    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=False,
                    duration_ms=elapsed, error=str(exc))
        log.warning("Scene failed: type=%s concept=%d: %s", card_type, concept_index, exc)
        return None
