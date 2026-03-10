"""
Модуль 3: Бриф инфографики.

Генерирует структуру для 5 инфографических слайдов карточки.
Выдаёт не изображения, а описание: заголовок + подзаголовок + иконка.
Это даёт дизайнеру или генератору изображений правильное ТЗ.
"""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.copy_generation import generate_infographic_brief
from keyboards import after_copy_keyboard, main_menu_keyboard
from logger_setup import log_error, log_event
from models.product_data import ProductData
from states import Infographic, Menu

router = Router()


def _e(t: object) -> str:
    return html.escape(str(t))


# ── Вход ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "module:infographic")
async def cb_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data    = await state.get_data()
    product = ProductData.from_state_dict(data.get("product"))

    if product.has_content():
        await _generate(callback.message, state, callback.from_user)
        return

    await state.set_state(Infographic.wait_title)
    await callback.message.answer(
        "📊 <b>Инфографика</b>\n\nВведи <b>название товара</b>:",
        parse_mode="HTML",
    )


@router.message(Infographic.wait_title, F.text)
async def msg_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(Infographic.wait_benefits)
    await message.answer("Опиши товар и его преимущества:")


@router.message(Infographic.wait_benefits, F.text)
async def msg_benefits(message: Message, state: FSMContext) -> None:
    await state.update_data(benefits=message.text.strip())
    await _generate(message, state, message.from_user)


# ── Генерация ─────────────────────────────────────────────────────────────────

async def _generate(message, state, user) -> None:
    data    = await state.get_data()
    product = ProductData.from_state_dict(data.get("product"))
    if data.get("title"):    product.title    = data["title"]
    if data.get("benefits"): product.benefits = data["benefits"]

    progress = await message.answer("⏳ Генерирую инфографику...")
    await state.set_state(Infographic.generating)

    try:
        result = await generate_infographic_brief(product, user.id, user.username)
    except Exception as exc:
        log_error(user.id, user.username, "infographic", str(exc))
        await progress.delete()
        await message.answer("Ошибка. Попробуй снова.", reply_markup=main_menu_keyboard())
        await state.set_state(Menu.main)
        return

    await progress.delete()

    slides = result.get("slides", [])
    if not slides:
        await message.answer("Не удалось сгенерировать. Попробуй снова.", reply_markup=main_menu_keyboard())
        await state.set_state(Menu.main)
        return

    text = f"📊 <b>Инфографика — {_e(product.title)}</b>\n\n"
    for s in slides:
        text += (
            f"<b>Слайд {s.get('number', '')}</b>\n"
            f"Заголовок: <b>{_e(s.get('headline', ''))}</b>\n"
        )
        if s.get("subheadline"): text += f"Подзаголовок: {_e(s['subheadline'])}\n"
        if s.get("icon"):        text += f"Иконка: <code>{_e(s['icon'])}</code>\n"
        if s.get("color_mood"):  text += f"Цвет: {_e(s['color_mood'])}\n"
        text += "\n"

    log_event(user.id, user.username, "infographic_done", {"slides": len(slides)})
    await state.set_state(Menu.main)
    await message.answer(text, parse_mode="HTML", reply_markup=after_copy_keyboard())
