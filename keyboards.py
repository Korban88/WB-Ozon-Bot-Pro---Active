from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def _kb(*rows: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    """Хелпер: список рядов [(text, callback_data), ...]"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t, callback_data=c) for t, c in row]
            for row in rows
        ]
    )


def _back() -> list[tuple[str, str]]:
    return [("↩️ Главное меню", "menu:main")]


# ── Главное меню ──────────────────────────────────────────────────────────────

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return _kb(
        [("🔍 Аудит карточки",    "module:analysis")],
        [("🖼 Visual Pack",        "module:visuals")],
        [("📊 Инфографика",        "module:infographic")],
        [("📣 Copy Pack",          "module:copy")],
        [("🎬 UGC сценарий",       "module:ugc")],
    )


# ── После анализа ─────────────────────────────────────────────────────────────

def after_analysis_keyboard() -> InlineKeyboardMarkup:
    """Кнопки после анализа. Данные уже в state — модули пропустят ввод."""
    return _kb(
        [("🖼 Visual Pack",   "module:visuals"),  ("📣 Copy Pack",   "module:copy")],
        [("📊 Инфографика",   "module:infographic"), ("🎬 UGC",      "module:ugc")],
        _back(),
    )


# ── Анализ: ручной ввод когда парсер вернул пустую карточку ──────────────────

def analysis_fallback_keyboard() -> InlineKeyboardMarkup:
    """Предлагаем ручной ввод или выход в меню."""
    return _kb(
        [("✏️ Ввести данные вручную", "analysis:manual")],
        _back(),
    )


# ── После визуалов ────────────────────────────────────────────────────────────

def after_visuals_keyboard() -> InlineKeyboardMarkup:
    return _kb(
        [("📣 Copy Pack",     "module:copy"),   ("🎬 UGC сценарий", "module:ugc")],
        [("📊 Инфографика",   "module:infographic")],
        _back(),
    )


# ── После текстов / инфографики / UGC ─────────────────────────────────────────

def after_copy_keyboard() -> InlineKeyboardMarkup:
    return _kb(
        [("🖼 Visual Pack",     "module:visuals")],
        [("🔍 Новый аудит",     "module:analysis")],
        _back(),
    )


# ── Категории ─────────────────────────────────────────────────────────────────

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
        row = [(CATEGORIES[i][0], f"category:{CATEGORIES[i][1]}")]
        if i + 1 < len(CATEGORIES):
            row.append((CATEGORIES[i + 1][0], f"category:{CATEGORIES[i + 1][1]}"))
        rows.append(row)
    return _kb(*rows)
