# WB/Ozon Card Bot — Project Concept & Architecture

> Читай этот файл в начале нового диалога, чтобы моментально войти в контекст проекта.

---

## Что это

Telegram-бот на Python для генерации продающих карточек товаров для маркетплейсов Wildberries и Ozon.
Стек: **aiogram 3.x · OpenRouter (LLM) · OpenAI gpt-image-1 (/edits) · Pillow (вёрстка) · Montserrat (шрифты)**

Репозиторий: `https://github.com/Korban88/WB-Ozon-Bot-Pro---Active`
Сервер: VPS Ubuntu, папка `/root/wb-ozon-bot`
Запуск: `source venv/bin/activate && python bot.py`

---

## Структура файлов

```
bot.py                  # точка входа, polling, ensure_fonts() при старте
config.py               # env vars
states.py               # FSM-состояния
keyboards.py            # inline-кнопки
logger_setup.py         # JSON-логирование → logs/dialog.log

handlers/
  start.py              # /start
  dialog.py             # шаги 1-6: маркетплейс → категория → название → преимущества → фото → карточка
  design.py             # шаги 7-8: текстовые ТЗ концептов → визуальные карточки (5 типов)

services/
  openrouter.py         # LLM: generate_card() + generate_design_concepts()
  card_types.py         # ядро системы: 5 типов карточек, промты, маппинг по категории
  scene_gen.py          # gpt-image-1 /edits: генерирует сцену с товаром по типу карточки
  card_renderer.py      # render_card(): 5 layout-движков + drawn Pillow icons
  background_gen.py     # pillow_gradient_background() — fallback-фон
  fonts.py              # Montserrat: ensure_fonts() + get_font()
  card_layout.py        # (legacy, не используется в основном flow)
  card_composer.py      # (legacy, rembg отключён — OOM на VPS)
  openai_image.py       # (legacy)
  image_gen.py          # (legacy, Pollinations.ai)

utils/images.py         # send_step_image() — отправляет PNG-иллюстрацию шага
assets/images/          # 11 PNG-иллюстраций: welcome, choose_marketplace, ..., error
assets/fonts/           # Montserrat TTF (скачиваются при первом запуске)

CONCEPT.md              # этот файл
```

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
      → "Сгенерировать дизайн-концепты"
          → design_concepts   [OpenRouter → 5 текстовых ТЗ]
          → "Сгенерировать 5 визуальных концептов"
              → visual_concepts  [5 карточек разных типов]
      → "Сделать новую карточку" → restart
```

---

## Генерация текстовой карточки

`services/openrouter.py` → `generate_card()`:
- Модель: `OPENROUTER_MODEL` (default `openai/gpt-4o-mini`)
- Vision-вызов: фото товара (base64) + данные пользователя
- Возвращает JSON: `{title, subtitle, description, features[], specs[], hashtags[]}`

`generate_design_concepts()`:
- Возвращает 5 концептов: `{index, name, colors, typography, composition}`
- `colors` — строка с 3 hex-цветами: `"Белый #FFFFFF · Синий #1A237E · Золотой #FFD700"`

---

## Генерация визуальных карточек (актуальный pipeline)

### Формат
**800×1000 px (4:5)** — стандарт WB/Ozon для карточек товаров.

### Архитектура: 5 типов карточек

Тип карточки определяется категорией товара (`services/card_types.py`):

| Категория | Порядок 5 типов |
|---|---|
| Одежда | hero · lifestyle · features · editorial · detail |
| Электроника | hero · features · lifestyle · editorial · detail |
| Красота | hero · lifestyle · features · detail · editorial |
| Дом | hero · lifestyle · features · detail · editorial |
| Аксессуары | hero · editorial · lifestyle · features · detail |
| Другое | hero · lifestyle · features · editorial · detail |

### Типы карточек

| Тип | Сцена | Панель | Промт-референс | Назначение |
|---|---|---|---|---|
| **hero** | 740px | 260px | Apple/Muji clean studio | Первое впечатление, thumbnail |
| **lifestyle** | 850px | 150px | Warm real environment | Эмоция, атмосфера |
| **features** | 380px | 620px | Pillow (без AI) | Иконки преимуществ |
| **editorial** | 650px | 350px | Vogue/Dazed art-directed | Дорогая типографика |
| **detail** | 800px | 200px | Luxury macro, raking light | Материал, качество |

### Pipeline для каждой карточки

```
1. generate_scene(card_type, concept, product_bytes)
   → gpt-image-1 /edits: товар интегрирован в сцену с правильным освещением
   → для 'features': возвращает None (Pillow gradient background)

