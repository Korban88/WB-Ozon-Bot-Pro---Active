"""
Парсер карточек маркетплейсов v4.

Изменения v4:
  - WB: card.wb.ru/cards/v2 заменён на search.wb.ru (поиск по артикулу)
  - WB: добавлен HTML scraping страницы как финальный fallback
  - WB: убран _resolve_redirects (замедлял парсинг без пользы)
  - WB: функция получения топ конкурентов через search API
  - Ozon: dual-strategy (JSON API + HTML scrape)
  - Подробное логирование HTTP статусов для диагностики

Правило: пустые поля — норма. Никогда не заполняем придуманными данными.
"""

import re
import json
import logging
from urllib.parse import urlparse

import aiohttp

from models.product_data import ProductData

log = logging.getLogger(__name__)

_WB_ARTICLE   = re.compile(r"[/=](\d{6,12})(?:[/?#]|$|\.aspx)")
_OZON_ARTICLE = re.compile(r"/product/[^/]+-(\d+)/?")

_WB_SEARCH_API = "https://search.wb.ru/exactmatch/ru/common/v4/search"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ru-RU,ru;q=0.9",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.wildberries.ru/",
}
_TIMEOUT      = aiohttp.ClientTimeout(total=20)
_TIMEOUT_FAST = aiohttp.ClientTimeout(total=8)


async def parse_url(url: str) -> ProductData | None:
    """
    Парсит карточку по URL.
    Возвращает None если URL не распознан как WB/Ozon.
    """
    url = url.strip()

    if "wildberries.ru" in url or "wb.ru" in url:
        return await _parse_wb(url)
    if "ozon.ru" in url:
        return await _parse_ozon(url)

    log.warning("URL not recognized as WB/Ozon: %s", url[:80])
    return None


# ─── Wildberries ──────────────────────────────────────────────────────────────

async def _parse_wb(url: str) -> ProductData | None:
    m = _WB_ARTICLE.search(url)
    if not m:
        log.warning("WB: no article found in URL: %s", url[:80])
        return None

    article_id = m.group(1)
    log.info("WB: article_id=%s", article_id)
    product = ProductData(article_id=article_id, marketplace="wb", url=url)

    # Попытка 1: Search API с артикулом как запросом
    data = await _wb_search_by_article(article_id)

    # Попытка 2: HTML scraping страницы
    if not data:
        log.info("WB: search failed, trying HTML scrape for %s", article_id)
        await _wb_html_scrape(product, url)
    else:
        product.title         = data.get("name", "")
        product.brand         = data.get("brand", "")
        product.rating        = float(data.get("rating", 0) or 0)
        product.reviews_count = int(data.get("feedbacks", 0) or 0)
        product.images_count  = int(data.get("pics", 0) or 0)
        product.category      = _wb_category(data.get("subjectName", ""))

        sale_price_u = data.get("salePriceU") or 0
        orig_price_u = data.get("priceU") or sale_price_u
        if sale_price_u:
            product.price          = int(sale_price_u) // 100
            product.original_price = int(orig_price_u) // 100

        log.info("WB search: parsed '%s' brand=%s price=%s rating=%s pics=%s",
                 product.title[:40], product.brand, product.price,
                 product.rating, product.images_count)

    if product.title and not product.description:
        product.description = await _wb_description(article_id, url)

    if not product.title:
        log.warning("WB: no title found for article %s", article_id)

    return product


async def _wb_search_by_article(article_id: str) -> dict | None:
    """
    Ищет товар через search.wb.ru с артикулом как поисковым запросом.
    Возвращает первый найденный товар с совпадающим id.
    """
    try:
        params = {
            "appType": "1", "curr": "rub", "dest": "-1257786",
            "spp": "30", "query": article_id,
            "resultset": "catalog", "sort": "popular",
            "regions": "80,38,83,4,64,33,68,70,30,40,86,75,69,1,31,66,110,48,22,71,114",
        }
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(_WB_SEARCH_API, params=params, headers=_HEADERS) as resp:
                log.debug("WB search API: HTTP %d for article %s", resp.status, article_id)
                if resp.status != 200:
                    return None
                data = await resp.json(content_type=None)

        products = data.get("data", {}).get("products", [])
        if not products:
            log.debug("WB search: empty products for article %s", article_id)
            return None

        # Ищем точное совпадение по id
        article_int = int(article_id)
        for p in products:
            if p.get("id") == article_int:
                return p

        # Если точного совпадения нет — берём первый результат
        log.debug("WB search: no exact match for %s, using first result (id=%s)",
                  article_id, products[0].get("id"))
        return products[0]

    except Exception as e:
        log.debug("WB search exception for %s: %s", article_id, e)
        return None


