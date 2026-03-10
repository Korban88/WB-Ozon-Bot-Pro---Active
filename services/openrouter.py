"""
OpenRouter API service.

Handles two types of calls:
  1. generate_card()  — vision call: analyzes product photo + user inputs,
                        returns structured product card JSON.
  2. generate_design_concepts() — text call: generates 5 design concept
                                  descriptions for the card.
"""

import base64
import json
import time
from typing import Any

import aiohttp

import config
from logger_setup import log, log_ai_call


# ── Constants ─────────────────────────────────────────────────────────────────
MAX_IMAGE_BYTES = 500_000  # truncate base64 to ~500 KB to avoid request errors
TIMEOUT_SECONDS = 60

MARKETPLACE_NAMES = {"wb": "Wildberries", "ozon": "Ozon"}
CATEGORY_NAMES = {
    "clothing":    "Одежда",
    "electronics": "Электроника",
    "home":        "Дом и интерьер",
    "beauty":      "Красота и уход",
    "accessories": "Аксессуары",
    "other":       "Другое",
}


# ── Card generation ────────────────────────────────────────────────────────────
CARD_SYSTEM_PROMPT = """Ты — профессиональный маркетолог и копирайтер для маркетплейсов Wildberries и Ozon.
Твоя задача — создавать продающие карточки товаров, которые привлекают внимание и конвертируют просмотры в покупки.

Правила:
- Используй эмодзи для визуального выделения ключевых преимуществ
- Пиши живым, убедительным языком — как лучший продавец
- SEO-оптимизируй название: включай ключевые слова, которые ищут покупатели
- Характеристики — конкретные цифры и факты, не общие слова
- Ответ СТРОГО в формате JSON, без пояснений до или после"""

CARD_USER_PROMPT = """Создай продающую карточку товара для маркетплейса {marketplace}.

Данные от продавца:
- Маркетплейс: {marketplace}
- Категория: {category}
- Название товара: {title}
- Преимущества и описание: {benefits}

На фото — сам товар. Используй визуальные детали с фото для точных характеристик.

Верни ТОЛЬКО JSON в следующем формате (без markdown-обёртки):
{{
  "title": "SEO-оптимизированное название (50-80 символов, включи ключевые слова)",
  "subtitle": "Короткий продающий подзаголовок (до 100 символов)",
  "description": "Продающее описание товара (2-3 абзаца, 300-500 символов, убеди купить)",
  "features": [
    "✅ Преимущество 1 (конкретно и убедительно)",
    "✅ Преимущество 2",
    "✅ Преимущество 3",
    "✅ Преимущество 4",
    "✅ Преимущество 5"
  ],
  "specs": [
    "Характеристика: значение",
    "Характеристика: значение",
    "Характеристика: значение"
  ],
  "hashtags": ["#тег1", "#тег2", "#тег3", "#тег4", "#тег5"]
}}"""


async def generate_card(
    user_id: int,
    username: str | None,
    title: str,
    category: str,
    marketplace: str,
    benefits: str,
    photo_bytes: bytes,
) -> dict[str, Any]:
    """
    Call OpenRouter with vision to generate a product card.
    Returns parsed JSON dict with card data.
    Raises RuntimeError on API failure.
    """
    # Encode photo as base64, truncate if too large
    if len(photo_bytes) > MAX_IMAGE_BYTES:
        photo_bytes = photo_bytes[:MAX_IMAGE_BYTES]
    b64_image = base64.b64encode(photo_bytes).decode("utf-8")

    marketplace_name = MARKETPLACE_NAMES.get(marketplace, marketplace)
    category_name    = CATEGORY_NAMES.get(category, category)

    messages = [
        {"role": "system", "content": CARD_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"},
                },
                {
                    "type": "text",
                    "text": CARD_USER_PROMPT.format(
                        marketplace=marketplace_name,
                        category=category_name,
                        title=title,
                        benefits=benefits,
                    ),
                },
            ],
        },
    ]

    start = time.monotonic()
    try:
        result = await _call_openrouter(messages, json_mode=False)
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, "openrouter/generate_card", success=True, duration_ms=elapsed)
        return _parse_json_response(result)
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, "openrouter/generate_card", success=False,
                    duration_ms=elapsed, error=str(exc))
        raise


# ── Design concepts generation ────────────────────────────────────────────────
DESIGN_SYSTEM_PROMPT = """Ты — арт-директор и дизайнер карточек товаров для маркетплейсов.
Создаёшь детальные ТЗ (технические задания) для дизайна карточек товаров.
Для каждого концепта указывай точные hex-коды цветов, шрифты с размерами и детальное описание композиции.
Ответ СТРОГО в формате JSON без комментариев и без markdown-обёртки."""

DESIGN_USER_PROMPT = """Создай 5 уникальных дизайн-концептов (ТЗ для дизайнера) для карточки товара.

Товар: {title}
Маркетплейс: {marketplace}
Категория: {category}

Для каждого концепта укажи:
1. Название стиля (ёмко и ярко, например «Минимализм Premium» или «Контраст Dark»)
2. Цветовую палитру — ровно 3 цвета с hex-кодами: фон, основной текст/заголовок, акцент
3. Типографику — шрифт, размеры в px, цвета для заголовка и подписей
4. Композицию — фон карточки, расположение товара, структура блоков (2-3 предложения)

Стили должны быть разными: например минимализм, тёмный контраст, яркий поп, природный/эко, премиум-люкс.

Верни ТОЛЬКО JSON (без markdown-обёртки):
{{
  "concepts": [
    {{
      "index": 1,
      "name": "Минимализм Premium",
      "colors": "Белый #FFFFFF · Тёмно-синий #1A237E · Акцент золотой #FFD700",
      "typography": "Заголовок: Montserrat Bold 72px, цвет #1A237E\\nПодписи: Medium 28px, цвет #333333\\nАкценты: #FFD700",
      "composition": "Центральная ось, симметрия, товар hero по центру 70% площади. Фон: студийный белый с мягкими тенями. Три буллета с преимуществами снизу на белом фоне, типографика Montserrat Bold."
    }},
    ... (5 концептов)
  ]
}}"""


