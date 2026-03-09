"""
Design concepts handler.

Step 7: Generate & display 5 detailed text design TZ (technical specs).
Step 8: Render 5 card mockup images using Pillow (product photo + text + concept colors).
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery

from keyboards import after_design_keyboard, after_visuals_keyboard
from logger_setup import log_error, log_event
from services.card_renderer import render_card
from services.openrouter import generate_design_concepts
from states import Dialog
from utils.images import send_step_image

router = Router()

_MARKETPLACE = {"wb": "WB", "ozon": "Ozon"}
_CATEGORY = {
    "clothing":    "Одежда",
    "electronics": "Электроника",
    "home":        "Дом и интерьер",
    "beauty":      "Красота и уход",
    "accessories": "Аксессуары",
    "other":       "Другое",
}

_CONTENT_BLOCKS = (
    "📋 Контент-блоки карточки\n"
    "▸ Зона 1: главный визуал товара (hero shot)\n"
    "▸ Зона 2: SEO-заголовок / оффер\n"
    "▸ Зона 3: 3–5 буллетов с ключевыми выгодами\n"
    "▸ Зона 4: USP-строка или призыв к действию"
)


def _format_concept(concept: dict, title: str, marketplace: str, category: str) -> str:
    index       = concept.get("index",       "?")
    name        = concept.get("name",        "Концепт")
    colors      = concept.get("colors",      "—")
    typography  = concept.get("typography",  "—")
    composition = concept.get("composition", "—")

    mp  = _MARKETPLACE.get(marketplace, marketplace)
    cat = _CATEGORY.get(category, category)

    return (
        f"КОНЦЕПТ {index}/5 — «{name}»\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Товар: {title}\n"
        f"Маркетплейс: {mp} · Категория: {cat}\n\n"
        f"🎨 Цветовая палитра\n{colors}\n\n"
        f"🔤 Типографика\n{typography}\n\n"
        f"🧩 Композиция\n{composition}\n\n"
        f"{_CONTENT_BLOCKS}\n\n"
        f"📐 Технические требования\n"
        f"▸ Формат: 1:1 (1000×1000px) или 3:4 (700×900px)\n"
        f"▸ Safe zone: 8–10% от краёв\n"
        f"▸ Текст читается на мобильном с первого взгляда\n"
        f"▸ Паттерн топ-карточек {mp} в категории «{cat}»"
    )


# ── Step 7: Generate text design TZ ───────────────────────────────────────────
@router.callback_query(F.data == "action:design_concepts")
async def cb_design_concepts(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    await callback.answer()

    log_event(user.id, user.username, "design_concepts_requested")

    data        = await state.get_data()
    title       = data.get("title",       "Товар")
    category    = data.get("category",    "other")
    marketplace = data.get("marketplace", "wb")

    # Progress message
    progress_msg = await send_step_image(
        callback.message,
        step="design_concepts",
        caption=(
            "📐 <b>Генерирую 5 текстовых ТЗ для дизайна...</b>\n\n"
            "Получишь подробное ТЗ для каждого стиля — передай дизайнеру или оцени сам.\n"
            "Обычно 15–30 секунд."
        ),
    )

    await state.set_state(Dialog.design_concepts)

    try:
        concepts = await generate_design_concepts(
            user_id     = user.id,
            username    = user.username,
            title       = title,
            category    = category,
            marketplace = marketplace,
        )
    except Exception as exc:
        log_error(user.id, user.username, "design_concepts", str(exc))
        try:
            await progress_msg.delete()
        except Exception:
            pass
        await callback.message.answer(
            "😔 Не удалось сгенерировать концепты. Попробуй ещё раз — нажми кнопку выше.",
            reply_markup=after_design_keyboard(),
        )
        return

    try:
        await progress_msg.delete()
    except Exception:
        pass

    if not concepts:
        await callback.message.answer(
            "😔 Получили пустой ответ от AI. Попробуй ещё раз.",
            reply_markup=after_design_keyboard(),
        )
        return

    await state.update_data(concepts=concepts)

    for concept in concepts:
        text = _format_concept(concept, title, marketplace, category)
        await callback.message.answer(text)  # plain text — hex codes safe without HTML

    log_event(user.id, user.username, "design_concepts_shown", {"count": len(concepts)})

    await send_step_image(
        callback.message,
        step="visual_concepts",
        caption=(
            "🖼 <b>Хочешь увидеть визуальные макеты?</b>\n\n"
            "Нажми кнопку ниже — сгенерирую 5 карточек с фото твоего товара "
            "в цветах каждого концепта."
        ),
        reply_markup=after_design_keyboard(),
    )


# ── Step 8: Render visual card mockups ────────────────────────────────────────
@router.callback_query(F.data == "action:visual_concepts")
async def cb_visual_concepts(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    await callback.answer()

    log_event(user.id, user.username, "visual_concepts_requested")

    data        = await state.get_data()
    concepts    = data.get("concepts",    [])
    title       = data.get("title",       "Товар")
    card        = data.get("card",        {})
    photo_bytes = data.get("photo_bytes", None)

    if not concepts:
        await callback.message.answer(
            "Сначала нажми «Сгенерировать дизайн-концепты» — "
            "мне нужны текстовые концепты для генерации изображений."
        )
        return

    if not photo_bytes:
        await callback.message.answer(
            "😔 Фото товара не найдено в сессии. Начни новую карточку через /start."
        )
        return

    progress_msg = await send_step_image(
        callback.message,
        step="generating",
        caption=(
            "⏳ <b>Рендерю визуальные макеты карточек...</b>\n\n"
            f"Вставляю фото товара в 5 концептов для <b>{title}</b>.\n"
            "Обычно занимает 10–20 секунд."
        ),
    )

    await state.set_state(Dialog.visual_concepts)

    features       = card.get("features", []) if card else []
    generated_count = 0
    failed_count    = 0

    for concept in concepts:
        index  = concept.get("index",  1)
        name   = concept.get("name",   "Концепт")
        colors = concept.get("colors", "#FFFFFF · #1A237E · #FFD700")

        try:
            image_bytes = render_card(
                photo_bytes = photo_bytes,
                title       = title,
                features    = features,
                colors_str  = colors,
            )
            await callback.message.answer_photo(
                photo   = BufferedInputFile(image_bytes, filename=f"card_concept_{index}.png"),
                caption = f"<b>Концепт {index}/5 — {name}</b>\n{colors}",
                parse_mode = "HTML",
            )
            generated_count += 1
        except Exception as exc:
            log_error(user.id, user.username, f"render_card_{index}", str(exc))
            failed_count += 1
            await callback.message.answer(
                f"⚠️ Концепт {index}/5 — <b>{name}</b>\nНе удалось создать макет.",
                parse_mode="HTML",
            )

    try:
        await progress_msg.delete()
    except Exception:
        pass

    if generated_count > 0:
        summary = (
            f"✅ <b>Готово!</b> Создано {generated_count} из {len(concepts)} макетов.\n\n"
            "Сохрани понравившиеся — они готовы к передаче дизайнеру или использованию на маркетплейсе."
        )
        if failed_count > 0:
            summary += f"\n\n⚠️ {failed_count} макетов не удалось создать."
    else:
        summary = "😔 Не удалось создать ни одного макета. Попробуй начать заново."

    log_event(user.id, user.username, "visual_concepts_done", {
        "generated": generated_count,
        "failed":    failed_count,
        "total":     len(concepts),
    })

    await callback.message.answer(
        summary,
        parse_mode  = "HTML",
        reply_markup = after_visuals_keyboard(),
    )
