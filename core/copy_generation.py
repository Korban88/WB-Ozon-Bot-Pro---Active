"""
Генерация текстов: листинг, реклама, инфографика, UGC.

АНТИГАЛЛЮЦИНАЦИОННАЯ СИСТЕМА v2:
  1. Перед каждым промтом строится ЯВНЫЙ СПИСОК ФАКТОВ из ProductData.
  2. LLM получает только этот список — никаких «общих знаний о товаре».
  3. Если данных мало — LLM явно об этом предупреждается и выдаёт
     честный минималистичный результат, а не выдумывает.
  4. Запрещено: материалы, состав, размеры, сертификаты, запахи,
     температурные эффекты, сравнения с конкурентами —
     если этого нет в предоставленных фактах.
"""

from typing import Any

from models.product_data import ProductData
from services import openrouter as llm

# ─── Хелперы ──────────────────────────────────────────────────────────────────

_CAT_NAMES = {
    "clothing": "Одежда", "electronics": "Электроника",
    "home": "Дом и интерьер", "beauty": "Красота и уход",
    "accessories": "Аксессуары", "other": "Другое",
}


def _facts_inventory(p: ProductData) -> str:
    """
    Создаёт ЯВНЫЙ СПИСОК ФАКТОВ которые LLM может использовать.
    Всё, чего нет в этом списке — запрещено упоминать.
    """
    facts = []
    if p.title:                  facts.append(f"• Название: {p.title}")
    if p.brand:                  facts.append(f"• Бренд: {p.brand}")
    if p.category and p.category != "other":
        facts.append(f"• Категория: {_CAT_NAMES.get(p.category, p.category)}")
    if p.marketplace:
        mp = {"wb": "Wildberries", "ozon": "Ozon"}.get(p.marketplace, p.marketplace)
        facts.append(f"• Маркетплейс: {mp}")
    if p.price:                  facts.append(f"• Цена: {p.price}₽")
    if p.rating:                 facts.append(f"• Рейтинг: {p.rating}/5 ({p.reviews_count} отзывов)")
    if p.description:            facts.append(f"• Описание из карточки: {p.description[:500]}")
    if p.benefits:               facts.append(f"• Характеристики/преимущества (от продавца): {p.benefits[:500]}")

    if not facts:
        return (
            "⚠️ ДАННЫХ О ТОВАРЕ НЕТ — есть только название.\n"
            "Генерируй только то, что можно вывести из названия. "
            "Не придумывай ничего лишнего."
        )

    data_quality = "достаточно" if len(facts) >= 4 else "мало"
    warning = "" if data_quality == "достаточно" else (
        "\n\n⚠️ ДАННЫХ МАЛО. Генерируй ТОЛЬКО на основе того что есть выше. "
        "Лучше короткий честный текст, чем длинный выдуманный."
    )

    return "ТОЛЬКО ЭТИ ФАКТЫ разрешено использовать:\n" + "\n".join(facts) + warning


_HARD_RULE = (
    "\n\nЖЁСТКОЕ ПРАВИЛО — НЕЛЬЗЯ:\n"
    "✗ придумывать материалы, ткань, состав, запахи, вкусы\n"
    "✗ придумывать размеры, вес, объём, мощность, технические цифры\n"
    "✗ придумывать эффекты (согревает, охлаждает, успокаивает и т.п.)\n"
    "✗ писать «популярный выбор», «любимый миллионами», «выбор экспертов»\n"
    "✗ сравнивать с конкурентами если данных нет\n"
    "✗ выдумывать сертификаты, стандарты, награды\n"
    "Если хочешь упомянуть что-то — проверь: есть ли это в списке фактов выше?"
)


# ─── Листинг (текст карточки для маркетплейса) ───────────────────────────────

_LISTING_SYSTEM = (
    "Ты — копирайтер для маркетплейсов Wildberries и Ozon. "
    "Пишешь продающие тексты СТРОГО на основе предоставленных фактов. "
    "Ответ СТРОГО в формате JSON без markdown-обёртки."
)


