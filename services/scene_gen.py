"""
Scene generation via gpt-image-1 /generations.

CRITICAL RULE: Product image is NEVER sent to OpenAI.
Generates EMPTY background scenes only.
Product is composited separately in card_renderer.py.

Pipeline:
  color_extractor → color_mood string
  scene_gen       → empty background scene (no product)
  card_renderer   → product cutout composited onto scene
"""

import base64
import time

import aiohttp

import config
from logger_setup import log, log_ai_call
from services.card_types import build_scene_prompt

_GENERATIONS_URL = "https://api.openai.com/v1/images/generations"
_TIMEOUT = 120

# 1024x1536 — closest supported size to 4:5 portrait format
_SCENE_SIZE = "1024x1536"


async def generate_scene(
    card_type:     str,
    color_mood:    str,
    user_id:       int,
    username:      str | None,
    concept_index: int = 1,
    marketplace:   str = "wb",
    category:      str = "other",
) -> bytes | None:
    """
    Generate background scene WITHOUT product via /generations endpoint.
    No product bytes are sent to OpenAI — ever.
    Returns PNG bytes or None on failure/unavailability.
    """
    if not config.OPENAI_API_KEY:
        return None

    # Features card uses Pillow-only gradient — no AI needed
    if card_type == "features":
        return None

    prompt = build_scene_prompt(card_type, color_mood, marketplace, category)
    service = f"openai_scene/{card_type}_{concept_index}"
    start = time.monotonic()

    try:
        payload = {
            "model":           config.OPENAI_IMAGE_MODEL,
            "prompt":          prompt,
            "n":               1,
            "size":            _SCENE_SIZE,
            "response_format": "b64_json",
        }
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type":  "application/json",
        }

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=_TIMEOUT)
        ) as session:
            async with session.post(
                _GENERATIONS_URL, headers=headers, json=payload
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"OpenAI HTTP {resp.status}: {body[:300]}")
                data = await resp.json()

        item = data["data"][0]
        if "b64_json" in item:
            image_bytes = base64.b64decode(item["b64_json"])
        elif "url" in item:
            async with aiohttp.ClientSession() as s:
                async with s.get(item["url"]) as r:
                    image_bytes = await r.read()
        else:
            raise RuntimeError(f"Unexpected response keys: {list(item.keys())}")

        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=True, duration_ms=elapsed)
        log.info("Scene ready: type=%s (%dms)", card_type, elapsed)
        return image_bytes

    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=False,
                    duration_ms=elapsed, error=str(exc))
        log.warning("Scene failed: type=%s: %s", card_type, exc)
        return None