2. render_card(card_type, scene_bytes, product_bytes, title, features, colors)
   → _make_canvas(): scene zone + gradient blend + text panel
   → type-specific typography zone renderer
```

### Типографика по типу

| Тип | Шрифт/размер | Элементы |
|---|---|---|
| hero | Bold 48px | Заголовок 1-2 строки, один подзаголовок |
| lifestyle | SemiBold 40px | Одна строка названия, одна фича |
| features | Bold 34px + drawn icons | 4 блока: иконка + название + описание |
| editorial | Bold 60px tracked | Tracked uppercase, `·` разделители |
| detail | SemiBold 32px tracked | Tracked caps, thin rule |

### Drawn icons для FEATURES карточки

Pillow рисует геометрические иконки на основе текста фичи:
- **star** — качество, premium, высококачественный
- **shield** — прочность, защита, долговечность
- **wave** — материал, ткань, шерсть, хлопок
- **leaf** (arcs) — комфорт, мягкость, удобство
- **diamond** — стиль, дизайн (default)

### Montserrat (`services/fonts.py`)

- `ensure_fonts()` → скачивает Bold/SemiBold/Regular/Light из репозитория JulietaUla/Montserrat
- Кэшируется в `assets/fonts/`, при повторных запусках не скачивается
- `get_font(variant, size)` → с fallback на системные шрифты Ubuntu

### Fallback (если нет OPENAI_API_KEY)

- `pillow_gradient_background(colors)` → градиент из цветов концепта
- `_place_product()` → продукт с soft ellipse shadow в scene zone
- Typography zone отрабатывает так же

---

## Переменные окружения (`.env` на сервере)

```
TELEGRAM_BOT_TOKEN=...
OPENROUTER_API_KEY=...         # обязательно
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=...             # для gpt-image-1 /edits (визуальные карточки)
LOG_LEVEL=INFO
```

---

## Зависимости (`requirements.txt`)

```
aiogram==3.13.0
aiohttp==3.10.10
python-dotenv==1.0.1
Pillow>=10.0.0
# rembg и onnxruntime ОТКЛЮЧЕНЫ — OOM на VPS (модель u2net 176MB)
```

---

## Деплой на сервер

```bash
cd /root/wb-ozon-bot
git pull
source venv/bin/activate
python bot.py
```

При первом запуске после `git pull` — бот скачает шрифты Montserrat (~600KB).

---

## Известные особенности / решённые проблемы

| Проблема | Решение |
|---|---|
| OpenRouter 401 | Неверный OPENROUTER_API_KEY в .env |
| Together AI 402 | Нет баланса → заменён на gpt-image-1 |
| gpt-image-1 галлюцинирует текст в сцене | Текст только через Pillow, в промтах строгий запрет |
| rembg OOM Killed | REMBG отключён навсегда, используется soft ellipse shadow |
| caption too long в Telegram | Фото + текст + кнопки — три отдельных сообщения |
| Montserrat 404 | URL исправлен на JulietaUla/Montserrat репозиторий |
| 5 одинаковых карточек | Заменено системой 5 типов карточек (hero/lifestyle/features/editorial/detail) |
| Белая рамка вокруг товара | Убрана: продукт вставляется без фрейма, только soft shadow |

---

## Актуальный статус (март 2026)

- ✅ Основной диалог работает (шаги 1–6, генерация текстовой карточки)
- ✅ Текстовые концепты работают (детальный формат ТЗ с hex-цветами)
- ✅ 5 типов визуальных карточек: hero / lifestyle / features / editorial / detail
- ✅ Типы зависят от категории товара
- ✅ Montserrat автоматически скачивается при старте
- ✅ rembg отключён, используется Pillow compositing
- ✅ Формат 4:5 (800×1000) — маркетплейс-стандарт
