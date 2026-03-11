"""
Генерация текстов: листинг, реклама, инфографика, UGC.

АНТИГАЛЛЮЦИНАЦИОННАЯ СИСТЕМА v3 — двухшаговая генерация:
  Шаг 1: LLM перечисляет ТОЛЬКО факты из ТЗ (явная верификация).
  Шаг 2: LLM генерирует текст ИСКЛЮЧИТЕЛЬНО из этого списка.

  Если в шаге 1 список фактов пустой или слишком короткий —
  бот не фантазирует, а выдаёт минималистичный честный результат.

Инфографика Blueprint v2:
  Категорийные сценарии слайдов — разный порядок и роли
  для одежды, электроники, красоты, дома, аксессуаров.
"""

from typing import Any

from models.product_data import ProductData
from services import openrouter as llm

# ─── Факты ────────────────────────────────────────────────────────────────────

_CAT_NAMES = {
    "clothing": "Одежда", "electronics": "Электроника",
    "home": "Дом и интерьер", "beauty": "Красота и уход",
    "accessories": "Аксессуары", "other": "Другое",
}


def _facts_inventory(p: ProductData) -> str:
    """Явный список фактов. Только реальные данные из ProductData."""
    facts = []
    if p.title:       facts.append(f"• Название: {p.title}")
    if p.brand:       facts.append(f"• Бренд: {p.brand}")
    if p.category and p.category != "other":
        facts.append(f"• Категория: {_CAT_NAMES.get(p.category, p.category)}")
    if p.marketplace:
        mp = {"wb": "Wildberries", "ozon": "Ozon"}.get(p.marketplace, p.marketplace)
        facts.append(f"• Маркетплейс: {mp}")
    if p.price:       facts.append(f"• Цена: {p.price}₽")
    if p.rating:      facts.append(f"• Рейтинг: {p.rating}/5 ({p.reviews_count} отзывов)")
    if p.description: facts.append(f"• Описание: {p.description[:500]}")
    if p.benefits:    facts.append(f"• Преимущества (от продавца): {p.benefits[:500]}")

    if not facts:
        return "⚠️ ДАННЫХ НЕТ. Работай только с названием, не придумывай ничего."

    suffix = ""
    if len(facts) < 4:
        suffix = (
            "\n\n⚠️ ДАННЫХ МАЛО — используй только то что выше. "
            "Короткий честный текст лучше длинного выдуманного."
        )
    return "РАЗРЕШЁННЫЕ ФАКТЫ:\n" + "\n".join(facts) + suffix


# Жёсткий запрет — вставляется в каждый промпт
_HARD_RULE = (
    "\n\nЖЁСТКИЙ ЗАПРЕТ (нарушение = брак):\n"
    "✗ материалы, ткань, состав — если не указано явно\n"
    "✗ запахи, вкусы, температурные эффекты\n"
    "✗ размеры, вес, объём — если не указано явно\n"
    "✗ «популярный выбор», «любимый миллионами», «выбор экспертов»\n"
    "✗ сертификаты, стандарты, награды — если не указано явно\n"
    "✗ любые характеристики, которых нет в разрешённых фактах выше\n"
    "Перед каждым утверждением мысленно спроси: «это есть в фактах?»"
)


# ─── Листинг ──────────────────────────────────────────────────────────────────

_LISTING_SYSTEM = (
    "Ты — копирайтер для WB/Ozon. Пишешь СТРОГО по фактам. "
    "Перед генерацией текста СНАЧАЛА перечисли в поле used_facts "
    "только те пункты из фактов, которые ты реально используешь. "
    "Ответ СТРОГО в JSON без markdown."
)


def _listing_prompt(p: ProductData) -> str:
    mp = {"wb": "Wildberries", "ozon": "Ozon"}.get(p.marketplace, p.marketplace)
    return f"""Текст карточки для {mp}.

{_facts_inventory(p)}
{_HARD_RULE}

Верни JSON:
{{
  "used_facts": ["факт 1 из списка выше", "факт 2"],
  "title":       "SEO-заголовок 50-80 символов",
  "subtitle":    "Подзаголовок до 100 символов",
  "description": "Описание 300-500 символов",
  "features":    ["✅ Преимущество 1", "✅ Преимущество 2"],
  "specs":       ["Характеристика: значение"],
  "hashtags":    ["#тег1", "#тег2", "#тег3"]
}}

features и specs — только из used_facts. Лучше 2 реальных, чем 5 выдуманных."""


async def generate_listing_copy(p: ProductData, user_id: int, username: str | None) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": _LISTING_SYSTEM},
        {"role": "user",   "content": _listing_prompt(p)},
    ]
    raw = await llm.call(messages, user_id=user_id, username=username, service="listing_copy")
    return llm.parse_json(raw)


# ─── Рекламный копипак ────────────────────────────────────────────────────────

_AD_SYSTEM = (
    "Ты — директ-рекламный копирайтер e-commerce. "
    "Пишешь конкретные тексты ТОЛЬКО по предоставленным фактам. "
    "Ответ СТРОГО в JSON без markdown."
)


