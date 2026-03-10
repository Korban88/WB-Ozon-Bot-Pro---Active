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
    """Buttons shown after the product text card is ready."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🖼 5 Premium Visuals",
            callback_data="action:premium_visuals"
        )],
        [InlineKeyboardButton(
            text="📣 Ad Copy Pack",
            callback_data="action:ad_copy"
        )],
        [InlineKeyboardButton(
            text="🔄 Новый товар",
            callback_data="action:restart"
        )],
    ])


def after_visuals_keyboard() -> InlineKeyboardMarkup:
    """Buttons shown after 5 premium visuals are generated."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📣 Ad Copy Pack",
            callback_data="action:ad_copy"
        )],
        [InlineKeyboardButton(
            text="🔄 Новый товар",
            callback_data="action:restart"
        )],
    ])


def after_ad_copy_keyboard() -> InlineKeyboardMarkup:
    """Buttons shown after ad copy pack is generated."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🖼 5 Premium Visuals",
            callback_data="action:premium_visuals"
        )],
        [InlineKeyboardButton(
            text="🔄 Новый товар",
            callback_data="action:restart"
        )],
    ])
