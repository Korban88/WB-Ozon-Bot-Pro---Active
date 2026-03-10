"""
OpenRouter API client — тонкая обёртка над HTTP.

Вся бизнес-логика (промты, форматирование) живёт в core/.
Этот файл только: отправить сообщения → получить строку.
"""

import json
import time

import aiohttp

import config
from logger_setup import log, log_ai_call

TIMEOUT = 90


async def call(
    messages:  list[dict],
    user_id:   int | None  = None,
    username:  str | None  = None,
    service:   str         = "openrouter",
    json_mode: bool        = False,
) -> str:
    """
    Отправляет messages в OpenRouter. Возвращает строку-ответ ассистента.
    Логирует вызов в dialog.log.
    """
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://github.com/wb-ozon-bot",
        "X-Title":       "WB/Ozon AI Studio",
    }
    payload: dict = {"model": config.OPENROUTER_MODEL, "messages": messages}
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    start = time.monotonic()
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=TIMEOUT)) as session:
            async with session.post(config.OPENROUTER_URL, headers=headers, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"OpenRouter HTTP {resp.status}: {body[:200]}")
                data = await resp.json()

        content = data["choices"][0]["message"]["content"]
        elapsed = int((time.monotonic() - start) * 1000)
        if user_id:
            log_ai_call(user_id, username, service, success=True, duration_ms=elapsed)
        return content

    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        if user_id:
            log_ai_call(user_id, username, service, success=False,
                        duration_ms=elapsed, error=str(exc))
        raise


def parse_json(text: str) -> dict:
    """
    Извлекает JSON из ответа модели.
    Автоматически срезает ```json ... ``` обёртку если она есть.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("JSON parse failed: %s...", text[:150])
        raise RuntimeError(f"Модель вернула невалидный JSON: {exc}") from exc
