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
  - Лучше чистый студийный кадр, чем плохой lifestyle-коллаж

Маршрутизация: VisualOrchestrator → VisualProvider → card_renderer
Провайдеры: OpenAI (default) | Pillow gradient (fallback) | External (stub)
"""

from collections.abc import AsyncGenerator

from models.product_data import ProductData
from core.visual_orchestrator import get_orchestrator


async def generate_visual_pack(
    product:  ProductData,
    user_id:  int,
    username: str | None,
) -> AsyncGenerator[tuple[int, str, bytes | None], None]:
    """
    Async-генератор. Для каждого из 5 типов карточек выдаёт:
      (index: 1-5, label: str, image_bytes: bytes | None)

    image_bytes = None если генерация конкретного изображения провалилась.
    Итерировать: async for index, label, image_bytes in generate_visual_pack(...)
    """
    orchestrator = get_orchestrator()
    async for index, label, image_bytes in orchestrator.generate_pack(product, user_id, username):
        yield index, label, image_bytes