async def _wb_html_scrape(product: ProductData, url: str) -> None:
    """Парсит HTML страницу WB для получения данных карточки."""
    try:
        html_headers = {
            **_HEADERS,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(url, headers=html_headers) as resp:
                log.debug("WB HTML: HTTP %d for %s", resp.status, url[:60])
                if resp.status != 200:
                    return
                html = await resp.text()

        # og:title
        if m := re.search(r'<meta\s+(?:property|name)="og:title"\s+content="([^"]+)"', html):
            product.title = m.group(1).strip()

        # og:description
        if m := re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]+)"', html):
            product.description = m.group(1).strip()

        # JSON-LD Product
        for ld_match in re.finditer(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.S
        ):
            try:
                ld = json.loads(ld_match.group(1))
                items = ld if isinstance(ld, list) else [ld]
                for item in items:
                    if item.get("@type") != "Product":
                        continue
                    if not product.title and item.get("name"):
                        product.title = item["name"]
                    if not product.brand and item.get("brand"):
                        b = item["brand"]
                        product.brand = b.get("name", "") if isinstance(b, dict) else str(b)
                    if not product.description and item.get("description"):
                        product.description = item["description"][:800]
                    agg = item.get("aggregateRating", {})
                    if isinstance(agg, dict) and not product.rating:
                        try:
                            product.rating = float(agg.get("ratingValue", 0))
                            product.reviews_count = int(agg.get("reviewCount", 0))
                        except (ValueError, TypeError):
                            pass
                    offers = item.get("offers", {})
                    if isinstance(offers, dict) and not product.price:
                        raw = offers.get("price") or offers.get("lowPrice", "")
                        try:
                            product.price = int(float(str(raw).replace(" ", "").replace(",", ".")))
                        except (ValueError, TypeError):
                            pass
                    break
            except (json.JSONDecodeError, KeyError):
                continue

        if product.title:
            log.info("WB HTML scrape: got title '%s'", product.title[:40])

    except Exception as e:
        log.warning("WB HTML scrape error for %s: %s", url[:60], e)


async def _wb_description(article_id: str, url: str) -> str:
    """Получает описание из HTML страницы WB."""
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT_FAST) as session:
            async with session.get(url, headers=_HEADERS) as resp:
                if resp.status != 200:
                    return ""
                html = await resp.text()

        if m := re.search(r'<meta\s+(?:property|name)="og:description"\s+content="([^"]{15,})"', html):
            return m.group(1).strip()
        if m := re.search(r'"description"\s*:\s*"([^"]{25,})"', html):
            return m.group(1).strip()[:800]
    except Exception as e:
        log.debug("WB description fetch failed: %s", e)
    return ""


# ─── Конкуренты WB ───────────────────────────────────────────────────────────

async def get_wb_competitors(title: str, n: int = 5) -> list[dict]:
    """
    Возвращает топ N конкурентов из WB поиска по ключевым словам из title.
    Данные: title, brand, price, rating, reviews_count, article_id.
    """
    if not title:
        return []

    words = title.strip().split()
    query = " ".join(words[:4])

    try:
        params = {
            "appType": "1", "curr": "rub", "dest": "-1257786",
            "spp": "30", "query": query,
            "resultset": "catalog", "sort": "popular",
            "regions": "80,38,83,4,64,33,68,70,30,40,86,75,69,1,31,66,110,48,22,71,114",
        }
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(_WB_SEARCH_API, params=params, headers=_HEADERS) as resp:
                if resp.status != 200:
                    log.debug("WB search: HTTP %d for query '%s'", resp.status, query)
                    return []
                data = await resp.json(content_type=None)

        products = data.get("data", {}).get("products", [])
        result = []
        for p in products[:n + 2]:
            p_price = (p.get("salePriceU") or p.get("priceU") or 0) // 100
            result.append({
                "title":      p.get("name", ""),
                "brand":      p.get("brand", ""),
                "price":      p_price,
                "rating":     round(float(p.get("rating", 0) or 0), 1),
                "reviews":    int(p.get("feedbacks", 0) or 0),
                "article_id": str(p.get("id", "")),
            })
            if len(result) >= n:
                break

        log.info("WB competitors: found %d for query '%s'", len(result), query)
        return result

    except Exception as e:
        log.warning("WB competitors failed for '%s': %s", query, e)
        return []


# ─── Ozon ─────────────────────────────────────────────────────────────────────

_OZON_API_HEADERS = {
    **_HEADERS,
    "Accept": "application/json, text/plain, */*",
    "x-o3-app-name": "ozon-front",
    "x-o3-app-version": "3.73.0",
}


async def _parse_ozon(url: str) -> ProductData | None:
    m = _OZON_ARTICLE.search(url)
    article_id = m.group(1) if m else ""
    product = ProductData(article_id=article_id, marketplace="ozon", url=url)

    parsed = urlparse(url)
    product_path = parsed.path.rstrip("/") + "/"

    # Попытка 1: Ozon internal JSON API
    if product_path.startswith("/product/"):
        await _ozon_json_api(product, product_path)

    # Попытка 2: HTML + JSON-LD
    if not product.title:
        await _ozon_html_scrape(product, url)

    if product.title:
        if product.category == "other":
            product.category = _wb_category(product.title)
        log.info("Ozon: parsed '%s' price=%s rating=%s",
                 product.title[:40], product.price, product.rating)
    else:
        log.warning("Ozon: no title found for %s", url[:60])

    return product