def _ad_prompt(p: ProductData) -> str:
    return f"""Рекламный копипак для товара.

{_facts_inventory(p)}
{_HARD_RULE}

Хуки строятся на КОНКРЕТНЫХ преимуществах из фактов.
Не используй «лучший», «премиальный», «топовый» без подтверждения фактами.

Верни JSON:
{{
  "hooks": [
    "Хук 1 — боль → решение из реальных фактов (10-18 слов)",
    "Хук 2 — конкретный вопрос к ЦА",
    "Хук 3 — результат/выгода из фактов",
    "Хук 4 — конкретная цифра или характеристика из фактов",
    "Хук 5 — lifestyle контекст (только если факты это поддерживают)"
  ],
  "copy_short": [
    "1 предложение для объявления — из фактов",
    "Вариант 2",
    "Вариант 3"
  ],
  "copy_medium": [
    "2-3 предложения для поста — из фактов",
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


# ─── Инфографика Blueprint v2 — категорийные сценарии ────────────────────────

# Порядок и роли слайдов для каждой категории
_CATEGORY_SLIDE_PLANS = {
    "clothing": [
        ("hook",         "Зацепи взгляд — силуэт, крой, образ"),
        ("benefit",      "Главное преимущество — комфорт, посадка, стиль"),
        ("spec",         "Состав / размерный ряд / уход"),
        ("usage",        "Сцена использования — где и как носить"),
        ("cta",          "Призыв + укрепление доверия"),
    ],
    "electronics": [
        ("hook",         "Главная фича — то ради чего берут"),
        ("spec",         "Ключевые характеристики — цифры, мощность, совместимость"),
        ("benefit",      "Что это даёт пользователю в жизни"),
        ("comparison",   "Чем лучше типичной альтернативы"),
        ("cta",          "Призыв + гарантия/доставка"),
    ],
    "beauty": [
        ("hook",         "Результат — до/после или трансформация"),
        ("benefit",      "Главный эффект — из состава или применения"),
        ("spec",         "Состав / объём / кому подходит"),
        ("usage",        "Как и когда применять"),
        ("cta",          "Призыв + безопасность/тест"),
    ],
    "home": [
        ("hook",         "Настроение — как выглядит в интерьере"),
        ("benefit",      "Главная польза — удобство, эстетика, функция"),
        ("spec",         "Размеры / материал / уход"),
        ("usage",        "Сцена использования — кухня, спальня, гостиная"),
        ("cta",          "Призыв + подходит для подарка"),
    ],
    "accessories": [
        ("hook",         "Образ — с чем носить, как смотрится"),
        ("benefit",      "Главное преимущество — качество, универсальность"),
        ("spec",         "Материал / размер / цвета"),
        ("usage",        "Сцена — повседневное/вечернее/деловое"),
        ("cta",          "Призыв + подарочная упаковка"),
    ],
    "other": [
        ("hook",         "Главный крючок — боль или желание"),
        ("benefit",      "Ключевая выгода"),
        ("spec",         "Конкретные характеристики"),
        ("social_proof", "Рейтинг / отзывы / подтверждение"),
        ("cta",          "Призыв к действию"),
    ],
}


def _slide_plan_text(category: str) -> str:
    plan = _CATEGORY_SLIDE_PLANS.get(category, _CATEGORY_SLIDE_PLANS["other"])
    lines = []
    for i, (role, intent) in enumerate(plan, 1):
        lines.append(f"  Слайд {i}: role={role} | задача: {intent}")
    return "\n".join(lines)


_INFOGRAPHIC_SYSTEM = (
    "Ты — арт-директор и стратег карточек маркетплейсов. "
    "Создаёшь blueprint инфографики с учётом категории товара. "
    "Каждый слайд — конкретная роль в воронке покупки. "
    "Работаешь ТОЛЬКО с предоставленными фактами. "
    "Ответ СТРОГО в JSON без markdown."
)


def _infographic_prompt(p: ProductData) -> str:
    cat  = p.category or "other"
    plan = _slide_plan_text(cat)
    cat_name = _CAT_NAMES.get(cat, "Другое")

    return f"""Blueprint инфографики для карточки. Категория: {cat_name}.

{_facts_inventory(p)}
{_HARD_RULE}

СЦЕНАРИЙ ДЛЯ КАТЕГОРИИ «{cat_name}» (используй этот порядок):
{plan}

Для каждого слайда из сценария создай спецификацию.
Headline и subheadline — ТОЛЬКО из разрешённых фактов.

Верни JSON:
{{
  "category": "{cat_name}",
  "slides": [
    {{
      "number":           1,
      "role":             "hook",
      "intent":           "что должен сделать этот слайд с покупателем",
      "headline":         "2-4 слова — из фактов",
      "subheadline":      "до 8 слов — из фактов",
      "icon":             "english-icon-keyword",
      "visual_hierarchy": "headline_dominant | icon_dominant | split",
      "color_mood":       "light | dark | accent",
      "seo_keyword":      "ключевое слово",
      "sells_because":    "почему этот слайд влияет на покупку — 1 фраза"
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
    "Создаёшь практичные сценарии (15-60 сек) которые продавец снимет сам. "
    "Работаешь ТОЛЬКО с предоставленными фактами. "
    "Ответ СТРОГО в JSON без markdown."
)


def _ugc_prompt(p: ProductData) -> str:
    return f"""Сценарий UGC-ролика.

{_facts_inventory(p)}
{_HARD_RULE}

Верни JSON:
{{
  "duration":  "15-30 сек",
  "format":    "9:16 вертикальное",
  "hook_text": "первые 3 секунды — боль или любопытство из фактов",
  "scenes": [
    {{"number": 1, "time": "0-3 сек",  "action": "...", "voiceover": "..."}},
    {{"number": 2, "time": "3-10 сек", "action": "...", "voiceover": "..."}},
    {{"number": 3, "time": "10-20 сек","action": "...", "voiceover": "..."}},
    {{"number": 4, "time": "20-30 сек","action": "...", "voiceover": "..."}}
  ],
  "cta": "призыв к действию"
}}"""


async def generate_ugc_scenario(p: ProductData, user_id: int, username: str | None) -> dict[str, Any]:
    messages = [
        {"role": "system", "content": _UGC_SYSTEM},
        {"role": "user",   "content": _ugc_prompt(p)},
    ]
    raw = await llm.call(messages, user_id=user_id, username=username, service="ugc")
    return llm.parse_json(raw)
