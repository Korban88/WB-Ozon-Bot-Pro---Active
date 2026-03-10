"""
Модуль 2: Генерация визуального пака.

Генерирует 5 премиальных изображений с товаром:
  1/5  Hero Shot       — студийный кадр, чистый фон
  2/5  Lifestyle       — атмосферный интерьер
  3/5  Lifestyle       — outdoor / social context
  4/5  Ad Creative     — editorial, драматичный
  5/5  Ad Creative     — detail, макро-фактура

Правила:
  - Товар не изменяется (пиксели неизменны)
  - Текст на изображениях отсутствует
  - Сцена генерируется без товара, товар накладывается отдельно
"""

from collections.abc import AsyncGenerator

import config
from models.product_data import ProductData
from services.card_renderer import render_card
from services.card_types import get_card_types
from services.color_extractor import extract_dominant_colors, get_color_description
from services.scene_gen import generate_scene

# Пользовательские подписи для 5 слотов пака
_SLOT_LABELS = {
    "hero":      "Hero Shot",
    "lifestyle": "Lifestyle",
    "social":    "Lifestyle",
    "editorial": "Ad Creative",
    "detail":    "Ad Creative",
}


async def generate_visual_pack(
    product:  "ProductData",
    user_id:  int,
    username: str | None,
) -> AsyncGenerator[tuple[int, str, bytes | None], None]:
    """
    Async-генератор. Для каждого из 5 типов карточек выдаёт:
      (index: 1-5, label: str, image_bytes: bytes | None)

    image_bytes = None если генерация конкретного изображения провалилась.
    Итерировать: async for index, label, image_bytes in generate_visual_pack(...)
    """
    use_openai = bool(config.OPENAI_API_KEY)

    # Извлекаем цветовую палитру из фото товара один раз
    try:
        palette    = extract_dominant_colors(product.photo_bytes, n_colors=3)
        color_mood = get_color_description(palette)
    except Exception:
        color_mood = "neutral warm"

    card_types = get_card_types(product.category)

    for i, card_type in enumerate(card_types):
        label = _SLOT_LABELS.get(card_type, card_type)

        # Генерируем пустую сцену (товар в неё НЕ попадает)
        scene_bytes = None
        if use_openai:
            scene_bytes = await generate_scene(
                card_type     = card_type,
                color_mood    = color_mood,
                user_id       = user_id,
                username      = username,
                concept_index = i + 1,
                marketplace   = product.marketplace,
                category      = product.category,
            )

        # Накладываем товар на сцену — без текста
        try:
            image_bytes = render_card(
                card_type     = card_type,
                scene_bytes   = scene_bytes,
                product_bytes = product.photo_bytes,
            )
        except Exception:
            image_bytes = None

        yield i + 1, label, image_bytes
