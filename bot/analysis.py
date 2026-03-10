"""
Модуль 1: Анализ карточки товара.

Пользователь присылает ссылку WB или Ozon.
Бот парсит карточку и возвращает структурированный анализ с рекомендациями.
После анализа — кнопки быстрого перехода в другие модули с уже загруженными данными.
"""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.analysis_engine import analyze_card
from keyboards import after_analysis_keyboard, main_menu_keyboard
from logger_setup import log_error, log_event
from models.product_data import ProductData
from services.marketplace_parser import parse_url
from states import Analysis, Menu

router = Router()


def _e(t: object) -> str:
    return html.escape(str(t))


# ── Вход в модуль ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "module:analysis")
async def cb_start_analysis(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(Analysis.wait_url)
    await callback.message.answer(
        "🔍 <b>Анализ карточки</b>\n\n"
        "Отправь ссылку на карточку товара:\n\n"
        "<b>Wildberries:</b>\n"
        "<code>https://www.wildberries.ru/catalog/123456789/detail.aspx</code>\n\n"
        "<b>Ozon:</b>\n"
        "<code>https://www.ozon.ru/product/название-123456789/</code>",
        parse_mode="HTML",
    )


# ── Получение URL ─────────────────────────────────────────────────────────────

@router.message(Analysis.wait_url, F.text)
async def msg_url(message: Message, state: FSMContext) -> None:
    user = message.from_user
    url  = message.text.strip()

    if "wildberries.ru" not in url and "wb.ru" not in url and "ozon.ru" not in url:
        await message.answer(
            "Это не похоже на ссылку WB или Ozon.\n"
            "Отправь ссылку вида:\n"
            "<code>https://www.wildberries.ru/catalog/123456789/detail.aspx</code>",
            parse_mode="HTML",
        )
        return

    await state.set_state(Analysis.analyzing)
    progress = await message.answer("⏳ Читаю карточку...")

    product = await parse_url(url)

    if not product:
        await progress.delete()
        await message.answer(
            "Не удалось распознать ссылку. Проверь формат и попробуй снова.",
            reply_markup=main_menu_keyboard(),
        )
        await state.set_state(Menu.main)
        return

    if not product.title:
        await progress.delete()
        await message.answer(
            "Не удалось получить данные карточки — маркетплейс не вернул информацию.\n\n"
            "Попробуй другой артикул или используй модуль <b>📣 Copy Pack</b> "
            "с ручным вводом данных.",
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )
        await state.set_state(Menu.main)
        return

    # Сохраняем данные для других модулей
    await state.update_data(product=product.to_state_dict())

    try:
        analysis_text = await analyze_card(
            product_brief = product.to_brief(),
            marketplace   = product.marketplace,
            user_id       = user.id,
            username      = user.username,
        )
    except Exception as exc:
        log_error(user.id, user.username, "analyze_card", str(exc))
        await progress.delete()
        await message.answer("Ошибка анализа. Попробуй позже.", reply_markup=main_menu_keyboard())
        await state.set_state(Menu.main)
        return

    await progress.delete()

    # Заголовок с данными карточки
    header = f"📦 <b>{_e(product.title)}</b>"
    if product.brand:         header += f" · {_e(product.brand)}"
    if product.price:         header += f"\n💰 {product.price:,}₽".replace(",", " ")
    if product.rating:        header += f" · ⭐ {product.rating} ({product.reviews_count} отз.)"
    if product.article_id:    header += f"\n🔗 Артикул: {product.article_id}"
    header += "\n\n"

    await message.answer(
        header + analysis_text,
        reply_markup=after_analysis_keyboard(),
    )

    log_event(user.id, user.username, "analysis_done", {
        "url": url, "title": product.title, "marketplace": product.marketplace,
    })
    await state.set_state(Menu.main)
