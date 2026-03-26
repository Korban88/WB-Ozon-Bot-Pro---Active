"""
Provider adapter — абстракция визуального провайдера.

VisualProvider (ABC) — контракт провайдера.
OpenAIProvider   — генерация пустых сцен через OpenAI gpt-image-1.
PillowProvider   — fallback: сигнал рендереру использовать Pillow-градиент.
ExternalProvider — заглушка для внешних сервисов (Fabula AI, MPCard, и др.)

Провайдеры — ТОЛЬКО execution layer для генерации пустых сцен.
Вся логика (какой режим, какой план сцены, валидация) — в visual_orchestrator.py.

Переключение провайдера: VISUAL_PROVIDER в .env (openai | pillow | external).
Подключение внешнего сервиса: реализуй ExternalProvider.generate_scene() + заполни
EXTERNAL_VISUAL_API_KEY и EXTERNAL_VISUAL_API_URL в .env.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

log = logging.getLogger(__name__)


class SceneBrief:
    """Задание на генерацию пустой сцены (без товара)."""
    __slots__ = ("card_type", "prompt", "color_mood", "category", "marketplace",
                 "width", "height")

    def __init__(
        self,
        card_type:   str,
        prompt:      str,
        color_mood:  str = "neutral warm",
        category:    str = "other",
        marketplace: str = "wb",
        width:       int = 1024,
        height:      int = 1536,
    ) -> None:
        self.card_type   = card_type
        self.prompt      = prompt
        self.color_mood  = color_mood
        self.category    = category
        self.marketplace = marketplace
        self.width       = width
        self.height      = height


class VisualProvider(ABC):
    """Контракт провайдера генерации пустых сцен."""

    @abstractmethod
    async def generate_scene(self, brief: SceneBrief) -> bytes | None:
        """Генерирует пустую сцену. Возвращает PNG bytes или None (→ Pillow fallback)."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Имя провайдера для логов."""
        ...


# ─── OpenAI Provider ──────────────────────────────────────────────────────────

class OpenAIProvider(VisualProvider):
    """Генерация пустых сцен через OpenAI gpt-image-1."""

    @property
    def name(self) -> str:
        return "openai"

    async def generate_scene(self, brief: SceneBrief) -> bytes | None:
        import base64
        import aiohttp
        import config

        if not getattr(config, "OPENAI_API_KEY", ""):
            return None

        size = f"{brief.width}x{brief.height}"
        payload = {
            "model":  getattr(config, "OPENAI_IMAGE_MODEL", "gpt-image-1"),
            "prompt": brief.prompt,
            "n":      1,
            "size":   size,
        }
        headers = {
            "Authorization": f"Bearer {config.OPENAI_API_KEY}",
            "Content-Type":  "application/json",
        }

        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            ) as session:
                async with session.post(
                    "https://api.openai.com/v1/images/generations",
                    headers=headers, json=payload
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        log.warning("OpenAI HTTP %d: %s", resp.status, body[:200])
                        return None
                    data = await resp.json()

            item = data["data"][0]
            if "b64_json" in item:
                return base64.b64decode(item["b64_json"])
            if "url" in item:
                async with aiohttp.ClientSession() as s:
                    async with s.get(item["url"]) as r:
                        return await r.read()
        except Exception as exc:
            log.warning("OpenAIProvider error: %s", exc)
        return None


# ─── Pillow Fallback Provider ─────────────────────────────────────────────────

class PillowProvider(VisualProvider):
    """
    Fallback провайдер. Возвращает None — сигнал card_renderer использовать
    встроенный Pillow-градиент из палитры товара.
    """

    @property
    def name(self) -> str:
        return "pillow"

    async def generate_scene(self, brief: SceneBrief) -> bytes | None:
        return None


# ─── External Provider (stub) ─────────────────────────────────────────────────

class ExternalProvider(VisualProvider):
    """
    Stub для внешних визуальных сервисов (Fabula AI, MPCard, и др.).

    Подключение:
      1. Реализуй generate_scene() с вызовом их API
      2. Установи VISUAL_PROVIDER=external в .env
      3. Заполни EXTERNAL_VISUAL_API_KEY и EXTERNAL_VISUAL_API_URL в .env

    Возвращает None до реализации → падает на OpenAI → на Pillow-градиент.
    """

    @property
    def name(self) -> str:
        return "external"

    async def generate_scene(self, brief: SceneBrief) -> bytes | None:
        log.info("ExternalProvider: not implemented, falling back to next provider")
        return None


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_provider() -> VisualProvider:
    """
    Возвращает провайдера по VISUAL_PROVIDER из config.
    Если OpenAI выбран но ключа нет — падает на Pillow.
    """
    try:
        import config
        name = getattr(config, "VISUAL_PROVIDER", "openai").lower()
    except Exception:
        name = "openai"

    if name == "external":
        return ExternalProvider()
    if name == "pillow":
        return PillowProvider()

    # openai (default): только если ключ есть
    try:
        import config
        if getattr(config, "OPENAI_API_KEY", ""):
            return OpenAIProvider()
    except Exception:
        pass

    log.info("No OPENAI_API_KEY — using PillowProvider (gradient fallback)")
    return PillowProvider()
