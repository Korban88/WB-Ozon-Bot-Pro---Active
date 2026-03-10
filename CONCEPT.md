# WB/Ozon Card Bot — Product Architecture v2

> Читай этот файл в начале нового диалога, чтобы моментально войти в контекст проекта.

---

## Что это

Telegram-бот на Python для создания трёх типов контента для продавцов маркетплейсов.
Стек: **aiogram 3.x · OpenRouter (LLM) · OpenAI gpt-image-1 · Pillow · Montserrat**

Репозиторий: `https://github.com/Korban88/WB-Ozon-Bot-Pro---Active`
Сервер: VPS Ubuntu, папка `/root/wb-ozon-bot`
Запуск: `source venv/bin/activate && python bot.py`

---

## Три продуктовых слоя

### Layer 1 — Текст карточки (Marketplace Listing)
SEO-заголовок, описание, характеристики, буллеты, хэштеги.
Генерируется через OpenRouter vision из фото + данных продавца.
Доставляется как текстовые сообщения — готово к вставке в редактор WB/Ozon.

### Layer 2 — 5 Premium Visuals
Пять атмосферных сцен с товаром, 800×1000px (4:5 portrait).
**Без текста на изображении** — чистый premium product photography.
Готовы для: допфото в WB/Ozon, соцсети, рекламные баннеры.

### Layer 3 — Ad Copy Pack
Пять рекламных хуков, три короткие копи, две средние копи, UGC-бриф.
Доставляется как текст — готово для VK Реклама, Telegram Ads, Яндекс, UGC.

---

## КРИТИЧЕСКОЕ ПРАВИЛО: неизменность товара

**Товар никогда не изменяется, не перегенерируется, не искажается.**

Запрещено:
- Менять цвет, форму, принт, логотип, текст на упаковке товара
- Перегенерировать товар через AI
- Отправлять фото товара в API генерации изображений (только OpenRouter vision)

Товар используется только как:
1. Ввод для OpenRouter vision (только чтение / анализ)
2. Источник для удаления фона (только alpha-канал, пиксели товара неизменны)
3. Immutable RGBA-слой поверх сцены

---

## Диалог пользователя

```
/start
  → choose_marketplace  (WB / Ozon)
  → choose_category     (Одежда, Электроника, Дом, Красота, Аксессуары, Другое)
  → enter_title         (название товара)
  → enter_benefits      (описание и преимущества)
  → upload_photo        (фото товара)
  → generating          [OpenRouter vision → JSON-карточка]
  → show_card           (текстовая карточка + кнопки)
      → "5 Premium Visuals"  → premium_visuals  [5 чистых сцен без текста]
      → "Ad Copy Pack"       → ad_copy          [хуки + копи + UGC-бриф]
      → "Новый товар"        → restart
```

---

## Visual Pipeline (Layer 2)

```
User photo
  │
  ├─► color_extractor → color_mood (из пикселей товара, не из промта)
  ├─► product_cutout  → RGBA cutout (фон удалён, пиксели товара неизменны)
  │
  └─► Для каждого из 5 card_types:
        scene_gen → пустая сцена-фон (gpt-image-1 /generations, товар НЕ отправляется)
        card_renderer → composite: сцена + товар (Pillow, БЕЗ текста поверх)
        → отправить PNG 800×1000
```

---

## Пять типов карточек

| Тип | Сцена | Позиция товара |
|---|---|---|
| hero | Студийный градиентный фон | Чуть выше центра |
| lifestyle | Интерьерная атмосфера, натуральный свет | Центр |
| social | Outdoor / улица / сад, soft bokeh | Чуть ниже центра |
| editorial | Драматический кинематографичный | Верхняя треть |
| detail | Макро-фактура материала | Центр, крупно |

Все типы: 800×1000px, full-height сцена, zero text overlay.

---

## Структура файлов

```
bot.py              — точка входа, polling, ensure_fonts() при старте
config.py           — env vars
states.py           — FSM-состояния
keyboards.py        — inline-кнопки

handlers/
  start.py          — /start
  dialog.py         — шаги 1–6: маркетплейс → категория → название → преимущества → фото → текст
  design.py         — шаги 7–8: premium_visuals, ad_copy

services/
  openrouter.py     — generate_card(), generate_ad_copy()
  scene_gen.py      — generate_scene(): пустой фон через gpt-image-1 /generations
  card_renderer.py  — render_card(): composite товар на сцену (без текста)
  card_types.py     — 5 типов, промты сцен, CANVAS_LAYOUT
  color_extractor.py — extract_dominant_colors() из фото товара
  product_cutout.py — удаление фона (rembg или Pillow corner-sampling)
  fonts.py          — Montserrat: ensure_fonts() + get_font()
  card_layout.py    — legacy (не используется в основном pipeline)

utils/images.py     — send_step_image() helper
assets/images/      — PNG-иллюстрации шагов
assets/fonts/       — Montserrat TTF (скачиваются при первом запуске)
```

---

## Переменные окружения

```
TELEGRAM_BOT_TOKEN=...        # обязательно
OPENROUTER_API_KEY=...        # обязательно
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=...            # для gpt-image-1 /generations (Premium Visuals)
LOG_LEVEL=INFO
```

---

## Что НЕ делать

- **Не накладывать текст на изображения** — слабая Pillow-типографика даёт шаблонный вид
- **Не отправлять фото товара в image gen API** — искажение товара
- **Не перегенерировать товар** — нарушение product immutability rule
- **Не использовать features card type** (удалён в v2 — был Pillow-only инфографик)
- **Не пытаться "починить" слабую типографику** — текст живёт в копипаке, не на изображении

---

## Roadmap

| Версия | Что | Статус |
|---|---|---|
| v2 | Premium Visuals без текста + Ad Copy Pack | **Текущий** |
| v3 | Multi-format creatives (1:1, 9:16) для VK/Telegram Ads | Запланировано |
| v4 | Higgsfield video: product showcase видео из фото | Запланировано |
| v5 | Web SaaS, subscription, bulk processing | Future |

---

## Деплой

```bash
cd /root/wb-ozon-bot
git pull
source venv/bin/activate
python bot.py
```

---

## Известные особенности

| Проблема | Решение |
|---|---|
| rembg OOM Killed | REMBG отключён, используется Pillow corner-sampling |
| gpt-image-1 галлюцинирует текст | Текст только в копипаке, не на изображении |
| caption too long в Telegram | Фото + текст + кнопки — три отдельных сообщения |
| Montserrat 404 | URL исправлен на JulietaUla/Montserrat репозиторий |