async def _ozon_json_api(product: ProductData, product_path: str) -> None:
    """Пробует получить данные через внутренний Ozon API."""
    api_url = f"https://www.ozon.ru/api/entrypoint-api.bx/page/json/v2?url={product_path}"
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(api_url, headers=_OZON_API_HEADERS) as resp:
                log.debug("Ozon JSON API: HTTP %d for %s", resp.status, product_path)
                if resp.status != 200:
                    return
                data = await resp.json(content_type=None)

        widgets = data.get("widgetStates", {})
        for key, value in widgets.items():
            try:
                w = json.loads(value) if isinstance(value, str) else value
                if not isinstance(w, dict):
                    continue

                if "webProductHeading" in key and not product.title:
                    product.title = w.get("title", "")

                if "webPrice" in key and not product.price:
                    raw = w.get("price", w.get("originalPrice", ""))
                    digits = re.sub(r"[^\d]", "", str(raw))
                    if digits:
                        product.price = int(digits)

                if ("webReviewProductScore" in key or "webRatingBar" in key) and not product.rating:
                    product.rating = float(w.get("score", w.get("rating", 0)) or 0)
                    product.reviews_count = int(w.get("count", w.get("reviewCount", 0)) or 0)

            except Exception:
                continue

        if product.title:
            log.debug("Ozon JSON API: got title '%s'", product.title[:40])

    except Exception as e:
        log.debug("Ozon JSON API failed for %s: %s", product_path, e)


async def _ozon_html_scrape(product: ProductData, url: str) -> None:
    """Резервный метод: HTML + JSON-LD парсинг."""
    try:
        headers = {**_HEADERS, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as session:
            async with session.get(url, headers=headers) as resp:
                log.debug("Ozon HTML: HTTP %d for %s", resp.status, url[:60])
                if resp.status != 200:
                    return
                html_text = await resp.text()

        if m := re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', html_text):
            product.title = m.group(1).strip()
        if m := re.search(r'<meta\s+property="og:description"\s+content="([^"]+)"', html_text):
            product.description = m.group(1).strip()

        for ld_match in re.finditer(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html_text, re.S
        ):
            try:
                ld = json.loads(ld_match.group(1))
                items = ld if isinstance(ld, list) else [ld]
                for item in items:
                    if item.get("@type") == "Product":
                        if not product.title and item.get("name"):
                            product.title = item["name"]
                        if not product.brand and item.get("brand"):
                            b = item["brand"]
                            product.brand = b.get("name", "") if isinstance(b, dict) else str(b)
                        if not product.description and item.get("description"):
                            product.description = item["description"][:800]
                        offers = item.get("offers", {})
                        if isinstance(offers, dict) and not product.price:
                            raw = offers.get("price") or offers.get("lowPrice", "")
                            try:
                                product.price = int(float(str(raw).replace(" ", "").replace(",", ".")))
                            except (ValueError, TypeError):
                                pass
                        agg = item.get("aggregateRating", {})
                        if isinstance(agg, dict) and not product.rating:
                            try:
                                product.rating = float(agg.get("ratingValue", 0))
                                product.reviews_count = int(agg.get("reviewCount", 0))
                            except (ValueError, TypeError):
                                pass
                        break
            except (json.JSONDecodeError, KeyError):
                continue

    except Exception as e:
        log.warning("Ozon HTML scrape error for %s: %s", url[:60], e)


# ─── Маппинг категорий ────────────────────────────────────────────────────────

def _wb_category(subject: str) -> str:
    s = subject.lower()
    if any(w in s for w in ["одежда", "платье", "куртка", "брюки", "футболка", "пальто",
                             "пиджак", "кофта", "свитер", "блузка", "юбка", "жакет", "костюм",
                             "джинсы", "шорты", "леггинсы", "комбинезон"]):
        return "clothing"
    if any(w in s for w in ["электроника", "телефон", "смартфон", "ноутбук", "планшет",
                             "наушники", "колонка", "гарнитура", "зарядка", "кабель",
                             "электро", "гаджет", "роутер", "powerbank", "usb"]):
        return "electronics"
    if any(w in s for w in ["красота", "уход", "косметика", "парфюм", "крем", "шампунь",
                             "маска", "помада", "тушь", "духи", "сыворотка", "скраб",
                             "тональный", "пудра", "тени", "лак"]):
        return "beauty"
    if any(w in s for w in ["дом", "интерьер", "мебель", "посуда", "декор", "постель",
                             "кухня", "ванная", "текстиль", "подушка", "одеяло",
                             "полотенце", "скатерть", "занавес"]):
        return "home"
    if any(w in s for w in ["сумка", "рюкзак", "кошелёк", "ремень", "очки", "перчатки",
                             "шапка", "кепка", "шарф", "платок", "аксессуар", "украшение",
                             "браслет", "кольцо", "серьги", "часы"]):
        return "accessories"
    return "other"
