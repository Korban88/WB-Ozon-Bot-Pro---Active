# WB/Ozon Card Bot — Project Concept & Architecture

> Читай этот файл в начале нового диалога, чтобы моментально войти в контекст проекта.

---

## Что это

Telegram-бот на Python для генерации продающих карточек товаров для маркетплейсов Wildberries и Ozon.
Стек: **aiogram 3.x · OpenRouter (LLM) · OpenAI gpt-image-1 (изображения) · rembg (вырезка фона) · Pillow (компоновка)**

Репозиторий: `https://github.com/Korban88/WB-Ozon-Bot-Pro---Active`
Сервер: VPS Ubuntu, папка `/root/wb-ozon-bot`, запуск `python bot.py`

---

## Структура файлов

```
bot.py                  # точка входа, polling
config.py               # env vars
states.py               # FSM-состояния
keyboards.py            # inline-кнопки
logger_setup.py         # JSON-логирование → logs/dialog.log

handlers/
  start.py              # /start
  dialog.py             # шаги 1-6: маркетплейс → категория → название → преимущества → фото → карточка
  design.py             # шаги 7-8: текстовые ТЗ концептов → визуальные карточки

services/
  openrouter.py         # LLM: generate_card() + generate_design_concepts()
  background_gen.py     # Layer 1: gpt-image-1 генерирует пустой стильный фон
  card_composer.py      # Layer 2: rembg вырезает фон товара + Pillow вставляет с тенью
  card_renderer.py      # Layer 3: Pillow накладывает текст (title + features)
  openai_image.py       # (legacy) старый монолитный подход — не используется в основном flow
  image_gen.py          # (legacy) Pollinations.ai — не используется

utils/images.py         # send_step_image() — отправляет PNG-иллюстрацию шага
assets/images/          # 11 PNG-иллюстраций: welcome, choose_marketplace, ..., error

CONCEPT.md              # этот файл — контекст проекта
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
              → visual_concepts  [3-layer pipeline → 5 карточек-изображений]
      → "Сделать новую карточку" → restart
```

---

## Генерация карточек (текст)

`services/openrouter.py` → `generate_card()`:
- Модель: `OPENROUTER_MODEL` (default `openai/gpt-4o-mini`)
- Vision-вызов: фото товара (base64) + данные пользователя
- Возвращает JSON: `{title, subtitle, description, features[], specs[], hashtags[]}`

`generate_design_concepts()`:
- Возвращает 5 концептов: `{index, name, colors, typography, composition}`
- `colors` — строка с 3 hex-цветами: `"Белый #FFFFFF · Синий #1A237E · Золотой #FFD700"`

---

## Генерация визуальных карточек (текущий pipeline)

### Step 1 — Сцена с товаром (`services/scene_gen.py`)
- `generate_scene()` → OpenAI `/v1/images/edits` с `gpt-image-1`
- Передаёт реальное фото товара → модель интегрирует товар в стильную сцену
- Единое освещение, товар — часть композиции (не стикер на фоне)
- Промт: NO TEXT, NO FRAMES, product as hero, unified lighting

### Step 2 — Текст (`services/card_renderer.py`)
- `overlay_text_premium()` → gradient fade снизу 26% (не тяжёлая плашка)
- Ease-in кривая прозрачности → плавный, не заметный переход
- Заголовок: Bold 40px + text-shadow, до 2 строк
- 3 буллета: `•` в accent-цвете + текст regular 22px
- Нет рамок, нет accent-стрип, нет разделителей

### Fallback (если нет OPENAI_API_KEY)
- `pillow_gradient_background()` → градиент из цветов концепта
- `render_card_pillow()` → продукт без белой рамки (soft ellipse shadow) + gradient text

---

## Переменные окружения (`.env` на сервере)

```
TELEGRAM_BOT_TOKEN=...
OPENROUTER_API_KEY=...         # обязательно
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=...             # для gpt-image-1 (дополнительно, для визуалов)
TOGETHER_API_KEY=...           # legacy, не используется
LOG_LEVEL=INFO
```

---

## Зависимости (`requirements.txt`)

```
aiogram==3.13.0
aiohttp==3.10.10
python-dotenv==1.0.1
Pillow>=10.0.0
rembg>=2.0.50          # AI-вырезка фона товара (скачивает u2net ~170MB при первом запуске)
onnxruntime>=1.16.0    # runtime для rembg
```

---

## Деплой на сервер

```bash
cd /root/wb-ozon-bot
git pull
source venv/bin/activate
pip install -r requirements.txt   # при первом запуске rembg скачает модель ~170MB
python bot.py
```

---

## Известные особенности / решённые проблемы

| Проблема | Решение |
|---|---|
| OpenRouter 401 | Неверный OPENROUTER_API_KEY в .env |
| Together AI 402 | Нет баланса → заменён на Pollinations → потом на gpt-image-1 |
| gpt-image-1 галлюцинирует текст | 3-layer pipeline: AI только фон, текст через Pillow |
| caption too long в Telegram | Фото + текст + кнопки — три отдельных сообщения |
| NameError marketplace | Добавлено чтение из state в cb_visual_concepts |
| Низкое качество изображений | Новый pipeline: фон → вырезка товара → текст отдельно |

---

## Актуальный статус (март 2026)

- ✅ Основной диалог работает (шаги 1–6, генерация карточки)
- ✅ Текстовые концепты работают (детальный формат ТЗ с hex-цветами)
- ✅ 3-layer pipeline внедрён (background_gen + card_composer + card_renderer)
- ⏳ Тестирование нового pipeline на сервере (rembg первый запуск = ~170MB)
- 🎯 Цель: визуальные карточки уровня professional marketplace design
