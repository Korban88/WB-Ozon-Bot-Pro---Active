"""
Helper for sending step images alongside bot messages.

Usage:
    await send_step_image(message, "welcome", caption="Текст сообщения")
    await send_step_image(message, "choose_marketplace", caption="...", reply_markup=kb)

If the image file is missing, the bot sends a plain text message instead —
so a missing file never breaks the dialog.
"""

import os
from aiogram import Bot
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup

import config
from logger_setup import log


async def send_step_image(
    message: Message,
    step: str,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "HTML",
) -> Message:
    """
    Send the image for `step` with `caption` as the photo caption.
    Falls back to a plain text message if the image file is not found.

    Returns the sent Message object.
    """
    image_path = os.path.join(config.IMAGES_DIR, f"{step}.png")

    if os.path.exists(image_path):
        return await message.answer_photo(
            photo=FSInputFile(image_path),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    else:
        log.warning("Image not found for step '%s': %s", step, image_path)
        return await message.answer(
            text=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )


async def send_step_image_to_chat(
    bot: Bot,
    chat_id: int,
    step: str,
    caption: str,
    reply_markup: InlineKeyboardMarkup | None = None,
    parse_mode: str = "HTML",
) -> Message:
    """
    Same as send_step_image but accepts chat_id directly.
    Useful when we don't have a Message object at hand.
    """
    image_path = os.path.join(config.IMAGES_DIR, f"{step}.png")

    if os.path.exists(image_path):
        return await bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(image_path),
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    else:
        log.warning("Image not found for step '%s': %s", step, image_path)
        return await bot.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
