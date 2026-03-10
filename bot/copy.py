"""
Модуль 4: Copy Pack.

Генерирует текст карточки для маркетплейса (листинг) + рекламный копипак.
Антигаллюцинационное правило: только данные из ТЗ, ничего выдуманного.
"""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.copy_generation import generate_ad_copy, generate_listing_copy
from keyboards import after_copy_keyboard, main_menu_keyboard
from logger_setup import log_error, log_event
from models.product_data import ProductData
from states import Copy, Menu

router = Router()


def _e(t: object) -> str:
    return html.escape(str(t))


# ── Вход ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "module:copy")
async def cb_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data    = await state.get_data()
    product = ProductData.from_state_dict(data.get("product"))

    if product.has_content():
        await _generate(callback.message, state, callback.from_user)
        return

    await state.set_state(Copy.wait_title)
    await callback.message.answer(
        "📣 <b>Copy Pack</b>\n\nВведи <b>название товара</b>:",
        parse_mode="HTML",
    )


@router.message(Copy.wait_title, F.text)
async def msg_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(Copy.wait_benefits)
    await message.answer(
        "Опиши <b>товар и его преимущества</b>.\n\n"
        "<i>Пиши только реальные характеристики — AI не будет их придумывать.</i>",
        parse_mode="HTML",
    )


@router.message(Copy.wait_benefits, F.text)
async def msg_benefits(message: Message, state: FSMContext) -> None:
    await state.update_data(benefits=message.text.strip())
    await _generate(message, state, message.from_user)


# ── Генерация ─────────────────────────────────────────────────────────────────

async def _generate(message, state, user) -> None:
    data    = await state.get_data()
    product = ProductData.from_state_dict(data.get("product"))
    if data.get("title"):    product.title    = data["title"]
    if data.get("benefits"): product.benefits = data["benefits"]
    if not product.marketplace: product.marketplace = "wb"

    progress = await message.answer("⏳ Генерирую Copy Pack...")
    await state.set_state(Copy.generating)

    try:
        listing = await generate_listing_copy(product, user.id, user.username)
        ad      = await generate_ad_copy(product, user.id, user.username)
    except Exception as exc:
        log_error(user.id, user.username, "copy_pack", str(exc))
        await progress.delete()
        await message.answer("Ошибка генерации. Попробуй снова.", reply_markup=main_menu_keyboard())
        await state.set_state(Menu.main)
        return

    await progress.delete()

    # ── Листинг ───────────────────────────────────────────────────────────────
    title_t  = listing.get("title", "")
    subtitle = listing.get("subtitle", "")
    desc     = listing.get("description", "")
    features = listing.get("features", [])
    specs    = listing.get("specs", [])
    hashtags = listing.get("hashtags", [])

    t = f"📝 <b>Текст карточки — {_e(product.title)}</b>\n\n"
    if title_t:  t += f"<b>Заголовок:</b>\n{_e(title_t)}\n\n"
    if subtitle: t += f"<b>Подзаголовок:</b>\n{_e(subtitle)}\n\n"
    if desc:     t += f"<b>Описание:</b>\n{_e(desc)}\n\n"
    if features: t += "<b>Преимущества:</b>\n" + "\n".join(_e(f) for f in features) + "\n\n"
    if specs:    t += "<b>Характеристики:</b>\n" + "\n".join(_e(s) for s in specs) + "\n\n"
    if hashtags: t += " ".join(_e(h) for h in hashtags)

    await message.answer(t, parse_mode="HTML")

    # ── Рекламный копипак ─────────────────────────────────────────────────────
    hooks       = ad.get("hooks",       [])
    copy_short  = ad.get("copy_short",  [])
    copy_medium = ad.get("copy_medium", [])

    a = "📣 <b>Рекламный копипак</b>\n\n"
    if hooks:
        a += "⚡️ <b>Хуки</b>\n"
        for i, h in enumerate(hooks, 1):
            a += f"{i}. {_e(h)}\n"
        a += "\n"
    if copy_short:
        a += "✍️ <b>Короткие тексты</b> <i>(для объявлений)</i>\n"
        for i, c in enumerate(copy_short, 1):
            a += f"{i}. {_e(c)}\n"
        a += "\n"
    if copy_medium:
        a += "📝 <b>Тексты для постов</b>\n"
        for i, c in enumerate(copy_medium, 1):
            a += f"\n<b>Вариант {i}:</b>\n{_e(c)}\n"

    await message.answer(a, parse_mode="HTML")

    log_event(user.id, user.username, "copy_done", {"title": product.title})
    await state.set_state(Menu.main)
    await message.answer("Copy Pack готов. Что дальше?", reply_markup=after_copy_keyboard())
