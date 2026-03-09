"""
Main dialog flow handler.

Covers steps 1-6:
  1. choose_marketplace  — inline button press
  2. choose_category     — inline button press
  3. enter_title         — text message
  4. enter_benefits      — text message
  5. upload_photo        — photo message → triggers AI generation
  6. show_card           — card ready, offer design buttons

Also handles:
  - "restart" action (callback)
  - "edit_benefits" action (callback)
  - Unexpected messages during wrong states (gentle nudge)
"""

import io

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from keyboards import (
    CATEGORY_NAMES,
    after_card_keyboard,
    category_keyboard,
    marketplace_keyboard,
)
from logger_setup import log_error, log_event, log_step
from services.openrouter import generate_card
from states import Dialog
from utils.images import send_step_image

router = Router()

MARKETPLACE_NAMES = {"wb": "🟣 Wildberries", "ozon": "🔵 Ozon"}


# ── Step 1: Choose marketplace ─────────────────────────────────────────────────
@router.callback_query(Dialog.choose_marketplace, F.data.startswith("marketplace:"))
async def cb_choose_marketplace(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    marketplace = callback.data.split(":")[1]  # "wb" or "ozon"

    await state.update_data(marketplace=marketplace)
    await callback.answer()

    log_step(user.id, user.username, "choose_marketplace", {"marketplace": marketplace})

    await send_step_image(
        callback.message,
        step="choose_category",
        caption=(
            f"Отлично! Выбран маркетплейс <b>{MARKETPLACE_NAMES[marketplace]}</b>\n\n"
            "Выбери <b>категорию товара</b> 👇"
        ),
        reply_markup=category_keyboard(),
    )
    await state.set_state(Dialog.choose_category)


# ── Step 2: Choose category ────────────────────────────────────────────────────
@router.callback_query(Dialog.choose_category, F.data.startswith("category:"))
async def cb_choose_category(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    category = callback.data.split(":")[1]

    await state.update_data(category=category)
    await callback.answer()

    log_step(user.id, user.username, "choose_category", {"category": category})

    await send_step_image(
        callback.message,
        step="enter_title",
        caption=(
            f"Категория: <b>{CATEGORY_NAMES.get(category, category)}</b> ✅\n\n"
            "Введи <b>название товара</b>.\n\n"
            "<i>Например: Беспроводные наушники с шумоподавлением</i>"
        ),
    )
    await state.set_state(Dialog.enter_title)


# ── Step 3: Enter title ────────────────────────────────────────────────────────
@router.message(Dialog.enter_title, F.text)
async def msg_enter_title(message: Message, state: FSMContext) -> None:
    user = message.from_user
    title = message.text.strip()

    if len(title) < 3:
        await message.answer("Название слишком короткое. Введи полное название товара.")
        return

    await state.update_data(title=title)
    log_step(user.id, user.username, "enter_title", {"title": title})

    await send_step_image(
        message,
        step="enter_benefits",
        caption=(
            f"Название: <b>{title}</b> ✅\n\n"
            "Теперь <b>опиши товар и его преимущества</b>.\n\n"
            "Напиши:\n"
            "• Чем товар лучше аналогов\n"
            "• Какие проблемы он решает\n"
            "• Особенности материала, состава или конструкции\n"
            "• Любые важные характеристики\n\n"
            "<i>Чем подробнее — тем лучше получится карточка</i>"
        ),
    )
    await state.set_state(Dialog.enter_benefits)


# ── Step 4: Enter benefits ─────────────────────────────────────────────────────
@router.message(Dialog.enter_benefits, F.text)
async def msg_enter_benefits(message: Message, state: FSMContext) -> None:
    user = message.from_user
    benefits = message.text.strip()

    if len(benefits) < 10:
        await message.answer(
            "Напиши подробнее — хотя бы несколько слов о преимуществах товара."
        )
        return

    await state.update_data(benefits=benefits)
    log_step(user.id, user.username, "enter_benefits", {"benefits_length": len(benefits)})

    await send_step_image(
        message,
        step="upload_photo",
        caption=(
            "Описание получено ✅\n\n"
            "📷 Теперь <b>отправь фотографию товара</b>.\n\n"
            "Отправь фото прямо в этот чат — я использую его для анализа "
            "и генерации карточки."
        ),
    )
    await state.set_state(Dialog.upload_photo)


# ── Step 5: Upload photo → generate card ──────────────────────────────────────
@router.message(Dialog.upload_photo, F.photo)
async def msg_upload_photo(message: Message, state: FSMContext) -> None:
    user = message.from_user

    # Telegram sends photos in multiple resolutions — take the largest
    photo = message.photo[-1]
    log_step(user.id, user.username, "upload_photo", {
        "file_id": photo.file_id,
        "file_size": photo.file_size,
        "width": photo.width,
        "height": photo.height,
    })

    # Show "generating" screen while AI works
    generating_msg = await send_step_image(
        message,
        step="generating",
        caption=(
            "⏳ <b>Генерирую карточку товара...</b>\n\n"
            "Анализирую фото и описание, подбираю ключевые слова.\n"
            "Обычно занимает 15-30 секунд."
        ),
    )

    await state.set_state(Dialog.generating)

    # Download photo bytes
    try:
        file = await message.bot.get_file(photo.file_id)
        buf = io.BytesIO()
        await message.bot.download_file(file.file_path, destination=buf)
        photo_bytes = buf.getvalue()
    except Exception as exc:
        log_error(user.id, user.username, "upload_photo", f"Photo download failed: {exc}")
        await generating_msg.delete()
        await _send_error(message, state)
        return

    # Load dialog data
    data = await state.get_data()

    # Call OpenRouter
    try:
        card = await generate_card(
            user_id    = user.id,
            username   = user.username,
            title      = data["title"],
            category   = data["category"],
            marketplace= data["marketplace"],
            benefits   = data["benefits"],
            photo_bytes= photo_bytes,
        )
    except Exception as exc:
        log_error(user.id, user.username, "generate_card", str(exc))
        await generating_msg.delete()
        await _send_error(message, state)
        return

    # Save card to state
    await state.update_data(card=card)
    await state.set_state(Dialog.show_card)

    # Delete "generating" message, show result
    try:
        await generating_msg.delete()
    except Exception:
        pass

    await _send_card(message, card)

    log_event(user.id, user.username, "card_generated", {
        "title": card.get("title", ""),
        "marketplace": data["marketplace"],
    })


# ── Send formatted card ────────────────────────────────────────────────────────
async def _send_card(message: Message, card: dict) -> None:
    """Format and send the product card. Splits into parts if too long."""

    title       = card.get("title",       "Название не сгенерировано")
    subtitle    = card.get("subtitle",    "")
    description = card.get("description", "")
    features    = card.get("features",    [])
    specs       = card.get("specs",       [])
    hashtags    = card.get("hashtags",    [])

    # Build features block
    features_text = "\n".join(f"  {f}" for f in features) if features else ""
    specs_text    = "\n".join(f"  • {s}" for s in specs)  if specs    else ""
    hashtags_text = " ".join(hashtags)                    if hashtags  else ""

    card_text = (
        f"<b>{title}</b>\n"
        f"{subtitle}\n\n"
        f"{description}"
    )

    if features_text:
        card_text += f"\n\n<b>Преимущества:</b>\n{features_text}"

    if specs_text:
        card_text += f"\n\n<b>Характеристики:</b>\n{specs_text}"

    if hashtags_text:
        card_text += f"\n\n{hashtags_text}"

    # Photo captions are limited to 1024 chars in Telegram.
    # Strategy: always send card_ready image with a short caption,
    # then send the full card text as a plain text message (limit 4096 chars).
    TEXT_LIMIT = 4096

    # 1. Send "card ready" image with short caption
    await send_step_image(
        message,
        step="card_ready",
        caption="✅ <b>Карточка товара готова!</b>",
    )

    # 2. Send full card as text message(s)
    for chunk in _split_text(card_text, TEXT_LIMIT):
        await message.answer(chunk, parse_mode="HTML")

    # 3. Action buttons in a separate message
    await message.answer("Что делаем дальше?", reply_markup=after_card_keyboard())


def _split_text(text: str, limit: int) -> list[str]:
    """Split text into chunks of max `limit` chars, splitting at newlines."""
    parts = []
    while len(text) > limit:
        split_at = text.rfind("\n", 0, limit)
        if split_at == -1:
            split_at = limit
        parts.append(text[:split_at])
        text = text[split_at:].lstrip("\n")
    if text:
        parts.append(text)
    return parts


# ── Restart action ─────────────────────────────────────────────────────────────
@router.callback_query(F.data == "action:restart")
async def cb_restart(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    await callback.answer()
    await state.clear()

    log_event(user.id, user.username, "restart")

    await send_step_image(
        callback.message,
        step="choose_marketplace",
        caption=(
            "🔄 <b>Начинаем сначала!</b>\n\n"
            "Выбери маркетплейс 👇"
        ),
        reply_markup=marketplace_keyboard(),
    )
    await state.set_state(Dialog.choose_marketplace)


# ── Edit benefits action ───────────────────────────────────────────────────────
@router.callback_query(F.data == "action:edit_benefits")
async def cb_edit_benefits(callback: CallbackQuery, state: FSMContext) -> None:
    user = callback.from_user
    await callback.answer()

    log_event(user.id, user.username, "edit_benefits")

    await send_step_image(
        callback.message,
        step="enter_benefits",
        caption=(
            "✏️ <b>Изменяем описание.</b>\n\n"
            "Напиши новое описание товара и его преимущества.\n"
            "Я пересгенерирую карточку с учётом изменений."
        ),
    )
    await state.set_state(Dialog.enter_benefits)


# ── Guard: unexpected messages during wrong states ─────────────────────────────
@router.message(Dialog.upload_photo, ~F.photo)
async def guard_upload_photo(message: Message) -> None:
    await message.answer(
        "📷 Мне нужна <b>фотография товара</b>.\n"
        "Отправь фото прямо в этот чат.",
        parse_mode="HTML",
    )


@router.message(Dialog.choose_marketplace)
@router.message(Dialog.choose_category)
async def guard_need_button(message: Message) -> None:
    await message.answer("Пожалуйста, выбери вариант с помощью кнопок выше 👆")


# ── Error screen ───────────────────────────────────────────────────────────────
async def _send_error(message: Message, state: FSMContext) -> None:
    """Send error screen and return user to choose_marketplace."""
    await send_step_image(
        message,
        step="error",
        caption=(
            "😔 <b>Что-то пошло не так.</b>\n\n"
            "Не удалось сгенерировать карточку. Попробуй ещё раз — "
            "для этого просто нажми /start.\n\n"
            "Если ошибка повторяется, проверь своё подключение к интернету."
        ),
        reply_markup=marketplace_keyboard(),
    )
    await state.clear()
