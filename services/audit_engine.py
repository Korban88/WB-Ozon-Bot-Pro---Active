"""
Audit Engine — deterministic CTR score from product metrics.

Правило: никакого LLM. Скоринг прозрачный и воспроизводимый.
Используется в bot/analysis.py ПЕРЕД LLM-анализом — добавляет
конкретные метрики к структурированному аудиту.

Принимает: ProductData
Возвращает: dict с score, label, emoji, problems, recommendations, factors
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.product_data import ProductData

log = logging.getLogger(__name__)


def calculate_ctr_score(product: "ProductData") -> dict:
    """
    Deterministic CTR score from concrete product metrics.

    Returns:
      score:           int 0-99
      label:           str ("Сильная карточка" / "Средняя" / "Слабая" / "Критически слабая")
      emoji:           str (🟢/🟡/🟠/🔴)
      problems:        list[str] — up to 3 main issues
      recommendations: list[str] — up to 3 specific actions
      factors:         dict[str, str] — metric name → status string
    """
    score           = 50
    problems        = []
    recommendations = []
    factors         = {}

    # ── Title ────────────────────────────────────────────────────
    title = product.title or ""
    tlen  = len(title)

    if tlen == 0:
        score -= 20
        problems.append("Название отсутствует")
        recommendations.append("Добавь SEO-название 60-80 символов с ключевыми словами категории")
        factors["Название"] = "❌ нет"
    elif tlen < 30:
        score -= 12
        problems.append(f"Название слишком короткое ({tlen} симв.) — теряется поисковый трафик")
        recommendations.append("Расширь название до 60-80 символов: ключевые слова + характеристики")
        factors["Название"] = f"⚠️ {tlen} симв."
    elif tlen > 100:
        score -= 5
        problems.append(f"Название слишком длинное ({tlen} симв.) — обрезается в выдаче")
        recommendations.append("Сократи до 80 символов — остальное перенеси в описание")
        factors["Название"] = f"⚠️ {tlen} симв."
    else:
        score += 10
        factors["Название"] = f"✅ {tlen} симв."

    # ── Rating ───────────────────────────────────────────────────
    rating = float(product.rating or 0)

    if rating == 0:
        score -= 10
        problems.append("Нет рейтинга — покупатели видят риск, алгоритм занижает позиции")
        recommendations.append("Первые 10-20 отзывов критичны — добавь открытку в упаковку")
        factors["Рейтинг"] = "❌ нет"
    elif rating < 4.0:
        score -= 15
        problems.append(f"Низкий рейтинг {rating:.1f} — WB/Ozon автоматически понижают позиции")
        recommendations.append(f"Разбери причины негатива в отзывах. Цель: минимум 4.5")
        factors["Рейтинг"] = f"⚠️ {rating:.1f}"
    elif rating < 4.5:
        score += 5
        factors["Рейтинг"] = f"✓ {rating:.1f}"
    else:
        score += 15
        factors["Рейтинг"] = f"✅ {rating:.1f}"

    # ── Reviews ──────────────────────────────────────────────────
    reviews = int(product.reviews_count or 0)

    if reviews == 0:
        score -= 15
        problems.append("Нет отзывов — главный барьер для первой покупки")
        recommendations.append("Вложи в упаковку открытку с QR-кодом и просьбой оставить отзыв")
        factors["Отзывы"] = "❌ нет"
    elif reviews < 10:
        score -= 8
        factors["Отзывы"] = f"⚠️ {reviews} (очень мало)"
    elif reviews < 50:
        score += 3
        factors["Отзывы"] = f"{reviews}"
    elif reviews < 500:
        score += 10
        factors["Отзывы"] = f"✅ {reviews}"
    else:
        score += 15
        factors["Отзывы"] = f"✅ {reviews}"

    # ── Photos ───────────────────────────────────────────────────
    images = int(product.images_count or 0)

    if images > 0:
        if images < 4:
            score -= 10
            problems.append(f"Мало фотографий ({images}) — покупатель не может изучить товар")
            recommendations.append("Добавь 7-10 фото: крупные планы, инфографику, lifestyle, размерную сетку")
            factors["Фото"] = f"⚠️ {images}"
        elif images < 7:
            score -= 3
            recommendations.append("Оптимум — 8-10 фото. Добавь инфографику и lifestyle-снимки")
            factors["Фото"] = f"✓ {images}"
        else:
            score += 10
            factors["Фото"] = f"✅ {images}"

    # ── Discount ─────────────────────────────────────────────────
    discount = product.discount_pct

    if discount >= 30:
        score += 8
        factors["Скидка"] = f"✅ -{discount}%"
    elif discount > 0:
        score += 3
        factors["Скидка"] = f"-{discount}%"

    # ── Brand ────────────────────────────────────────────────────
    brand = (product.brand or "").strip()

    if not brand or brand.lower() in ("нет бренда", "no brand", "без бренда"):
        score -= 5
        factors["Бренд"] = "⚠️ нет"
    else:
        score += 3
        factors["Бренд"] = f"✅ {brand}"

    # ── Clamp and label ──────────────────────────────────────────
    score = max(5, min(99, score))

    if score >= 75:
        label, emoji = "Сильная карточка", "🟢"
    elif score >= 55:
        label, emoji = "Средняя карточка", "🟡"
    elif score >= 35:
        label, emoji = "Слабая карточка", "🟠"
    else:
        label, emoji = "Критически слабая", "🔴"

    return {
        "score":           score,
        "label":           label,
        "emoji":           emoji,
        "problems":        problems[:3],
        "recommendations": recommendations[:3],
        "factors":         factors,
    }


def format_ctr_block(ctr: dict) -> str:
    """
    Форматирует CTR score как HTML-блок для вставки в сообщение аудита.
    """
    score   = ctr["score"]
    label   = ctr["label"]
    emoji   = ctr["emoji"]
    filled  = score // 10
    bar     = "█" * filled + "░" * (10 - filled)
    factors = ctr.get("factors", {})

    lines = [
        "━━━ 📊 CTR-ОЦЕНКА (автоматическая) ━━━",
        f"{emoji} <b>{label}</b>",
        f"<code>{bar}  {score}/100</code>",
    ]

    if factors:
        lines.append("")
        for name, val in factors.items():
            lines.append(f"  <b>{name}:</b> {val}")

    problems = ctr.get("problems", [])
    if problems:
        lines += ["", "<b>Ключевые риски:</b>"]
        for p in problems:
            lines.append(f"  • {p}")

    recs = ctr.get("recommendations", [])
    if recs:
        lines += ["", "<b>Быстрые действия:</b>"]
        for i, r in enumerate(recs, 1):
            lines.append(f"  {i}. {r}")

    return "\n".join(lines)
