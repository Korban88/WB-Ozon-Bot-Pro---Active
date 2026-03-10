"""
Парсер карточек маркетплейсов.

WB:   использует публичный card API (без авторизации).
Ozon: парсит og-мета из HTML (js не нужен для og:title/og:description).

Правило: пустые поля — это нормально. Никогда не заполняем поля выдуманными данными.
"""

import re

import aiohttp

from models.product_data import ProductData

_WB_ARTICLE   = re.compile(r"/catalog/(\d+)/")
_OZON_ARTICLE = re.compile(r"/product/[^/]+-(\d+)/?")
_WB_API_URL   = "https://card.wb.ru/cards/v2/detail"
_HEADERS      = {"User-Agent": "Mozilla/5.0 (compatible; WBOzonBot/2.0)"}
_TIMEOUT      = aiohttp.ClientTimeout(total=15)


async def parse_url(url: str) -> ProductData | None:
    """
    Определяет маркетплейс по URL и парсит данные карточки.
    Возвращает None если URL не распознан.
    Возвращает ProductData с пустыми полями если данные не удалось получить.
    """
    url = url.strip()
    if "wildberries.ru" in url or "wb.ru" in url:
        return await _parse_wb(url)
    if "ozon.ru" in url:
        return await _parse_ozon(url)
    return None


async def _parse_wb(url: str) -> ProductData | None:
    m = _WB_ARTICLE.search(url)
    if not m:
        return None

    article_id = m.group(1)
    product = ProductData(article_id=article_id, marketplace="wb", url=url)

    try:
        params = {"appType": "1", "curr": "rub", "dest": "-1257786", "nm": article_id}
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(_WB_API_URL, params=params, headers=_HEADERS) as resp:
                if resp.status != 200:
                    return product
                data = await resp.json(content_type=None)

        items = data.get("data", {}).get("products", [])
        if not items:
            return product

        p = items[0]
        product.title         = p.get("name", "")
        product.brand         = p.get("brand", "")
        product.rating        = float(p.get("rating", 0))
        product.reviews_count = int(p.get("feedbacks", 0))
        product.category      = _wb_category(p.get("subjectName", ""))

        # Цена в копейках → рубли
        price_raw = p.get("salePriceU") or p.get("priceU") or 0
        if price_raw:
            product.price = price_raw // 100

    except Exception:
        pass  # возвращаем то, что успели заполнить

    return product


async def _parse_ozon(url: str) -> ProductData | None:
    m = _OZON_ARTICLE.search(url)
    product = ProductData(
        article_id=m.group(1) if m else "",
        marketplace="ozon",
        url=url,
    )

    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(url, headers={**_HEADERS, "Accept-Language": "ru-RU,ru;q=0.9"}) as resp:
                if resp.status != 200:
                    return product
                html = await resp.text()

        if m := re.search(r'<meta property="og:title" content="([^"]+)"', html):
            product.title = m.group(1).strip()

        if m := re.search(r'<meta property="og:description" content="([^"]+)"', html):
            product.description = m.group(1).strip()

    except Exception:
        pass

    return product


def _wb_category(subject: str) -> str:
    """Маппинг WB subjectName → наш код категории."""
    s = subject.lower()
    if any(w in s for w in ["одежда", "платье", "куртка", "брюки", "футболка", "пальто", "пиджак", "кофта", "свитер", "блузка", "юбка"]):
        return "clothing"
    if any(w in s for w in ["электроника", "телефон", "смартфон", "ноутбук", "планшет", "наушники", "колонка", "гарнитура", "зарядка"]):
        return "electronics"
    if any(w in s for w in ["красота", "уход", "косметика", "парфюм", "крем", "шампунь", "маска", "помада", "тушь"]):
        return "beauty"
    if any(w in s for w in ["дом", "интерьер", "мебель", "посуда", "декор", "постель", "кухня", "ванная"]):
        return "home"
    if any(w in s for w in ["сумка", "рюкзак", "кошелёк", "ремень", "очки", "перчатки", "шапка", "кепка", "шарф", "платок", "аксессуар"]):
        return "accessories"
    return "other"
