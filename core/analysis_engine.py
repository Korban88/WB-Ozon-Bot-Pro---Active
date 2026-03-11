"""
Card Audit Engine v3 — аудит карточки + конкурентный анализ.

Принимает:
  - product_brief: данные карточки
  - competitors: список конкурентов из WB search (опционально)
  - marketplace, user_id, username

Выдаёт структурированный аудит:
  CTR-риски → Конверсионные риски → Конкурентная картина →
  Quick Wins → Стратегические улучшения → Пример улучшенного заголовка

Правило: только данные из product_brief и competitors. Ничего выдуманного.
"""

from services import openrouter as llm

_SYSTEM = """Ты — эксперт по росту продаж на маркетплейсах Wildberries и Ozon.
Специализация: аудит карточек, рост CTR, конкурентный анализ, оптимизация конверсии.
Даёшь жёсткие, конкретные, честные рекомендации без воды.
Не придумываешь данные о рынке — анализируешь только то, что предоставлено."""


def _format_competitors(competitors: list[dict]) -> str:
    if not competitors:
        return ""
    lines = ["КОНКУРЕНТЫ (топ поисковой выдачи по схожему запросу):"]
    for i, c in enumerate(competitors, 1):
        line = f"  {i}. {c.get('title', '—')[:60]}"
        if c.get("brand"):    line += f" | {c['brand']}"
        if c.get("price"):    line += f" | {c['price']}₽"
        if c.get("rating"):   line += f" | ⭐{c['rating']}"
        if c.get("reviews"):  line += f" ({c['reviews']} отз.)"
        lines.append(line)
    return "\n".join(lines)


def _prompt(brief: str, marketplace: str, competitors: list[dict]) -> str:
    mp = {"wb": "Wildberries", "ozon": "Ozon"}.get(marketplace, marketplace)
    comp_block = _format_competitors(competitors)

    return f"""Проведи аудит карточки товара на {mp}.

ДАННЫЕ КАРТОЧКИ:
{brief}

{comp_block}

Структура аудита — СТРОГО по этим блокам:

━━━ 🎯 CTR-РИСКИ (что мешает кликать) ━━━
— Заголовок/название: X/10
  Проблема: [конкретно что не так — ключи, длина, позиционирование]
— Главное фото (по описанию): X/10
  Проблема: [что вероятно слабо или чего не хватает]
— Цена и рейтинг: X/10

━━━ 💰 КОНВЕРСИОННЫЕ РИСКИ (что мешает покупать) ━━━
— Описание: X/10
— УТП и отстройка: X/10
— Инфографика (по данным): X/10

{"━━━ 🔍 КОНКУРЕНТНАЯ КАРТИНА ━━━" if competitors else ""}
{"Сравни с конкурентами выше. Укажи:" if competitors else ""}
{"— Где карточка проигрывает по цене/рейтингу/отзывам" if competitors else ""}
{"— Чего нет в нашей карточке, что есть у конкурентов (по названиям)" if competitors else ""}
{"— Что можно сделать лучше" if competitors else ""}

━━━ ⚡ QUICK WINS (сделать за 1-2 дня) ━━━
[3-5 конкретных действий с прогнозируемым эффектом]

━━━ 📈 СТРАТЕГИЧЕСКИЕ УЛУЧШЕНИЯ ━━━
[2-3 более сложных улучшения на 1-2 недели]

━━━ ✍️ ПРИМЕР УЛУЧШЕННОГО ЗАГОЛОВКА ━━━
Было: [текущий заголовок]
Стало: [SEO-улучшенный вариант с ключевыми словами]
Почему лучше: [1 строка]

Важно: анализируй только предоставленные данные. Если чего-то нет — укажи это как риск."""


async def analyze_card(
    product_brief: str,
    marketplace:   str,
    user_id:       int,
    username:      str | None,
    competitors:   list[dict] | None = None,
) -> str:
    """
    Аудит карточки + конкурентный анализ (если переданы конкуренты).
    Возвращает форматированный текст.
    """
    messages = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user",   "content": _prompt(product_brief, marketplace, competitors or [])},
    ]
    return await llm.call(messages, user_id=user_id, username=username, service="analysis")
