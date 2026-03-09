from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def marketplace_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🟣 Wildberries", callback_data="marketplace:wb"),
            InlineKeyboardButton(text="🔵 Ozon",        callback_data="marketplace:ozon"),
        ]
    ])


CATEGORIES = [
    ("👗 Одежда",      "clothing"),
    ("🎧 Электроника", "electronics"),
    ("🏠 Дом",         "home"),
    ("💄 Красота",     "beauty"),
    ("👜 Аксессуары",  "accessories"),
    ("📦 Другое",      "other"),
]

CATEGORY_NAMES = {code: name for name, code in CATEGORIES}


def category_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for i in range(0, len(CATEGORIES), 2):
        row = [InlineKeyboardButton(
            text=CATEGORIES[i][0],
            callback_data=f"category:{CATEGORIES[i][1]}"
        )]
        if i + 1 < len(CATEGORIES):
            row.append(InlineKeyboardButton(
                text=CATEGORIES[i + 1][0],
                callback_data=f"category:{CATEGORIES[i + 1][1]}"
            ))
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def after_card_keyboard() -> InlineKeyboardMarkup:
    """Buttons shown after the product card is ready."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🎨 Сгенерировать дизайн-концепты",
            callback_data="action:design_concepts"
        )],
        [InlineKeyboardButton(
            text="🔄 Сделать новую карточку",
            callback_data="action:restart"
        )],
    ])


def after_design_keyboard() -> InlineKeyboardMarkup:
    """Buttons shown after text design concepts."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🖼 Сгенерировать 5 визуальных концептов",
            callback_data="action:visual_concepts"
        )],
        [InlineKeyboardButton(
            text="🔄 Сделать новую карточку",
            callback_data="action:restart"
        )],
    ])


def after_visuals_keyboard() -> InlineKeyboardMarkup:
    """Buttons shown after visual concepts."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔄 Сделать новую карточку",
            callback_data="action:restart"
        )],
        [InlineKeyboardButton(
            text="✏️ Изменить описание",
            callback_data="action:edit_benefits"
        )],
    ])
