"""
Модуль 1: Аудит карточки + конкурентный анализ.

Флоу:
  1. Пользователь даёт ссылку WB/Ozon
  2. Парсим карточку + параллельно ищем конкурентов
  3. Если парсинг провалился — предлагаем ручной ввод
  4. Запускаем анализ с данными конкурентов
  5. Выдаём структурированный аудит + кнопки переходов
"""

import asyncio
import html

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from core.analysis_engine import analyze_card
from keyboards import after_analysis_keyboard, analysis_fallback_keyboard, main_menu_keyboard
from logger_setup import log_error, log_event
from models.product_data import ProductData
from services.audit_engine import calculate_ctr_score, format_ctr_block
from services.marketplace_parser import get_wb_competitors, parse_url
from states import Analysis, Menu

router = Router()


def _e(t: object) -> str:
    return html.escape(str(t))


# ── Вход ──────────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "module:analysis")
async def cb_start_analysis(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(Analysis.wait_url)
    await callback.message.answer(
        "🔍 <b>Аудит карточки</b>\n\n"
        "Отправь ссылку на карточку с Wildberries или Ozon.\n\n"
        "Получишь:\n"
        "• Оценку карточки по ключевым метрикам\n"
        "• Главные причины низких продаж\n"
        "• Конкретные шаги для роста\n"
        "• Сравнение с конкурентами",
        parse_mode="HTML",
    )


# ── Получение URL ─────────────────────────────────────────────────────────────

@router.message(Analysis.wait_url, F.text)
async def msg_url(message: Message, state: FSMContext) -> None:
    user = message.from_user
    url  = message.text.strip()

    if not any(d in url for d in ["wildberries.ru", "wb.ru", "ozon.ru"]):
        await message.answer(
            "Это не похоже на ссылку WB или Ozon.\n"
            "Примеры:\n"
            "<code>https://www.wildberries.ru/catalog/123456789/detail.aspx</code>\n"
            "<code>https://www.ozon.ru/product/название-123456789/</code>",
            parse_mode="HTML",
        )
        return

    await state.set_state(Analysis.analyzing)
    progress = await message.answer("⏳ Читаю карточку...")

    product = await parse_url(url)

    if not product:
        await progress.edit_text("⚠️ Не удалось распознать ссылку. Проверь формат.")
        await message.answer("Попробуй снова или введи данные вручную.", reply_markup=main_menu_keyboard())
        await state.set_state(Menu.main)
        return

    if not product.title:
        await progress.delete()
        await state.update_data(manual_url=url, manual_marketplace=product.marketplace or "wb")
        await message.answer(
            "⚠️ <b>Маркетплейс не вернул данные карточки.</b>\n\n"
            "Возможные причины: карточка скрыта, временный сбой API, "
            "нестандартный формат ссылки.\n\n"
            "Введи данные вручную — аудит будет таким же:",
            parse_mode="HTML",
            reply_markup=analysis_fallback_keyboard(),
        )
        await state.set_state(Menu.main)
        return

    # Параллельно: ищем конкурентов пока обновляем прогресс
    await progress.edit_text("⏳ Ищу конкурентов...")
    competitors = []
    if product.marketplace == "wb" and product.title:
        try:
            competitors = await asyncio.wait_for(
                get_wb_competitors(product.title, n=5),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            pass

    await state.update_data(product=product.to_state_dict())
    await progress.edit_text("⏳ Провожу аудит...")
    await _run_analysis(message, state, product, user, progress, competitors)


# ── Ручной ввод ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "analysis:manual")
async def cb_manual_start(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.set_state(Analysis.wait_manual_title)
    await callback.message.answer(
        "✏️ <b>Ручной ввод</b>\n\nВведи <b>название товара</b> (как на маркетплейсе):",
        parse_mode="HTML",
    )


@router.message(Analysis.wait_manual_title, F.text)
async def msg_manual_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("Слишком короткое. Введи полное название товара.")
        return
    await state.update_data(manual_title=title)
    await state.set_state(Analysis.wait_manual_desc)
    await message.answer(
        f"Название: <b>{_e(title)}</b> ✅\n\n"
        "Опиши товар:\n"
        "— цена, рейтинг, количество отзывов\n"
        "— характеристики и преимущества\n"
        "— для кого и зачем\n\n"
        "<i>Чем больше данных — тем точнее аудит.</i>",
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
    await state.update_data(product=product.to_state_dict())

    progress = await message.answer("⏳ Ищу конкурентов...")
    competitors = []
    if product.title:
        try:
            competitors = await asyncio.wait_for(
                get_wb_competitors(product.title, n=5),
                timeout=10.0,
            )
        except asyncio.TimeoutError:
            pass

    await progress.edit_text("⏳ Провожу аудит...")
    await _run_analysis(message, state, product, user, progress, competitors)


# ── Общая логика анализа ──────────────────────────────────────────────────────

async def _run_analysis(
    message, state, product: ProductData, user,
    progress_msg=None, competitors: list | None = None,
) -> None:
    try:
        analysis_text = await analyze_card(
            product_brief = product.to_brief(),
            marketplace   = product.marketplace,
            user_id       = user.id,
            username      = user.username,
            competitors   = competitors or [],
        )
    except Exception as exc:
        log_error(user.id, user.username, "analyze_card", str(exc))
        if progress_msg:
            await progress_msg.delete()
        await message.answer("Ошибка анализа. Попробуй позже.", reply_markup=main_menu_keyboard())
        await state.set_state(Menu.main)
        return

    if progress_msg:
        await progress_msg.delete()

    # ── Заголовок карточки ─────────────────────────────────────────────────────
    header = f"📦 <b>{_e(product.title)}</b>"
    if product.brand:         header += f" · {_e(product.brand)}"
    if product.price:
        price_str = f"{product.price:,}".replace(",", " ")
        header += f"\n💰 {price_str}₽"
        if product.discount_pct:
            header += f" <i>(-{product.discount_pct}%)</i>"
    if product.rating:        header += f" · ⭐ {product.rating}"
    if product.reviews_count: header += f" ({product.reviews_count:,} отз.)".replace(",", " ")
    if product.images_count:  header += f" · 📸 {product.images_count} фото"
    if product.article_id:    header += f"\n🔗 Артикул: {product.article_id}"
    if competitors:           header += f"\n🔍 Найдено конкурентов: {len(competitors)}"

    # ── CTR Score (deterministic, no LLM) ─────────────────────────────────────
    ctr       = calculate_ctr_score(product)
    ctr_block = format_ctr_block(ctr)

    # Отправляем заголовок + CTR score ПЕРВЫМ сообщением (всегда быстро)
    await message.answer(header + "\n\n" + ctr_block, parse_mode="HTML")

    # ── LLM-анализ ─────────────────────────────────────────────────────────────
    # Разбиваем если длиннее лимита Telegram
    if len(analysis_text) <= 4096:
        await message.answer(analysis_text, parse_mode="HTML")
    else:
        await message.answer(analysis_text[:3800] + "\n\n<i>…продолжение →</i>", parse_mode="HTML")
        await message.answer(analysis_text[3800:4096 * 2], parse_mode="HTML")

    await message.answer(
        "Данные сохранены. Переходи в любой модуль:",
        reply_markup=after_analysis_keyboard(),
    )

    log_event(user.id, user.username, "analysis_done", {
        "title": product.title,
        "marketplace": product.marketplace,
        "competitors_found": len(competitors or []),
    })
    await state.set_state(Menu.main)
