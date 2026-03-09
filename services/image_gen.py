"""
Image generation service via Pollinations.ai (free, no API key required).

Pollinations generates images on-demand by GET request to a URL.
Falls back gracefully if the API call fails — returns None and the bot skips that image.
"""

import time
import urllib.parse

import aiohttp

from logger_setup import log, log_ai_call

TIMEOUT_SECONDS = 90


def _build_url(prompt: str) -> str:
    encoded = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded}?width=1024&height=1024&nologo=true"


async def generate_image(
    user_id: int,
    username: str | None,
    prompt: str,
    concept_index: int = 0,
) -> str | None:
    """
    Generate one image via Pollinations.ai (free, no API key needed).

    Returns the image URL (generation happens on first GET), or None on failure.
    """
    url = _build_url(prompt)

    start = time.monotonic()
    service_name = f"pollinations/concept_{concept_index}"
    try:
        timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, allow_redirects=True) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"Pollinations HTTP {resp.status}: {body[:200]}")
                image_bytes = await resp.read()

        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service_name, success=True, duration_ms=elapsed)

        # Return bytes directly wrapped in a sentinel so caller can send without re-downloading
        # We store bytes in a module-level cache keyed by url
        _image_cache[url] = image_bytes
        return url

    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, service_name, success=False,
                    duration_ms=elapsed, error=str(exc))
        log.warning("Image generation failed for concept %d: %s", concept_index, exc)
        return None


# Simple in-memory cache so download_image doesn't re-fetch already downloaded bytes
_image_cache: dict[str, bytes] = {}


async def download_image(url: str) -> bytes | None:
    """
    Return image bytes. Uses cache if already downloaded during generate_image.
    Falls back to HTTP GET if not cached.
    """
    if url in _image_cache:
        return _image_cache.pop(url)

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
