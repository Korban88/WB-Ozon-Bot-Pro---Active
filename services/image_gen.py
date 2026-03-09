"""
Image generation service via Together AI (FLUX.1-schnell-Free).

Falls back gracefully if no API key is set or if the API call fails —
in that case returns None and the bot skips that image.
"""

import time

import aiohttp

import config
from logger_setup import log, log_ai_call

TIMEOUT_SECONDS = 90


async def generate_image(
    user_id: int,
    username: str | None,
    prompt: str,
    concept_index: int = 0,
) -> str | None:
    """
    Generate one image via Together AI.

    Args:
        prompt: English image prompt for FLUX
        concept_index: for logging (1-5)

    Returns:
        Public image URL string, or None if generation failed.
    """
    if not config.TOGETHER_API_KEY:
        log.warning("TOGETHER_API_KEY not set — skipping image generation")
        return None

    headers = {
        "Authorization": f"Bearer {config.TOGETHER_API_KEY}",
        "Content-Type":  "application/json",
    }
    payload = {
        "model":  config.TOGETHER_MODEL,
        "prompt": prompt,
        "n":      1,
        "width":  1024,
        "height": 1024,
    }

    start = time.monotonic()
    service_name = f"together_ai/concept_{concept_index}"
    try:
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(config.TOGETHER_URL, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"Together AI HTTP {resp.status}: {body[:300]}")
                data = await resp.json()

        url = data["data"][0]["url"]
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service_name, success=True, duration_ms=elapsed)
        return url

    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service_name, success=False,
                    duration_ms=elapsed, error=str(exc))
        log.warning("Image generation failed for concept %d: %s", concept_index, exc)
        return None


async def download_image(url: str) -> bytes | None:
    """
    Download image bytes from a URL.
    Returns bytes or None on failure.
    Telegram can sometimes not reach external CDNs, so we download
    the image ourselves and send it as binary data.
    """
    try:
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status == 200:
                    return await resp.read()
                log.warning("Image download HTTP %d from %s", resp.status, url)
                return None
    except Exception as exc:
        log.warning("Image download failed from %s: %s", url, exc)
        return None