def _listing_prompt(p: ProductData) -> str:
    mp = {"wb": "Wildberries", "ozon": "Ozon"}.get(p.marketplace, p.marketplace)
    return f"""Создай текст карточки товара для {mp}.

{_facts_inventory(p)}
{_HARD_RULE}

Верни JSON:
{{
  "title":       "SEO-заголовок 50-80 символов с ключевыми словами",
  "subtitle":    "Продающий подзаголовок до 100 символов",
  "description": "Описание 300-500 символов, 2-3 абзаца",
  "features":    ["✅ Преимущество из фактов 1", "✅ Преимущество 2", "✅ Преимущество 3"],
  "specs":       ["Характеристика: значение — только из фактов"],
  "hashtags":    ["#тег1", "#тег2", "#тег3", "#тег4", "#тег5"]
}}

Важно: features и specs — только то что есть в фактах. Лучше 2 реальных, чем 5 выдуманных."""


async def generate_listing_copy(p: ProductData, user_id: int, username: str | None) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": _LISTING_SYSTEM},
        {"role": "user",   "content": _listing_prompt(p)},
    ]
    raw = await llm.call(messages, user_id=user_id, username=username, service="listing_copy")
    return llm.parse_json(raw)


# ─── Рекламный копипак ────────────────────────────────────────────────────────

_AD_SYSTEM = (
    "Ты — директ-рекламный копирайтер для российского e-commerce. "
    "Пишешь короткие мощные тексты, которые конвертируют. "
    "Работаешь ТОЛЬКО с фактами, которые предоставлены. "
    "Ответ СТРОГО в формате JSON без markdown-обёртки."
)


def _ad_prompt(p: ProductData) -> str:
    return f"""Создай рекламный копипак.

{_facts_inventory(p)}
{_HARD_RULE}

Хуки и тексты строятся на реальных преимуществах товара из фактов выше.
Не пиши общих фраз типа «лучший», «премиальный», «топовый» без подтверждения фактами.

Верни JSON:
{{
  "hooks": [
    "Хук 1 — конкретная проблема → конкретное решение из фактов (10-18 слов)",
    "Хук 2 — вопрос к целевой аудитории",
    "Хук 3 — результат/трансформация на основе реального преимущества",
    "Хук 4 — конкретный факт или цифра из данных",
    "Хук 5 — lifestyle или эмоция, но только если категория это поддерживает"
  ],
  "copy_short": [
    "Вариант 1 — 1 предложение для объявления на основе фактов",
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


# ─── Инфографика: полный blueprint для дизайнера ──────────────────────────────

_INFOGRAPHIC_SYSTEM = (
    "Ты — арт-директор и стратег по карточкам маркетплейсов. "
    "Создаёшь детальные брифы инфографических слайдов. "
    "Каждый слайд — конкретная роль в воронке продаж. "
    "Работаешь ТОЛЬКО с предоставленными фактами о товаре. "
    "Ответ СТРОГО в формате JSON без markdown-обёртки."
)


def _infographic_prompt(p: ProductData) -> str:
    return f"""Создай полный blueprint для 5 инфографических слайдов карточки маркетплейса.

{_facts_inventory(p)}
{_HARD_RULE}

Каждый слайд выполняет конкретную роль в воронке: hook → benefit → spec → social_proof → cta.
Если данных для social_proof нет — замени на второй benefit.

Верни JSON:
{{
  "slides": [
    {{
      "number":           1,
      "role":             "hook",
      "priority":         1,
      "headline":         "Короткий заголовок 2-4 слова — из фактов",
      "subheadline":      "Уточнение до 8 слов — из фактов",
      "icon":             "english-icon-keyword для библиотеки иконок",
      "visual_hierarchy": "headline_dominant | icon_dominant | split",
      "color_mood":       "light | dark | accent",
      "seo_keyword":      "ключевое слово для этого слайда",
      "sells_because":    "одна фраза: почему этот слайд влияет на покупку"
    }}
  ]
}}

Роли слайдов по порядку: hook (цепляет), benefit (главное преимущество),
spec (конкретная характеристика), social_proof (рейтинг/отзывы если есть), cta (призыв).
Headline и subheadline — только из фактов выше."""


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
    "Работаешь ТОЛЬКО с предоставленными фактами. "
    "Ответ СТРОГО в формате JSON без markdown-обёртки."
)


def _ugc_prompt(p: ProductData) -> str:
    return f"""Создай сценарий UGC-ролика для товара.

{_facts_inventory(p)}
{_HARD_RULE}

Сцены, действия и закадровый текст — только на основе реальных фактов о товаре.
Не придумывай сцены с эффектами которых нет в фактах.

Верни JSON:
{{
  "duration":  "15-30 сек",
  "format":    "9:16 вертикальное",
  "hook_text": "текст/действие для первых 3 секунд — цепляет за боль или любопытство",
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
