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
    "👋 <b>Привет! Я помогу создать продающую карточку товара для маркетплейса.</b>\n\n"
    "Всего несколько шагов — и ты получишь:\n"
    "📝 Готовый текст карточки с SEO-заголовком\n"
    "🎨 5 дизайн-концептов на выбор\n"
    "🖼 Готовые визуальные варианты карточки\n\n"
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
