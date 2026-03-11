"""
Парсер карточек маркетплейсов v2.

WB:   использует card API v2 (основной) + catalog API v1 (запасной) + HTML (описание).
Ozon: парсит og-мета + JSON-LD из HTML.

Правило: пустые поля — это нормально. Никогда не заполняем поля выдуманными данными.
"""

import re
import json

import aiohttp

from models.product_data import ProductData

_WB_ARTICLE   = re.compile(r"/catalog/(\d+)/")
_OZON_ARTICLE = re.compile(r"/product/[^/]+-(\d+)/?")

# WB API endpoints — пробуем по порядку
_WB_API_V2   = "https://card.wb.ru/cards/v2/detail"
_WB_API_V1   = "https://catalog.wb.ru/cards/v1/detail"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
}
_TIMEOUT = aiohttp.ClientTimeout(total=20)


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


# ─── Wildberries ──────────────────────────────────────────────────────────────

async def _parse_wb(url: str) -> ProductData | None:
    m = _WB_ARTICLE.search(url)
    if not m:
        return None

    article_id = m.group(1)
    product = ProductData(article_id=article_id, marketplace="wb", url=url)

    # Пробуем v2, потом v1
    data = await _wb_api_v2(article_id) or await _wb_api_v1(article_id)

    if data:
        product.title         = data.get("name", "")
        product.brand         = data.get("brand", "")
        product.rating        = float(data.get("rating", 0) or 0)
        product.reviews_count = int(data.get("feedbacks", 0) or 0)
        product.category      = _wb_category(data.get("subjectName", ""))

        price_raw = data.get("salePriceU") or data.get("priceU") or 0
        if price_raw:
            product.price = int(price_raw) // 100

    # Если есть заголовок — пробуем получить описание из HTML
    if product.title and not product.description:
        product.description = await _wb_description(article_id, url)

    return product


async def _wb_api_v2(article_id: str) -> dict | None:
    """WB Card API v2 — основной."""
    try:
        params = {"appType": "1", "curr": "rub", "dest": "-1257786", "nm": article_id}
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(_WB_API_V2, params=params, headers=_HEADERS) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
        items = data.get("data", {}).get("products", [])
        return items[0] if items else None
    except Exception:
        return None


async def _wb_api_v1(article_id: str) -> dict | None:
    """WB Catalog API v1 — запасной."""
    try:
        params = {"appType": "1", "curr": "rub", "dest": "-1257786", "nm": article_id}
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(_WB_API_V1, params=params, headers=_HEADERS) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)
        items = (data.get("data", {}) or {}).get("products", [])
        return items[0] if items else None
    except Exception:
        return None


async def _wb_description(article_id: str, url: str) -> str:
    """Пытается получить описание товара из HTML страницы WB."""
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(url, headers=_HEADERS) as resp:
                if resp.status != 200:
                    return ""
                html = await resp.text()

        # og:description
        if m := re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]{10,})"', html):
            return m.group(1).strip()

        # JSON-LD description
        if m := re.search(r'"description"\s*:\s*"([^"]{20,})"', html):
            return m.group(1).strip()[:800]

    except Exception:
        pass
    return ""


# ─── Ozon ─────────────────────────────────────────────────────────────────────

async def _parse_ozon(url: str) -> ProductData | None:
    m = _OZON_ARTICLE.search(url)
    product = ProductData(
        article_id=m.group(1) if m else "",
        marketplace="ozon",
        url=url,
    )

    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(url, headers=_HEADERS) as resp:
                if resp.status != 200:
                    return product
                html = await resp.text()

        # og:title
        if m := re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html):
            product.title = m.group(1).strip()

        # og:description
        if m := re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html):
            product.description = m.group(1).strip()

        # JSON-LD — более богатые данные
        for ld_match in re.finditer(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S):
            try:
                ld = json.loads(ld_match.group(1))
                items = ld if isinstance(ld, list) else [ld]
                for item in items:
                    if item.get("@type") == "Product":
                        if not product.title and item.get("name"):
                            product.title = item["name"]
                        if not product.brand and item.get("brand"):
                            brand = item["brand"]
                            product.brand = brand.get("name", "") if isinstance(brand, dict) else str(brand)
                        if not product.description and item.get("description"):
                            product.description = item["description"][:800]
                        # Цена
                        offers = item.get("offers", {})
                        if isinstance(offers, dict):
                            price_str = offers.get("price", "") or offers.get("lowPrice", "")
                            try:
                                product.price = int(float(str(price_str).replace(" ", "").replace(",", ".")))
                            except (ValueError, TypeError):
                                pass
                        # Рейтинг
                        agg = item.get("aggregateRating", {})
                        if isinstance(agg, dict):
                            try:
                                product.rating = float(agg.get("ratingValue", 0))
                                product.reviews_count = int(agg.get("reviewCount", 0))
                            except (ValueError, TypeError):
                                pass
                        break
            except (json.JSONDecodeError, KeyError):
                continue

        # Категория по заголовку
        if product.title and product.category == "other":
            product.category = _wb_category(product.title)

    except Exception:
        pass

    return product


# ─── Маппинг категорий ────────────────────────────────────────────────────────

def _wb_category(subject: str) -> str:
    """Маппинг субкатегории → наш код категории."""
    s = subject.lower()
    if any(w in s for w in ["одежда", "платье", "куртка", "брюки", "футболка", "пальто",
                             "пиджак", "кофта", "свитер", "блузка", "юбка", "жакет", "костюм"]):
        return "clothing"
    if any(w in s for w in ["электроника", "телефон", "смартфон", "ноутбук", "планшет",
                             "наушники", "колонка", "гарнитура", "зарядка", "кабель",
                             "электро", "гаджет", "роутер"]):
        return "electronics"
    if any(w in s for w in ["красота", "уход", "косметика", "парфюм", "крем", "шампунь",
                             "маска", "помада", "тушь", "духи", "сыворотка", "скраб"]):
        return "beauty"
    if any(w in s for w in ["дом", "интерьер", "мебель", "посуда", "декор", "постель",
                             "кухня", "ванная", "текстиль", "подушка", "одеяло"]):
        return "home"
    if any(w in s for w in ["сумка", "рюкзак", "кошелёк", "ремень", "очки", "перчатки",
                             "шапка", "кепка", "шарф", "платок", "аксессуар", "украшение"]):
        return "accessories"
    return "other"
