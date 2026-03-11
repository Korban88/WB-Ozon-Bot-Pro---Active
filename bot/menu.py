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
    "AI Creative Studio для продавцов на маркетплейсах.\n\n"
    "🔍 <b>Аудит карточки</b> — оценка CTR-факторов и action plan\n"
    "🖼 <b>Visual Pack</b> — 5 визуалов (Hero + Lifestyle + Ad Creative)\n"
    "📊 <b>Инфографика</b> — полный blueprint для дизайнера\n"
    "📣 <b>Copy Pack</b> — тексты карточки + рекламный пак\n"
    "🎬 <b>UGC сценарий</b> — скрипт для короткого видео\n\n"
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
