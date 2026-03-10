"""
Генерация текстов: листинг, реклама, инфографика, UGC.

АНТИГАЛЛЮЦИНАЦИОННОЕ ПРАВИЛО (применяется во всех промтах):
Использовать ТОЛЬКО данные из ТЗ.
Категорически запрещено придумывать:
  - материалы, ткань, состав
  - размеры, вес, объём
  - технические характеристики
  - сертификаты, стандарты
  - любые свойства, которых нет в ТЗ
Если данных нет — просто не упоминай этот аспект.
"""

from typing import Any

from models.product_data import ProductData
from services import openrouter as llm

_NO_HALLUCINATION = (
    "\nСТРОГОЕ ПРАВИЛО: используй ТОЛЬКО данные из ТЗ выше. "
    "Не придумывай материалы, размеры, характеристики или свойства, которых нет в ТЗ. "
    "Если данных нет — не упоминай этот аспект. Лучше меньше, но правда."
)


# ─── Листинг (текст карточки для маркетплейса) ────────────────────────────────

_LISTING_SYSTEM = (
    "Ты — копирайтер для маркетплейсов Wildberries и Ozon. "
    "Пишешь продающие тексты строго на основе данных от продавца. "
    + _NO_HALLUCINATION
    + " Ответ СТРОГО в формате JSON без markdown-обёртки."
)


def _listing_prompt(p: ProductData) -> str:
    mp = {"wb": "Wildberries", "ozon": "Ozon"}.get(p.marketplace, p.marketplace)
    return f"""Создай текст карточки товара для {mp}.

ТЗ:
{p.to_brief()}

Верни JSON:
{{
  "title":       "SEO-заголовок 50-80 символов с ключевыми словами",
  "subtitle":    "Продающий подзаголовок до 100 символов",
  "description": "Описание 300-500 символов, 2-3 абзаца",
  "features":    ["✅ Преимущество 1", "✅ Преимущество 2", "✅ Преимущество 3", "✅ Преимущество 4", "✅ Преимущество 5"],
  "specs":       ["Характеристика: значение"],
  "hashtags":    ["#тег1", "#тег2", "#тег3", "#тег4", "#тег5"]
}}"""


async def generate_listing_copy(p: ProductData, user_id: int, username: str | None) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": _LISTING_SYSTEM},
        {"role": "user",   "content": _listing_prompt(p)},
    ]
    raw = await llm.call(messages, user_id=user_id, username=username, service="listing_copy")
    return llm.parse_json(raw)


# ─── Рекламный копипак ────────────────────────────────────────────────────────

_AD_SYSTEM = (
    "Ты — директ-реклама копирайтер для российского e-commerce. "
    "Пишешь короткие мощные тексты, которые конвертируют. "
    + _NO_HALLUCINATION
    + " Ответ СТРОГО в формате JSON без markdown-обёртки."
)


def _ad_prompt(p: ProductData) -> str:
    return f"""Создай рекламный копипак для товара.

ТЗ:
{p.to_brief()}

Верни JSON:
{{
  "hooks": [
    "Хук 1 — проблема → решение (10-18 слов)",
    "Хук 2 — любопытство или вопрос",
    "Хук 3 — результат/трансформация",
    "Хук 4 — цифра или факт",
    "Хук 5 — эмоция или lifestyle"
  ],
  "copy_short": [
    "Вариант 1 — 1 предложение для объявления",
    "Вариант 2",
    "Вариант 3"
  ],
  "copy_medium": [
    "Вариант 1 — 2-3 предложения для поста в Telegram/VK",
    "Вариант 2"
  ]
}}"""


async def generate_ad_copy(p: ProductData, user_id: int, username: str | None) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": _AD_SYSTEM},
        {"role": "user",   "content": _ad_prompt(p)},
    ]
    raw = await llm.call(messages, user_id=user_id, username=username, service="ad_copy")
    return llm.parse_json(raw)


# ─── Бриф инфографики ─────────────────────────────────────────────────────────

_INFOGRAPHIC_SYSTEM = (
    "Ты — арт-директор карточек маркетплейсов. "
    "Создаёшь структурированные брифы для инфографических слайдов. "
    "Инфографика — это структура (заголовок + подзаголовок + иконка), а не текст на картинке. "
    + _NO_HALLUCINATION
    + " Ответ СТРОГО в формате JSON без markdown-обёртки."
)


def _infographic_prompt(p: ProductData) -> str:
    return f"""Создай бриф для 5 инфографических слайдов карточки.

ТЗ:
{p.to_brief()}

Каждый слайд — одно конкретное преимущество.
Иконка — английское ключевое слово для поиска в библиотеке иконок (например: "shield", "leaf", "timer").

Верни JSON:
{{
  "slides": [
    {{
      "number":      1,
      "headline":    "Короткий заголовок 3-5 слов",
      "subheadline": "Уточнение или выгода до 10 слов",
      "icon":        "english-icon-keyword",
      "color_mood":  "light | dark | accent"
    }}
  ]
}}"""


async def generate_infographic_brief(p: ProductData, user_id: int, username: str | None) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": _INFOGRAPHIC_SYSTEM},
        {"role": "user",   "content": _infographic_prompt(p)},
    ]
    raw = await llm.call(messages, user_id=user_id, username=username, service="infographic")
    return llm.parse_json(raw)


# ─── UGC сценарий ─────────────────────────────────────────────────────────────

_UGC_SYSTEM = (
    "Ты — режиссёр UGC-роликов для e-commerce. "
    "Создаёшь конкретные сценарии коротких видео (15-60 сек) для продавцов. "
    "Сценарий должен быть практичным — продавец снимет его сам или объяснит блогеру. "
    + _NO_HALLUCINATION
    + " Ответ СТРОГО в формате JSON без markdown-обёртки."
)


def _ugc_prompt(p: ProductData) -> str:
    return f"""Создай сценарий UGC-ролика для товара.

ТЗ:
{p.to_brief()}

Верни JSON:
{{
  "duration":  "15-30 сек",
  "format":    "9:16 вертикальное",
  "hook_text": "текст/действие для первых 3 секунд",
  "scenes": [
    {{
      "number":    1,
      "time":      "0-3 сек",
      "action":    "что происходит на экране",
      "voiceover": "что говорит человек (пусто если без голоса)"
    }},
    {{ "number": 2, "time": "3-10 сек",  "action": "...", "voiceover": "..." }},
    {{ "number": 3, "time": "10-20 сек", "action": "...", "voiceover": "..." }},
    {{ "number": 4, "time": "20-30 сек", "action": "...", "voiceover": "..." }}
  ],
  "cta": "финальный призыв к действию"
}}"""


async def generate_ugc_scenario(p: ProductData, user_id: int, username: str | None) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": _UGC_SYSTEM},
        {"role": "user",   "content": _ugc_prompt(p)},
    ]
    raw = await llm.call(messages, user_id=user_id, username=username, service="ugc")
    return llm.parse_json(raw)
