"""
Visual Orchestrator — режиссёр создания визуального пака.

Mode A — COMPOSITING (default, всегда):
  Сцена генерируется без товара. Товар накладывается отдельно (пиксели неизменны).
  Pipeline: color_extract → scene_plan → prompt_build → provider → composite → log

Правила:
  - Товар не изменяется (пиксели неизменны)
  - Лучше чистый студийный кадр, чем плохой lifestyle-коллаж
  - Логи: провайдер, ретраи, gradient fallback

Внешние сервисы (Fabula AI, MPCard) — только execution layer:
  - Подключаются через ExternalProvider в provider_adapter.py
  - НЕ влияют на логику выбора сцен или валидацию результата
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from models.product_data import ProductData
from core.provider_adapter import SceneBrief, VisualProvider, get_provider
from services.card_renderer import render_card
from services.card_types import get_card_types, build_scene_prompt
from services.color_extractor import extract_dominant_colors, get_color_description

log = logging.getLogger(__name__)

_SLOT_LABELS = {
    "hero":      "Hero Shot",
    "lifestyle": "Lifestyle",
    "social":    "Lifestyle",
    "editorial": "Ad Creative",
    "detail":    "Ad Creative",
}

_SCENE_W, _SCENE_H = 1024, 1536
_MAX_RETRIES = 2


class VisualOrchestrator:
    """Координирует создание визуального пака из 5 изображений."""

    def __init__(self, provider: VisualProvider | None = None) -> None:
        self._provider = provider or get_provider()

    async def generate_pack(
        self,
        product:  ProductData,
        user_id:  int,
        username: str | None,
    ) -> AsyncGenerator[tuple[int, str, bytes | None], None]:
        """
        Async-генератор: (index: 1-5, label: str, image_bytes: bytes | None).
        image_bytes = None если визуал не удалось создать.
        """
        try:
            palette    = extract_dominant_colors(product.photo_bytes, n_colors=3)
            color_mood = get_color_description(palette)
        except Exception:
            color_mood = "neutral warm"

        log.info("VisualOrchestrator: provider=%s color_mood=%s category=%s",
                 self._provider.name, color_mood, product.category)

        card_types = get_card_types(product.category)

        for i, card_type in enumerate(card_types):
            label       = _SLOT_LABELS.get(card_type, card_type)
            scene_bytes = await self._get_scene(
                card_type, color_mood, product.category, product.marketplace, i + 1
            )

            try:
                image_bytes = render_card(
                    card_type     = card_type,
                    scene_bytes   = scene_bytes,
                    product_bytes = product.photo_bytes,
                )
                log.info("Visual %d/%d OK: type=%s source=%s",
                         i + 1, len(card_types), card_type,
                         "ai" if scene_bytes else "gradient")
            except Exception as exc:
                log.warning("Visual %d/%d FAILED: type=%s: %s",
                            i + 1, len(card_types), card_type, exc)
                image_bytes = None

            yield i + 1, label, image_bytes

    async def _get_scene(
        self,
        card_type:   str,
        color_mood:  str,
        category:    str,
        marketplace: str,
        slot_index:  int,
    ) -> bytes | None:
        """Пробует получить AI-сцену с ретраями. None → card_renderer Pillow fallback."""
        prompt = build_scene_prompt(card_type, color_mood, marketplace, category)
        brief  = SceneBrief(
            card_type   = card_type,
            prompt      = prompt,
            color_mood  = color_mood,
            category    = category,
            marketplace = marketplace,
            width       = _SCENE_W,
            height      = _SCENE_H,
        )

        for attempt in range(_MAX_RETRIES):
            scene = await self._provider.generate_scene(brief)
            if scene:
                return scene
            if attempt < _MAX_RETRIES - 1:
                log.info("Scene retry %d/%d: type=%s provider=%s",
                         attempt + 1, _MAX_RETRIES, card_type, self._provider.name)

        log.info("Scene→gradient fallback: type=%s slot=%d", card_type, slot_index)
        return None


_orchestrator: VisualOrchestrator | None = None


def get_orchestrator() -> VisualOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = VisualOrchestrator()
    return _orchestrator
