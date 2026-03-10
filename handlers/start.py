"""
/start command handler.

Resets any active dialog state and shows the welcome screen.
"""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards import marketplace_keyboard
from logger_setup import log_event
from states import Dialog
from utils.images import send_step_image

router = Router()

WELCOME_TEXT = (
    "👋 <b>Привет! Я помогу создать профессиональный контент для товара на маркетплейсе.</b>\n\n"
    "Загрузи фото — получишь три пакета:\n\n"
    "📝 <b>Текст карточки</b> — SEO-заголовок, описание, характеристики, хэштеги\n"
    "🖼 <b>5 Premium Visuals</b> — чистые сцены с товаром, без текста, готовые к загрузке\n"
    "📣 <b>Ad Copy Pack</b> — хуки, тексты для рекламы и UGC-бриф\n\n"
    "Начнём? Выбери маркетплейс 👇"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    user = message.from_user

    # Clear any previous dialog state
    await state.clear()

    log_event(
        user.id,
        user.username,
        event="bot_started",
        data={"first_name": user.first_name},
    )

    await send_step_image(
        message,
        step="welcome",
        caption=WELCOME_TEXT,
        reply_markup=marketplace_keyboard(),
    )

    await state.set_state(Dialog.choose_marketplace)
