"""
ProductData — единственный объект, который передаётся между модулями.

ПРАВИЛО: все поля берутся из ввода пользователя или парсера маркетплейса.
Нельзя придумывать или подставлять значения, которых нет в источнике.
"""

from dataclasses import dataclass, field


@dataclass
class ProductData:
    title:         str   = ""
    category:      str   = "other"
    marketplace:   str   = "wb"
    benefits:      str   = ""       # описание и преимущества от продавца
    brand:         str   = ""
    description:   str   = ""       # описание из карточки маркетплейса
    price:         int   = 0
    original_price: int  = 0        # цена до скидки (для расчёта discount_pct)
    article_id:    str   = ""
    rating:        float = 0.0
    reviews_count: int   = 0
    images_count:  int   = 0        # кол-во фото карточки (WB: поле pics)
    url:           str   = ""
    photo_bytes:   bytes = field(default=b"", repr=False)

    def has_content(self) -> bool:
        """True если есть достаточно данных для генерации текстов."""
        return bool(self.title) and bool(self.benefits or self.description)

    @property
    def discount_pct(self) -> int:
        """Скидка в процентах от оригинальной цены."""
        if self.original_price > self.price > 0:
            return round((1 - self.price / self.original_price) * 100)
        return 0

    def to_brief(self) -> str:
        """Текстовый бриф для промтов LLM. Только непустые поля."""
        mp = {"wb": "Wildberries", "ozon": "Ozon"}.get(self.marketplace, self.marketplace)
        cat = {
            "clothing": "Одежда", "electronics": "Электроника",
            "home": "Дом и интерьер", "beauty": "Красота и уход",
            "accessories": "Аксессуары", "other": "Другое",
        }.get(self.category, self.category)

        parts = []
        if self.title:         parts.append(f"Название: {self.title}")
        if self.brand:         parts.append(f"Бренд: {self.brand}")
        if self.category != "other": parts.append(f"Категория: {cat}")
        if self.marketplace:   parts.append(f"Маркетплейс: {mp}")
        if self.price:
            price_str = f"Цена: {self.price}₽"
            if self.discount_pct:
                price_str += f" (скидка {self.discount_pct}%)"
            parts.append(price_str)
        if self.rating:        parts.append(f"Рейтинг: {self.rating}/5 ({self.reviews_count} отзывов)")
        if self.images_count:  parts.append(f"Фотографий в карточке: {self.images_count}")
        if self.description:   parts.append(f"Описание: {self.description[:600]}")
        if self.benefits:      parts.append(f"Преимущества (от продавца): {self.benefits[:600]}")
        return "\n".join(parts)

    def to_state_dict(self) -> dict:
        """Сериализация для FSM state. Без photo_bytes."""
        return {
            "title": self.title, "category": self.category, "marketplace": self.marketplace,
            "benefits": self.benefits, "brand": self.brand, "description": self.description,
            "price": self.price, "original_price": self.original_price,
            "article_id": self.article_id, "rating": self.rating,
            "reviews_count": self.reviews_count, "images_count": self.images_count,
            "url": self.url,
        }

    @classmethod
    def from_state_dict(cls, d: dict | None) -> "ProductData":
        if not d:
            return cls()
        return cls(
            title=d.get("title", ""),              category=d.get("category", "other"),
            marketplace=d.get("marketplace", "wb"), benefits=d.get("benefits", ""),
            brand=d.get("brand", ""),              description=d.get("description", ""),
            price=d.get("price", 0),               original_price=d.get("original_price", 0),
            article_id=d.get("article_id", ""),    rating=d.get("rating", 0.0),
            reviews_count=d.get("reviews_count", 0), images_count=d.get("images_count", 0),
            url=d.get("url", ""),
        )
