"""
Design concepts handler.

Step 7: Generate & display 5 detailed text design TZ (technical specs).
Step 8: Generate visual card mockups via 3-layer pipeline:
    Layer 1 → gpt-image-1 generates styled background (empty, no product, no text)
    Layer 2 → rembg removes product background + Pillow composites product with shadow
    Layer 3 → Pillow overlays accurate text (title + features)
    Fallback → Pillow-only card if OpenAI unavailable
"""

import html

import config as _cfg
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery

from keyboards import after_design_keyboard, after_visuals_keyboard
from logger_setup import log_error, log_event
from services.card_renderer import render_card
from services.card_types import get_card_types, TYPE_LABELS_RU
from services.scene_gen import generate_scene
from services.openrouter import generate_design_concepts
from services.color_extractor import extract_dominant_colors, get_color_description
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

_INDEX_EMOJI = {1: "1️⃣", 2: "2️⃣", 3: "3️⃣", 4: "4️⃣", 5: "5️⃣"}


def _e(text: str) -> str:
    return html.escape(str(text))


def _format_concept(concept: dict, title: str, marketplace: str, category: str) -> str:
    index       = concept.get("index",       1)
    name        = concept.get("name",        "Концепт")
    colors      = concept.get("colors",      "—")
    typography  = concept.get("typography",  "—")
    composition = concept.get("composition", "—")

    mp  = _MARKETPLACE.get(marketplace, marketplace)
    cat = _CATEGORY.get(category, category)
    num = _INDEX_EMOJI.get(index, f"{index}.")

    typo_lines = _e(typography).replace("\\n", "\n").split("\n")
    typo_html  = "\n".join(f"<i>{ln.strip()}</i>" for ln in typo_lines if ln.strip())

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


# ── Step 8: Visual card mockups (3-layer pipeline) ─────────────────────────────
@router.callback_query(F.data == "action:visual_concepts")
async def cb_visual_concepts(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    await callback.answer()

    log_event(user.id, user.username, "visual_concepts_requested")

    data        = await state.get_data()
    concepts    = data.get("concepts",    [])
    title       = data.get("title",       "Товар")
    category    = data.get("category",    "other")
    marketplace = data.get("marketplace", "wb")
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

    use_openai = bool(_cfg.OPENAI_API_KEY)

    # ── Extract product colors ONCE (scenes and typography use product palette) ──
    try:
        dominant_colors = extract_dominant_colors(photo_bytes, n_colors=3)
        color_mood = get_color_description(dominant_colors)
    except Exception:
        color_mood = "neutral"
    log_event(user.id, user.username, "colors_extracted", {"color_mood": color_mood})

    progress_msg = await send_step_image(
        callback.message,
        step="generating",
        caption=(
            "⏳ <b>Генерирую карточки...</b>\n\n"
            + (
                f"🎨 Цвета из продукта: <i>{_e(color_mood)}</i>\n"
                "🖼 Сцена генерируется без продукта\n"
                "✂️ Продукт вырезается и вставляется слоем\n"
                "✏️ Типографика — Pillow\n\n"
                "5 карточек · обычно 30–60 сек каждая."
                if use_openai else
                f"🎨 Pillow-рендер · цвета из продукта: <i>{_e(color_mood)}</i>"
            )
        ),
    )

    await state.set_state(Dialog.visual_concepts)

    features        = card.get("features", []) if card else []
    subtitle        = card.get("subtitle", "")  if card else ""
    card_types      = get_card_types(category)
    generated_count = 0
    failed_count    = 0

    for concept, card_type in zip(concepts, card_types):
        index      = concept.get("index", 1)
        name       = concept.get("name",  "Концепт")
        type_label = TYPE_LABELS_RU.get(card_type, card_type)
        image_bytes = None

        # ── Scene: EMPTY BACKGROUND only, product is NEVER sent to OpenAI ────
        scene_bytes = None
        if use_openai:
            scene_bytes = await generate_scene(
                card_type     = card_type,
                color_mood    = color_mood,
                user_id       = user.id,
                username      = user.username,
                concept_index = index,
                marketplace   = marketplace,
                category      = category,
            )

        # ── Render: product cutout composited onto scene, Pillow typography ───
        try:
            image_bytes = render_card(
                card_type     = card_type,
                scene_bytes   = scene_bytes,
                product_bytes = photo_bytes,
                title         = title,
                features      = features,
                colors_str    = "",
                subtitle      = subtitle,
            )
        except Exception as exc:
            log_error(user.id, user.username, f"render_{card_type}_{index}", str(exc))

        # ── Send result ────────────────────────────────────────────────────────
        if image_bytes:
            try:
                await callback.message.answer_photo(
                    photo      = BufferedInputFile(image_bytes, filename=f"card_{index}.png"),
                    caption    = (f"<b>{_e(type_label)} — {_e(name)}</b>\n"
                                  f"<i>Цвета из продукта · {_e(color_mood)}</i>"),
                    parse_mode = "HTML",
                )
                generated_count += 1
            except Exception as exc:
                log_error(user.id, user.username, f"send_card_{index}", str(exc))
                failed_count += 1
        else:
            failed_count += 1
            await callback.message.answer(
                f"⚠️ Концепт {index}/5 — <b>{_e(name)}</b>\nНе удалось создать карточку.",
                parse_mode="HTML",
            )

    try:
        await progress_msg.delete()
    except Exception:
        pass

    if generated_count > 0:
        summary = (
            f"✅ <b>Готово!</b> Создано {generated_count} из {len(concepts)} карточек.\n\n"
            "Сохрани понравившиеся — готовы к передаче дизайнеру или использованию на маркетплейсе."
        )
        if failed_count > 0:
            summary += f"\n\n⚠️ {failed_count} карточек не удалось создать."
    else:
        summary = "😔 Не удалось создать ни одной карточки. Попробуй начать заново через /start."

    log_event(user.id, user.username, "visual_concepts_done", {
        "generated": generated_count, "failed": failed_count, "total": len(concepts),
    })

    await callback.message.answer(
        summary, parse_mode="HTML", reply_markup=after_visuals_keyboard(),
    )
