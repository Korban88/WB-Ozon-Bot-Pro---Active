"""
Модуль 2: Генерация визуального пака.

5 изображений:  1 Hero Shot · 2 Lifestyle · 2 Ad Creative.
Без текста на изображениях. Товар не изменяется.

Если в state есть данные из предыдущего анализа — пропускает вопросы про название/описание,
сразу просит фото.
"""

import html
import io

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from core.image_generation import generate_visual_pack
from keyboards import after_visuals_keyboard, category_keyboard, CATEGORY_NAMES
from logger_setup import log_error, log_event
from models.product_data import ProductData
from states import Menu, Visuals

router = Router()


def _e(t: object) -> str:
    return html.escape(str(t))


# ── Вход в модуль ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "module:visuals")
async def cb_start_visuals(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    product = ProductData.from_state_dict(data.get("product"))

    if product.title:
        # Данные уже есть из анализа — просим только фото
        await state.set_state(Visuals.wait_photo)
        await callback.message.answer(
            f"📸 <b>Загрузи фото товара</b>\n\n"
            f"Товар: <b>{_e(product.title)}</b>\n\n"
            "Отправь фото — лучше всего студийное или на белом фоне.",
            parse_mode="HTML",
        )
        return

    # Данных нет — начинаем с категории
    await state.set_state(Visuals.wait_category)
    await callback.message.answer(
        "🖼 <b>Создать визуалы</b>\n\nВыбери категорию товара:",
        reply_markup=category_keyboard(),
        parse_mode="HTML",
    )


# ── Шаги сбора данных ─────────────────────────────────────────────────────────

@router.callback_query(Visuals.wait_category, F.data.startswith("category:"))
async def cb_category(callback: CallbackQuery, state: FSMContext) -> None:
    category = callback.data.split(":")[1]
    await state.update_data(category=category)
    await callback.answer()
    await state.set_state(Visuals.wait_title)
    await callback.message.answer(
        f"Категория: <b>{CATEGORY_NAMES.get(category, category)}</b> ✅\n\n"
        "Введи <b>название товара</b>:",
        parse_mode="HTML",
    )


@router.message(Visuals.wait_title, F.text)
async def msg_title(message: Message, state: FSMContext) -> None:
    title = message.text.strip()
    if len(title) < 3:
        await message.answer("Название слишком короткое. Введи полное название.")
        return
    await state.update_data(title=title)
    await state.set_state(Visuals.wait_benefits)
    await message.answer(
        f"Название: <b>{_e(title)}</b> ✅\n\n"
        "Опиши <b>товар и его преимущества</b> — из чего сделан, для кого, чем лучше:",
        parse_mode="HTML",
    )


@router.message(Visuals.wait_benefits, F.text)
async def msg_benefits(message: Message, state: FSMContext) -> None:
    await state.update_data(benefits=message.text.strip())
    await state.set_state(Visuals.wait_photo)
    await message.answer(
        "📸 <b>Загрузи фото товара</b>\n\n"
        "Отправь фото — лучше всего студийное или на белом фоне.",
        parse_mode="HTML",
    )


@router.message(Visuals.wait_photo, ~F.photo)
async def guard_photo(message: Message) -> None:
    await message.answer("Нужна фотография. Отправь фото товара.")


# ── Генерация ─────────────────────────────────────────────────────────────────

@router.message(Visuals.wait_photo, F.photo)
async def msg_photo(message: Message, state: FSMContext) -> None:
    user  = message.from_user
    photo = message.photo[-1]

    # Скачиваем фото
    file = await message.bot.get_file(photo.file_id)
    buf  = io.BytesIO()
    await message.bot.download_file(file.file_path, destination=buf)
    photo_bytes = buf.getvalue()

    # Собираем ProductData из state + входных данных
    data    = await state.get_data()
    product = ProductData.from_state_dict(data.get("product"))
    if data.get("title"):     product.title    = data["title"]
    if data.get("benefits"):  product.benefits = data["benefits"]
    if data.get("category"):  product.category = data["category"]
    if not product.category:  product.category = "other"
    product.photo_bytes = photo_bytes

    await state.set_state(Visuals.generating)
    progress = await message.answer(
        "⏳ <b>Генерирую 5 изображений...</b>\n\n"
        "1 Hero Shot · 2 Lifestyle · 2 Ad Creative\n"
        "Без текста — чистые коммерческие фото.\n\n"
        "Обычно 30–60 сек на каждое.",
        parse_mode="HTML",
    )

    generated = 0
    failed    = 0

    async for index, label, image_bytes in generate_visual_pack(product, user.id, user.username):
        if image_bytes:
            try:
                await message.answer_photo(
                    photo      = BufferedInputFile(image_bytes, filename=f"visual_{index}.png"),
                    caption    = f"<b>{index}/5 — {_e(label)}</b>",
                    parse_mode = "HTML",
                )
                generated += 1
            except Exception as exc:
                log_error(user.id, user.username, f"send_visual_{index}", str(exc))
                failed += 1
        else:
            failed += 1
            await message.answer(f"⚠️ {index}/5 — {_e(label)}: не удалось создать.")

    try:
        await progress.delete()
    except Exception:
        pass

    log_event(user.id, user.username, "visuals_done", {"generated": generated, "failed": failed})

    summary = f"✅ <b>{generated} из 5 визуалов готовы.</b>"
    if failed:
        summary += f"\n⚠️ {failed} не удалось создать."
    summary += "\n\nЧто дальше?"

    await state.set_state(Menu.main)
    await message.answer(summary, parse_mode="HTML", reply_markup=after_visuals_keyboard())
