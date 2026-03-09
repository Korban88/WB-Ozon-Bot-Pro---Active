"""
Design concepts handler.

Step 7: Generate & display 5 detailed text design TZ (technical specs).
Step 8: Render 5 card mockup images using OpenAI gpt-image-1 (Pillow fallback).
"""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery

from keyboards import after_design_keyboard, after_visuals_keyboard
from logger_setup import log_error, log_event
from services.card_renderer import overlay_text_on_image, render_card
from services.openai_image import build_image_prompt, generate_card_image
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

# Эмодзи-номера для концептов
_INDEX_EMOJI = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣"}


def _e(text: str) -> str:
    """Escape HTML special characters in dynamic content."""
    return html.escape(str(text))


def _format_concept(concept: dict, title: str, marketplace: str, category: str) -> str:
    """Format one TZ concept as a styled HTML message."""
    index       = concept.get("index",       1)
    name        = concept.get("name",        "Концепт")
    colors      = concept.get("colors",      "—")
    typography  = concept.get("typography",  "—")
    composition = concept.get("composition", "—")

    mp  = _MARKETPLACE.get(marketplace, marketplace)
    cat = _CATEGORY.get(category, category)
    num = _INDEX_EMOJI.get(index, f"{index}.")

    # Typography may contain \n — split into lines for italic formatting
    typo_lines = _e(typography).replace("\\n", "\n").split("\n")
    typo_html  = "\n".join(f"<i>{line.strip()}</i>" for line in typo_lines if line.strip())

    return (
        f"{num} <b>КОНЦЕПТ {index}/5 — «{_e(name)}»</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>Товар:</b> {_e(title)}\n"
        f"<b>Маркетплейс:</b> {_e(mp)} · <b>Категория:</b> {_e(cat)}\n"
        f"\n"
        f"🎨 <b>Цветовая палитра</b>\n"
        f"<code>{_e(colors)}</code>\n"
        f"\n"
        f"🔤 <b>Типографика</b>\n"
        f"{typo_html}\n"
        f"\n"
        f"🧩 <b>Композиция</b>\n"
        f"{_e(composition)}\n"
        f"\n"
        f"📋 <b>Контент-блоки карточки</b>\n"
        f"▸ Зона 1: главный визуал товара <i>(hero shot)</i>\n"
        f"▸ Зона 2: SEO-заголовок / оффер\n"
        f"▸ Зона 3: 3–5 буллетов с ключевыми выгодами\n"
        f"▸ Зона 4: USP-строка или призыв к действию\n"
        f"\n"
        f"📐 <b>Технические требования</b>\n"
        f"▸ Формат: <code>1:1 (1000×1000px)</code> или <code>3:4 (700×900px)</code>\n"
        f"▸ Safe zone: 8–10% от краёв\n"
        f"▸ Текст читается на мобильном с первого взгляда\n"
        f"▸ Паттерн топ-карточек {_e(mp)} в категории «{_e(cat)}»"
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

    await callback.message.answer(
        "✅ <b>5 дизайн-концептов готовы!</b>\n"
        "Ниже — детальное ТЗ для каждого стиля 👇",
        parse_mode="HTML",
    )

    for concept in concepts:
        text = _format_concept(concept, title, marketplace, category)
        await callback.message.answer(text, parse_mode="HTML")

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
    category    = data.get("category",    "other")    # ← FIX: was missing
    marketplace = data.get("marketplace", "wb")       # ← FIX: was missing
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

    import config as _cfg
    use_openai = bool(_cfg.OPENAI_API_KEY)

    progress_msg = await send_step_image(
        callback.message,
        step="generating",
        caption=(
            "⏳ <b>Генерирую визуальные макеты карточек...</b>\n\n"
            f"{'🤖 OpenAI gpt-image-1' if use_openai else '🎨 Pillow-рендер'} · "
            f"5 концептов для <b>{_e(title)}</b>.\n"
            f"{'Обычно 30–90 секунд.' if use_openai else 'Обычно 5–10 секунд.'}"
        ),
    )

    await state.set_state(Dialog.visual_concepts)

    features        = card.get("features", []) if card else []
    generated_count = 0
    failed_count    = 0

    for concept in concepts:
        index  = concept.get("index",  1)
        name   = concept.get("name",   "Концепт")
        colors = concept.get("colors", "#FFFFFF · #1A237E · #FFD700")

        image_bytes = None

        # ── Primary: OpenAI gpt-image-1 → Pillow text overlay ─────────────────
        if use_openai:
            prompt = build_image_prompt(
                concept     = concept,
                title       = title,
                features    = features,
                marketplace = marketplace,
                category    = category,
            )
            ai_visual = await generate_card_image(
                user_id       = user.id,
                username      = user.username,
                prompt        = prompt,
                photo_bytes   = photo_bytes,
                concept_index = index,
            )
            if ai_visual is not None:
                # Overlay accurate text on the AI-generated visual
                try:
                    image_bytes = overlay_text_on_image(
                        base_bytes = ai_visual,
                        title      = title,
                        features   = features,
                        colors_str = colors,
                    )
                except Exception as exc:
                    log_error(user.id, user.username, f"overlay_{index}", str(exc))
                    image_bytes = ai_visual  # send without overlay if it fails

        # ── Fallback: full Pillow renderer ─────────────────────────────────────
        if image_bytes is None:
            try:
                image_bytes = render_card(
                    photo_bytes = photo_bytes,
                    title       = title,
                    features    = features,
                    colors_str  = colors,
                )
            except Exception as exc:
                log_error(user.id, user.username, f"render_card_{index}", str(exc))

        if image_bytes:
            try:
                await callback.message.answer_photo(
                    photo      = BufferedInputFile(image_bytes, filename=f"card_concept_{index}.png"),
                    caption    = f"<b>Концепт {index}/5 — {_e(name)}</b>\n<code>{_e(colors)}</code>",
                    parse_mode = "HTML",
                )
                generated_count += 1
            except Exception as exc:
                log_error(user.id, user.username, f"send_card_{index}", str(exc))
                failed_count += 1
        else:
            failed_count += 1
            await callback.message.answer(
                f"⚠️ Концепт {index}/5 — <b>{_e(name)}</b>\nНе удалось создать макет.",
                parse_mode="HTML",
            )

    try:
        await progress_msg.delete()
    except Exception:
        pass

    if generated_count > 0:
        summary = (
            f"✅ <b>Готово!</b> Создано {generated_count} из {len(concepts)} макетов.\n\n"
            "Сохрани понравившиеся — они готовы к передаче дизайнеру "
            "или использованию на маркетплейсе."
        )
        if failed_count > 0:
            summary += f"\n\n⚠️ {failed_count} макетов не удалось создать."
    else:
        summary = "😔 Не удалось создать ни одного макета. Попробуй начать заново через /start."

    log_event(user.id, user.username, "visual_concepts_done", {
        "generated": generated_count,
        "failed":    failed_count,
        "total":     len(concepts),
    })

    await callback.message.answer(
        summary,
        parse_mode   = "HTML",
        reply_markup = after_visuals_keyboard(),
    )
