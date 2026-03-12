"""
Главное меню. Точка входа /start и /menu.
"""

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards import main_menu_keyboard
from states import Menu

router = Router()

_WELCOME = (
    "🤖 <b>WB/Ozon AI Studio</b>\n\n"
    "Помогаю продавцам улучшать карточки товаров и увеличивать продажи.\n\n"
    "🔍 <b>Аудит карточки</b> — что мешает продажам и как это исправить\n"
    "🖼 <b>5 визуалов</b> — готовые изображения для карточки\n"
    "📊 <b>Инфографика</b> — структура карточки для дизайнера\n"
    "📣 <b>Тексты карточки</b> — название, описание, буллеты\n"
    "🎬 <b>Сценарий видео</b> — короткий ролик для соцсетей\n\n"
    "Выбери с чего начать:"
)


@router.message(CommandStart())
@router.message(Command("menu"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Menu.main)
    await message.answer(_WELCOME, reply_markup=main_menu_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "menu:main")
async def cb_menu_main(callback: CallbackQuery, state: FSMContext) -> None:
    """Кнопка «Главное меню» из любого модуля."""
    await callback.answer()
    await state.set_state(Menu.main)
    await callback.message.answer(_WELCOME, reply_markup=main_menu_keyboard(), parse_mode="HTML")
