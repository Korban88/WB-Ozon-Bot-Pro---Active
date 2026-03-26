"""
Модуль 5: UGC сценарий.

Генерирует сценарий короткого видеоролика (15-60 сек) по сценам.
Продавец может снять ролик сам или передать сценарий создателю UGC.
"""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.copy_generation import generate_ugc_scenario
from keyboards import after_copy_keyboard, main_menu_keyboard
from logger_setup import log_error, log_event
from models.product_data import ProductData
from states import Menu, UGC

router = Router()


def _e(t: object) -> str:
    return html.escape(str(t))


# ── Вход ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "module:ugc")
async def cb_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data    = await state.get_data()
    product = ProductData.from_state_dict(data.get("product"))

    if product.has_content():
        await _generate(callback.message, state, callback.from_user)
        return

    await state.set_state(UGC.wait_title)
    await callback.message.answer(
        "🎬 <b>UGC Сценарий</b>\n\nВведи <b>название товара</b>:",
        parse_mode="HTML",
    )


@router.message(UGC.wait_title, F.text)
async def msg_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(UGC.wait_benefits)
    await message.answer("Опиши товар — что это, для кого, какие преимущества:")


@router.message(UGC.wait_benefits, F.text)
async def msg_benefits(message: Message, state: FSMContext) -> None:
    await state.update_data(benefits=message.text.strip())
    await _generate(message, state, message.from_user)


# ── Генерация ─────────────────────────────────────────────────────────────────

async def _generate(message, state, user) -> None:
    data    = await state.get_data()
    product = ProductData.from_state_dict(data.get("product"))
    if data.get("title"):    product.title    = data["title"]
    if data.get("benefits"): product.benefits = data["benefits"]

    progress = await message.answer("⏳ Пишу сценарий...")
    await state.set_state(UGC.generating)

    try:
        result = await generate_ugc_scenario(product, user.id, user.username)
    except Exception as exc:
        log_error(user.id, user.username, "ugc", str(exc))
        await progress.delete()
        await message.answer("Ошибка. Попробуй снова.", reply_markup=main_menu_keyboard())
        await state.set_state(Menu.main)
        return

    await progress.delete()

    duration    = result.get("duration",    "15-30 сек")
    fmt         = result.get("format",      "9:16")
    hook        = result.get("hook",        result.get("hook_text", ""))
    micro_story = result.get("micro_story", "")
    benefit     = result.get("benefit",     "")
    scenes      = result.get("scenes",      [])
    cta         = result.get("cta",         "")

    text  = f"🎬 <b>UGC Сценарий — {_e(product.title)}</b>\n"
    text += f"⏱ {_e(duration)} · {_e(fmt)}\n\n"

    if hook:
        text += f"🎯 <b>Хук:</b> {_e(hook)}\n\n"
    if micro_story:
        text += f"💬 <b>Микро-история:</b> {_e(micro_story)}\n\n"
    if benefit:
        text += f"✨ <b>Польза:</b> {_e(benefit)}\n\n"

    if scenes:
        text += "<b>Раскадровка:</b>"
        for s in scenes:
            text += (
                f"\n\n<b>Сцена {s.get('number','')} <i>({_e(s.get('time',''))})</i></b>\n"
                f"📹 {_e(s.get('action',''))}\n"
            )
            if s.get("voiceover"):
                text += f"🗣 {_e(s['voiceover'])}\n"

    if cta:
        text += f"\n\n🔔 <b>CTA:</b> {_e(cta)}"

    log_event(user.id, user.username, "ugc_done", {"title": product.title})
    await state.set_state(Menu.main)
    await message.answer(text, parse_mode="HTML", reply_markup=after_copy_keyboard())
