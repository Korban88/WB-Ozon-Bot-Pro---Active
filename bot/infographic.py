"""
Модуль 3: Инфографика — полный blueprint для дизайнера.

Выдаёт не просто заголовок+иконку, а полную спецификацию карточки:
  - Роль каждого слайда в воронке продаж
  - Приоритет и визуальная иерархия
  - SEO-ключевое слово для слайда
  - Объяснение: почему этот слайд влияет на покупку
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

_ROLE_LABELS = {
    "hook":         "🎣 Хук (цепляет внимание)",
    "benefit":      "✅ Преимущество",
    "spec":         "📐 Характеристика",
    "social_proof": "⭐ Соц. доказательство",
    "cta":          "🛒 Призыв к действию",
}

_HIERARCHY_LABELS = {
    "headline_dominant": "Крупный заголовок в фокусе",
    "icon_dominant":     "Иконка в фокусе + текст рядом",
    "split":             "Иконка и текст 50/50",
}


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
        "📊 <b>Инфографика — Blueprint</b>\n\n"
        "Получишь полный бриф для дизайнера: роль каждого слайда, "
        "заголовки, иконки, визуальный стиль и SEO-ключи.\n\n"
        "Введи <b>название товара</b>:",
        parse_mode="HTML",
    )


@router.message(Infographic.wait_title, F.text)
async def msg_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(Infographic.wait_benefits)
    await message.answer(
        "Опиши товар: характеристики, преимущества, для кого.\n"
        "<i>Только реальные данные — AI не будет выдумывать.</i>",
        parse_mode="HTML",
    )


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

    progress = await message.answer("⏳ Создаю blueprint инфографики...")
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
        num        = s.get("number", "")
        role       = s.get("role", "")
        role_label = _ROLE_LABELS.get(role, role)
        headline   = s.get("headline", "")
        subhead    = s.get("subheadline", "")
        icon       = s.get("icon", "")
        hierarchy  = s.get("visual_hierarchy", "")
        color_mood = s.get("color_mood", "")
        seo_kw     = s.get("seo_keyword", "")
        sells      = s.get("sells_because", "")

        text += f"━━━ <b>Слайд {num} — {role_label}</b> ━━━\n"
        if headline:   text += f"📝 <b>{_e(headline)}</b>\n"
        if subhead:    text += f"   {_e(subhead)}\n"
        if icon:       text += f"🔷 Иконка: <code>{_e(icon)}</code>\n"
        if hierarchy:
            h_label = _HIERARCHY_LABELS.get(hierarchy, hierarchy)
            text += f"👁 Компоновка: {_e(h_label)}\n"
        if color_mood: text += f"🎨 Стиль: {_e(color_mood)}\n"
        if seo_kw:     text += f"🔑 SEO-ключ: <i>{_e(seo_kw)}</i>\n"
        if sells:      text += f"💡 Продаёт потому что: {_e(sells)}\n"
        text += "\n"

    text += (
        "─────────────────────────\n"
        "<i>Передай этот бриф дизайнеру — "
        "он сразу поймёт что и как делать.</i>"
    )

    log_event(user.id, user.username, "infographic_done", {"slides": len(slides)})
    await state.set_state(Menu.main)
    await message.answer(text, parse_mode="HTML", reply_markup=after_copy_keyboard())