async def generate_design_concepts(
    user_id: int,
    username: str | None,
    title: str,
    category: str,
    marketplace: str,
) -> list[dict[str, Any]]:
    """
    Generate 5 detailed design concept TZ (technical specs).
    Returns list of concept dicts: [{index, name, colors, typography, composition}, ...]
    """
    marketplace_name = MARKETPLACE_NAMES.get(marketplace, marketplace)
    category_name    = CATEGORY_NAMES.get(category, category)

    messages = [
        {"role": "system", "content": DESIGN_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": DESIGN_USER_PROMPT.format(
                title=title,
                marketplace=marketplace_name,
                category=category_name,
            ),
        },
    ]

    start = time.monotonic()
    try:
        result = await _call_openrouter(messages, json_mode=False)
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, "openrouter/design_concepts", success=True, duration_ms=elapsed)
        data = _parse_json_response(result)
        return data.get("concepts", [])
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, "openrouter/design_concepts", success=False,
                    duration_ms=elapsed, error=str(exc))
        raise


# ── Ad Copy Pack generation ───────────────────────────────────────────────────

AD_COPY_SYSTEM_PROMPT = """Ты — топовый директ-реклама копирайтер для российского e-commerce (Wildberries, Ozon, VK Реклама, Telegram Ads).
Пишешь короткие, мощные тексты, которые реально конвертируют.
Знаешь психологию покупателя, триггеры, AIDA, PAS.
Ответ СТРОГО в формате JSON без markdown-обёртки и без пояснений."""

AD_COPY_USER_PROMPT = """Создай полный рекламный копипак для товара.

Товар: {title}
Маркетплейс: {marketplace}
Категория: {category}
Описание и преимущества: {benefits}

Верни ТОЛЬКО JSON (без markdown-обёртки):
{{
  "hooks": [
    "Хук 1 — 10-18 слов, проблема → решение",
    "Хук 2 — любопытство или вопрос",
    "Хук 3 — результат / трансформация",
    "Хук 4 — социальное доказательство / цифра",
    "Хук 5 — эмоциональный / lifestyle"
  ],
  "copy_short": [
    "Вариант 1 — 1 предложение, 10-15 слов, для объявления",
    "Вариант 2 — другой угол",
    "Вариант 3 — ещё вариант"
  ],
  "copy_medium": [
    "Вариант 1 — 2-3 предложения, для поста в Telegram/VK",
    "Вариант 2 — другой подход"
  ],
  "ugc_brief": "Сценарий для UGC-видео 15-30 сек. Формат: Хук (0-3с): [текст]. Проблема (3-8с): [текст]. Продукт (8-20с): [текст]. CTA (20-30с): [текст]."
}}"""


async def generate_ad_copy(
    user_id: int,
    username: str | None,
    title: str,
    category: str,
    marketplace: str,
    benefits: str,
) -> dict[str, Any]:
    """
    Generate ad copy pack: 5 hooks, 3 short copy, 2 medium copy, UGC brief.
    Returns parsed JSON dict.
    Raises RuntimeError on API failure.
    """
    marketplace_name = MARKETPLACE_NAMES.get(marketplace, marketplace)
    category_name    = CATEGORY_NAMES.get(category, category)

    messages = [
        {"role": "system", "content": AD_COPY_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": AD_COPY_USER_PROMPT.format(
                title=title,
                marketplace=marketplace_name,
                category=category_name,
                benefits=benefits,
            ),
        },
    ]

    start = time.monotonic()
    try:
        result = await _call_openrouter(messages, json_mode=False)
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, "openrouter/ad_copy", success=True, duration_ms=elapsed)
        return _parse_json_response(result)
    except Exception as exc:
        elapsed = int((time.monotonic() - start) * 1000)
        log_ai_call(user_id, username, "openrouter/ad_copy", success=False,
                    duration_ms=elapsed, error=str(exc))
        raise


# ── Internal helpers ──────────────────────────────────────────────────────────
async def _call_openrouter(messages: list[dict], json_mode: bool = False) -> str:
    """Make a raw OpenRouter API call. Returns the assistant message content."""
    headers = {
        "Authorization": f"Bearer {config.OPENROUTER_API_KEY}",
        "Content-Type":  "application/json",
        "HTTP-Referer":  "https://github.com/wb-ozon-bot",
        "X-Title":       "WB/Ozon Card Bot",
    }

    payload: dict[str, Any] = {
        "model":    config.OPENROUTER_MODEL,
        "messages": messages,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(config.OPENROUTER_URL, headers=headers, json=payload) as resp:
            if resp.status != 200:
                body = await resp.text()
                raise RuntimeError(f"OpenRouter HTTP {resp.status}: {body[:300]}")
            data = await resp.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected OpenRouter response structure: {data}") from exc


def _parse_json_response(text: str) -> dict[str, Any]:
    """
    Extract JSON from model response.
    Models sometimes wrap JSON in ```json ... ``` — we strip that.
    """
    text = text.strip()

    # Strip markdown code fence if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        log.warning("Failed to parse JSON response: %s...", text[:200])
        raise RuntimeError(f"Model returned invalid JSON: {exc}") from exc
