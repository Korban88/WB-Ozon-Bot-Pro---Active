"""
Premium visuals and ad copy handlers.

action:premium_visuals — generate 5 text-free premium visual scenes.
    Pipeline: color extraction → scene gen (gpt-image-1) → product composite (Pillow).
    NO text overlay. Images are clean premium product photography.

action:ad_copy — generate ad copy pack.
    5 hooks, 3 short copy variants, 2 medium copy variants, UGC video brief.
"""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery

from keyboards import after_ad_copy_keyboard, after_visuals_keyboard
from logger_setup import log_error, log_event
from services.card_renderer import render_card
from services.card_types import get_card_types, TYPE_LABELS_RU
from services.scene_gen import generate_scene
from services.openrouter import generate_ad_copy
from services.color_extractor import extract_dominant_colors, get_color_description
from states import Dialog
from utils.images import send_step_image

router = Router()


def _e(text: str) -> str:
    return html.escape(str(text))


# ── Premium Visuals ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "action:premium_visuals")
async def cb_premium_visuals(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    await callback.answer()

    log_event(user.id, user.username, "premium_visuals_requested")

    data        = await state.get_data()
    photo_bytes = data.get("photo_bytes")
    category    = data.get("category",    "other")
    marketplace = data.get("marketplace", "wb")
    title       = data.get("title",       "Товар")

    if not photo_bytes:
        await callback.message.answer(
            "Фото товара не найдено в сессии. Начни новую карточку через /start."
        )
        return

    use_openai = bool(__import__("config").OPENAI_API_KEY)

    # Extract product color palette once
    try:
        dominant_colors = extract_dominant_colors(photo_bytes, n_colors=3)
        color_mood = get_color_description(dominant_colors)
    except Exception:
        color_mood = "neutral warm"
    log_event(user.id, user.username, "colors_extracted", {"color_mood": color_mood})

    progress_msg = await send_step_image(
        callback.message,
        step="generating",
        caption=(
            "⏳ <b>Генерирую 5 Premium Visuals...</b>\n\n"
            + (
                f"Палитра товара: <i>{_e(color_mood)}</i>\n"
                "Сцены генерируются без текста — чистый визуал.\n\n"
                "5 форматов · обычно 30–60 сек на каждый."
                if use_openai else
                f"Pillow-рендер · палитра: <i>{_e(color_mood)}</i>\n"
                "Без текста — чистый визуал."
            )
        ),
    )

    await state.set_state(Dialog.premium_visuals)

    card_types      = get_card_types(category)
    generated_count = 0
    failed_count    = 0

    for i, card_type in enumerate(card_types):
        type_label  = TYPE_LABELS_RU.get(card_type, card_type)
        image_bytes = None

        # Generate empty scene background
        scene_bytes = None
        if use_openai:
            scene_bytes = await generate_scene(
                card_type     = card_type,
                color_mood    = color_mood,
                user_id       = user.id,
                username      = user.username,
                concept_index = i + 1,
                marketplace   = marketplace,
                category      = category,
            )

        # Composite product onto scene — NO text overlay
        try:
            image_bytes = render_card(
                card_type     = card_type,
                scene_bytes   = scene_bytes,
                product_bytes = photo_bytes,
            )
        except Exception as exc:
            log_error(user.id, user.username, f"render_{card_type}_{i+1}", str(exc))

        # Send result
        if image_bytes:
            try:
                await callback.message.answer_photo(
                    photo   = BufferedInputFile(image_bytes, filename=f"visual_{i+1}.png"),
                    caption = f"<b>{i+1}/5 — {_e(type_label)}</b>",
                    parse_mode = "HTML",
                )
                generated_count += 1
            except Exception as exc:
                log_error(user.id, user.username, f"send_visual_{i+1}", str(exc))
                failed_count += 1
        else:
            failed_count += 1
            await callback.message.answer(
                f"⚠️ {i+1}/5 — <b>{_e(type_label)}</b>: не удалось создать.",
                parse_mode="HTML",
            )

    try:
        await progress_msg.delete()
    except Exception:
        pass

    log_event(user.id, user.username, "premium_visuals_done", {
        "generated": generated_count, "failed": failed_count,
    })

    if generated_count > 0:
        summary = (
            f"✅ <b>{generated_count} визуалов готовы.</b>\n\n"
            "Без текста — можно сразу загружать в WB/Ozon или использовать для рекламы.\n"
            "Хочешь рекламный копипак — хуки, тексты объявлений и UGC-бриф?"
        )
    else:
        summary = "Не удалось создать визуалы. Попробуй начать заново через /start."

    await state.set_state(Dialog.show_card)
    await callback.message.answer(
        summary, parse_mode="HTML", reply_markup=after_visuals_keyboard(),
    )


# ── Ad Copy Pack ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "action:ad_copy")
async def cb_ad_copy(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    await callback.answer()

    log_event(user.id, user.username, "ad_copy_requested")

    data        = await state.get_data()
    title       = data.get("title",       "Товар")
    category    = data.get("category",    "other")
    marketplace = data.get("marketplace", "wb")
    benefits    = data.get("benefits",    "")

    progress_msg = await send_step_image(
        callback.message,
        step="generating",
        caption=(
            "⏳ <b>Генерирую Ad Copy Pack...</b>\n\n"
            "5 рекламных хуков · 3 короткие копи · 2 средние копи · UGC-бриф\n"
            "Обычно 10–20 секунд."
        ),
    )

    await state.set_state(Dialog.ad_copy)

    try:
        copy_data = await generate_ad_copy(
            user_id     = user.id,
            username    = user.username,
            title       = title,
            category    = category,
            marketplace = marketplace,
            benefits    = benefits,
        )
    except Exception as exc:
        log_error(user.id, user.username, "ad_copy", str(exc))
        try:
            await progress_msg.delete()
        except Exception:
            pass
        await callback.message.answer(
            "Не удалось сгенерировать копипак. Попробуй ещё раз.",
            reply_markup=after_ad_copy_keyboard(),
        )
        return

    try:
        await progress_msg.delete()
    except Exception:
        pass

    # Format and send
    hooks       = copy_data.get("hooks",        [])
    copy_short  = copy_data.get("copy_short",   [])
    copy_medium = copy_data.get("copy_medium",  [])
    ugc_brief   = copy_data.get("ugc_brief",    "")

    text = f"📣 <b>Ad Copy Pack — {_e(title)}</b>\n\n"

    if hooks:
        text += "⚡️ <b>Рекламные хуки</b>\n"
        for i, hook in enumerate(hooks, 1):
            text += f"{i}. {_e(hook)}\n"
        text += "\n"

    if copy_short:
        text += "✍️ <b>Короткие тексты</b> <i>(для объявлений)</i>\n"
        for i, c in enumerate(copy_short, 1):
            text += f"{i}. {_e(c)}\n"
        text += "\n"

    if copy_medium:
        text += "📝 <b>Тексты для постов</b>\n"
        for i, c in enumerate(copy_medium, 1):
            text += f"\n<b>Вариант {i}:</b>\n{_e(c)}\n"
        text += "\n"

    if ugc_brief:
        text += f"🎬 <b>UGC-бриф</b>\n{_e(ugc_brief)}"

    await callback.message.answer(text, parse_mode="HTML")

    log_event(user.id, user.username, "ad_copy_done", {"title": title})

    await state.set_state(Dialog.show_card)
    await callback.message.answer(
        "Копипак готов. Бери и используй в рекламе, описании или UGC.",
        reply_markup=after_ad_copy_keyboard(),
    )
