"""
Модуль 1: Аудит карточки товара (Card Audit).

Основной флоу:
  1. Пользователь присылает ссылку WB/Ozon
  2. Бот парсит карточку
  3. Если парсинг успешен → анализируем
  4. Если парсинг вернул пустую карточку → предлагаем ручной ввод
  5. Выдаём структурированный аудит с action plan

После анализа — кнопки быстрого перехода в другие модули с уже загруженными данными.
"""

import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.analysis_engine import analyze_card
from keyboards import after_analysis_keyboard, analysis_fallback_keyboard, main_menu_keyboard
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
        "🔍 <b>Аудит карточки товара</b>\n\n"
        "Отправь ссылку на карточку товара:\n\n"
        "<b>Wildberries:</b>\n"
        "<code>https://www.wildberries.ru/catalog/123456789/detail.aspx</code>\n\n"
        "<b>Ozon:</b>\n"
        "<code>https://www.ozon.ru/product/название-123456789/</code>\n\n"
        "<i>Получишь: оценку CTR-факторов, список проблем и приоритетный action plan.</i>",
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

    await progress.delete()

    if not product:
        await message.answer(
            "Не удалось распознать ссылку. Проверь формат и попробуй снова.",
            reply_markup=main_menu_keyboard(),
        )
        await state.set_state(Menu.main)
        return

    # Парсинг успешен, но данных мало → предлагаем ручной ввод
    if not product.title:
        await state.update_data(manual_url=url, manual_marketplace=product.marketplace or "wb")
        await message.answer(
            "⚠️ <b>Маркетплейс не вернул данные карточки.</b>\n\n"
            "Это бывает при закрытых карточках или временных ошибках API.\n\n"
            "Можешь ввести данные вручную — аудит будет таким же точным.",
            parse_mode="HTML",
            reply_markup=analysis_fallback_keyboard(),
        )
        await state.set_state(Menu.main)
        return

    # Сохраняем данные для переиспользования в других модулях
    await state.update_data(product=product.to_state_dict())

    await _run_analysis(message, state, product, user)


# ── Ручной ввод (когда парсер не смог) ────────────────────────────────────────

@router.callback_query(F.data == "analysis:manual")
async def cb_manual_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(Analysis.wait_manual_title)
    await callback.message.answer(
        "✏️ <b>Ручной ввод данных</b>\n\n"
        "Введи <b>название товара</b> (как на маркетплейсе):",
        parse_mode="HTML",
    )


@router.message(Analysis.wait_manual_title, F.text)
async def msg_manual_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("Слишком короткое название. Введи полное название товара.")
        return
    await state.update_data(manual_title=title)
    await state.set_state(Analysis.wait_manual_desc)
    await message.answer(
        f"Название: <b>{_e(title)}</b> ✅\n\n"
        "Теперь опиши товар:\n"
        "— характеристики (размер, материал, цвет и т.п.)\n"
        "— преимущества\n"
        "— для кого и зачем\n\n"
        "<i>Чем больше реальных данных — тем точнее аудит.</i>",
        parse_mode="HTML",
    )


@router.message(Analysis.wait_manual_desc, F.text)
async def msg_manual_desc(message: Message, state: FSMContext) -> None:
    user = message.from_user
    data = await state.get_data()

    product = ProductData(
        title       = data.get("manual_title", ""),
        description = message.text.strip(),
        marketplace = data.get("manual_marketplace", "wb"),
        url         = data.get("manual_url", ""),
    )

    # Сохраняем для переиспользования
    await state.update_data(product=product.to_state_dict())

    progress = await message.answer("⏳ Провожу аудит...")
    await _run_analysis(message, state, product, user, progress_msg=progress)


# ── Общая логика анализа ──────────────────────────────────────────────────────

async def _run_analysis(message, state, product: ProductData, user, progress_msg=None) -> None:
    if not progress_msg:
        progress_msg = await message.answer("⏳ Провожу аудит карточки...")

    try:
        analysis_text = await analyze_card(
            product_brief = product.to_brief(),
            marketplace   = product.marketplace,
            user_id       = user.id,
            username      = user.username,
        )
    except Exception as exc:
        log_error(user.id, user.username, "analyze_card", str(exc))
        await progress_msg.delete()
        await message.answer("Ошибка анализа. Попробуй позже.", reply_markup=main_menu_keyboard())
        await state.set_state(Menu.main)
        return

    await progress_msg.delete()

    # Заголовок с данными карточки
    header = f"📦 <b>{_e(product.title)}</b>"
    if product.brand:         header += f" · {_e(product.brand)}"
    if product.price:         header += f"\n💰 {product.price:,}₽".replace(",", " ")
    if product.rating:        header += f" · ⭐ {product.rating}"
    if product.reviews_count: header += f" ({product.reviews_count:,} отз.)".replace(",", " ")
    if product.article_id:    header += f"\n🔗 Артикул: {product.article_id}"
    header += "\n\n"

    full_text = header + analysis_text

    # Telegram лимит 4096 символов — разбиваем если нужно
    if len(full_text) <= 4096:
        await message.answer(full_text, parse_mode="HTML")
    else:
        await message.answer(header + analysis_text[:3800] + "\n\n<i>…продолжение ниже</i>", parse_mode="HTML")
        await message.answer(analysis_text[3800:], parse_mode="HTML")

    await message.answer(
        "Что делаем дальше? Все данные уже загружены — выбери модуль:",
        reply_markup=after_analysis_keyboard(),
    )

    log_event(user.id, user.username, "analysis_done", {
        "title": product.title,
        "marketplace": product.marketplace,
        "has_url": bool(product.url),
    })
    await state.set_state(Menu.main)
