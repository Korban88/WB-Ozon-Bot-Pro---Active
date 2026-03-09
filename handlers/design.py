"""
Design concepts handler.

Covers steps 7-9:
  7. design_concepts    — generate & show 5 text design descriptions
  8. visual_concepts    — generate & show 5 AI images (Together AI)
"""

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InputMediaPhoto

from keyboards import after_design_keyboard, after_visuals_keyboard
from logger_setup import log_error, log_event
from services.image_gen import download_image, generate_image
from services.openrouter import generate_design_concepts
from states import Dialog
from utils.images import send_step_image

router = Router()


# ── Step 7: Generate text design concepts ─────────────────────────────────────
@router.callback_query(F.data == "action:design_concepts")
async def cb_design_concepts(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    await callback.answer()

    log_event(user.id, user.username, "design_concepts_requested")

    data = await state.get_data()
    title      = data.get("title",       "Товар")
    category   = data.get("category",   "other")
    marketplace= data.get("marketplace","wb")

    # Show progress image
    progress_msg = await send_step_image(
        callback.message,
        step="design_concepts",
        caption=(
            "🎨 <b>Генерирую 5 дизайн-концептов...</b>\n\n"
            "Подбираю стили, цвета и композицию специально для твоего товара."
        ),
    )

    await state.set_state(Dialog.design_concepts)

    try:
        concepts = await generate_design_concepts(
            user_id    = user.id,
            username   = user.username,
            title      = title,
            category   = category,
            marketplace= marketplace,
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

    # Save concepts to state (we'll need image_prompts for visual generation)
    await state.update_data(concepts=concepts)

    # Send each concept as a separate message
    await callback.message.answer("✅ <b>5 дизайн-концептов для твоей карточки:</b>", parse_mode="HTML")

    for concept in concepts:
        index       = concept.get("index",       "?")
        name        = concept.get("name",        "Концепт")
        description = concept.get("description", "")

        await callback.message.answer(
            f"<b>Концепт {index}/5 — {name}</b>\n\n{description}",
            parse_mode="HTML",
        )

    log_event(user.id, user.username, "design_concepts_shown", {"count": len(concepts)})

    await send_step_image(
        callback.message,
        step="visual_concepts",
        caption=(
            "🖼 Хочешь увидеть, как это будет выглядеть визуально?\n\n"
            "Нажми кнопку ниже — я сгенерирую 5 изображений карточек."
        ),
        reply_markup=after_design_keyboard(),
    )


# ── Step 8: Generate visual concepts (AI images) ──────────────────────────────
@router.callback_query(F.data == "action:visual_concepts")
async def cb_visual_concepts(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    await callback.answer()

    log_event(user.id, user.username, "visual_concepts_requested")

    data = await state.get_data()
    concepts = data.get("concepts", [])
    title    = data.get("title",    "Товар")

    if not concepts:
        await callback.message.answer(
            "Сначала нажми «Сгенерировать дизайн-концепты» — "
            "мне нужны текстовые концепты для генерации изображений."
        )
        return

    # Show progress
    progress_msg = await send_step_image(
        callback.message,
        step="generating",
        caption=(
            "⏳ <b>Генерирую визуальные концепты...</b>\n\n"
            f"Создаю 5 изображений для <b>{title}</b>.\n"
            "Это может занять 30-60 секунд."
        ),
    )

    await state.set_state(Dialog.visual_concepts)

    # Generate images for all 5 concepts
    generated_count = 0
    failed_count    = 0

    for concept in concepts:
        index        = concept.get("index",        1)
        name         = concept.get("name",         "Концепт")
        image_prompt = concept.get("image_prompt", f"product card for {title}, commercial photography")

        # Generate image URL via Together AI
        url = await generate_image(
            user_id       = user.id,
            username      = user.username,
            prompt        = image_prompt,
            concept_index = index,
        )

        if url is None:
            failed_count += 1
            await callback.message.answer(
                f"⚠️ Концепт {index}/5 — <b>{name}</b>\n"
                f"Не удалось сгенерировать изображение.",
                parse_mode="HTML",
            )
            continue

        # Download image and send as binary (Telegram can't always reach CDNs)
        image_bytes = await download_image(url)

        if image_bytes:
            await callback.message.answer_photo(
                photo=BufferedInputFile(image_bytes, filename=f"concept_{index}.jpg"),
                caption=f"<b>Концепт {index}/5 — {name}</b>",
                parse_mode="HTML",
            )
            generated_count += 1
        else:
            # Fallback: try sending by URL directly
            try:
                await callback.message.answer_photo(
                    photo=url,
                    caption=f"<b>Концепт {index}/5 — {name}</b>",
                    parse_mode="HTML",
                )
                generated_count += 1
            except Exception as exc:
                log_error(user.id, user.username, f"send_visual_{index}", str(exc))
                failed_count += 1
                await callback.message.answer(
                    f"⚠️ Концепт {index}/5 — <b>{name}</b>\n"
                    f"Не удалось отправить изображение.",
                    parse_mode="HTML",
                )

    try:
        await progress_msg.delete()
    except Exception:
        pass

    # Summary message
    if generated_count > 0:
        summary = (
            f"✅ <b>Готово!</b> Сгенерировано {generated_count} из {len(concepts)} изображений.\n\n"
            "Сохрани понравившиеся варианты — они готовы к использованию на маркетплейсе."
        )
        if failed_count > 0:
            summary += f"\n\n⚠️ {failed_count} изображений не удалось сгенерировать."
    else:
        summary = (
            "😔 Не удалось сгенерировать ни одного изображения.\n\n"
            "Попробуй позже или обратись к администратору бота."
        )

    log_event(user.id, user.username, "visual_concepts_done", {
        "generated": generated_count,
        "failed":    failed_count,
        "total":     len(concepts),
    })

    await callback.message.answer(
        summary,
        parse_mode="HTML",
        reply_markup=after_visuals_keyboard(),
    )
