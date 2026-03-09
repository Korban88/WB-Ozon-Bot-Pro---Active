"""
Marketplace card image generation via OpenAI gpt-image-1.

Uses /v1/images/edits endpoint:
  - takes the original product photo as input image
  - applies the TZ concept (colors, typography, composition)
  - generates a professional marketplace card with Russian text

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
    """Build the image generation prompt from TZ concept data."""
    _mp  = {"wb": "Wildberries", "ozon": "Ozon"}
    _cat = {
        "clothing":    "Одежда",
        "electronics": "Электроника",
        "home":        "Дом и интерьер",
        "beauty":      "Красота и уход",
        "accessories": "Аксессуары",
        "other":       "Другое",
    }
    mp_name  = _mp.get(marketplace,  marketplace)
    cat_name = _cat.get(category, category)

    name        = concept.get("name",        "")
    colors      = concept.get("colors",      "")
    typography  = concept.get("typography",  "")
    composition = concept.get("composition", "")

    # Up to 3 clean feature bullets
    bullets = []
    for f in features[:3]:
        import re
        clean = re.sub(r'^[✅•▸✓➤→\-\s]+', '', f).strip()
        if clean:
            bullets.append(clean)
    bullets_text = "\n".join(f"• {b}" for b in bullets)

    return (
        f"Создай карточку товара для маркетплейса {mp_name}, категория «{cat_name}».\n"
        f"Стиль карточки: «{name}»\n\n"
        f"ФОТО ТОВАРА (прилагается): Это фото реального товара. "
        f"Размести его в центре карточки как главный визуал (hero shot). "
        f"Товар должен выглядеть как на оригинальном фото — не изменяй его.\n\n"
        f"ЦВЕТА: {colors}\n"
        f"ТИПОГРАФИКА: {typography}\n"
        f"КОМПОЗИЦИЯ: {composition}\n\n"
        f"ТЕКСТ НА КАРТОЧКЕ (на русском языке):\n"
        f"Заголовок: {title}\n"
        f"Преимущества:\n{bullets_text}\n\n"
        f"ТРЕБОВАНИЯ:\n"
        f"• Формат 1:1 (1000×1000px)\n"
        f"• Весь текст читается на мобильном\n"
        f"• Safe zone 8–10% от краёв\n"
        f"• Стиль топ-карточек {mp_name} в категории «{cat_name}»"
    )


async def generate_card_image(
    user_id: int,
    username: str | None,
    prompt: str,
    photo_bytes: bytes,
    concept_index: int = 0,
) -> bytes | None:
    """
    Generate a marketplace card image using OpenAI gpt-image-1.

    Takes the product photo + TZ prompt, returns PNG bytes.
    Returns None if OPENAI_API_KEY is not set or on any error.
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
        log.info("OpenAI image generated for concept %d (%dms)", concept_index, elapsed)
        return image_bytes

    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service, success=False,
                    duration_ms=elapsed, error=str(exc))
        log.warning("OpenAI image gen failed for concept %d: %s", concept_index, exc)
        return None
