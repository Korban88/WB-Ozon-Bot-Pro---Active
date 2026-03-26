# WB/Ozon AI Studio — Концепция и архитектура (v4.2)

> **Читай этот файл в начале нового диалога, чтобы сразу войти в контекст.**
> Здесь всё: что за продукт, как устроен, что менялось, где болевые точки.

---

## Быстрый старт

| Параметр | Значение |
|---|---|
| Репозиторий | `https://github.com/Korban88/WB-Ozon-Bot-Pro---Active` |
| Локальная папка | `C:\Claude Code Projects\WB-Ozon-Bot-Pro---Active` |
| Сервер | `31.129.108.93`, root, `VpD3IRb%ZzxI` |
| Путь на сервере | `/root/wb-ozon-bot` |
| Systemd сервис | `wb-ozon-bot.service` |

**Деплой после изменений:**
```bash
# Локально
git add -p && git commit -m "..." && git push origin main

# На сервере (через Node.js SSH, так как paramiko/sshpass недоступны на Windows)
node -e "require('C:/Users/korba/AppData/Local/Temp/ssh2mod/node_modules/ssh2').Client..."
# команда: cd /root/wb-ozon-bot && git pull origin main && systemctl restart wb-ozon-bot.service
```

**Просмотр логов:**
```bash
journalctl -u wb-ozon-bot.service -n 50 --no-pager
```

---

## Что за продукт

Telegram-бот для продавцов WB и Ozon. AI-студия: принимает ссылку на товар или ручной ввод — генерирует пять видов контента через отдельные модули. Пользователь вводит данные один раз (при аудите), далее все модули используют ту же сессию.

---

## Пять модулей

| # | Кнопка | Что делает | Ключевые файлы |
|---|---|---|---|
| 1 | 🔍 Аудит карточки | Парсит URL → CTR Score (детерм.) + AI-анализ с конкурентами | `bot/analysis.py`, `core/analysis_engine.py`, `services/audit_engine.py` |
| 2 | 🖼 5 визуалов | 5 изображений: AI-сцена + товар поверх (компоузитинг) | `bot/visuals.py`, `core/image_generation.py`, `core/visual_orchestrator.py` |
| 3 | 📊 Инфографика | ТЗ-бриф для дизайнера: 5 слайдов с типом, макетом, иконками | `bot/infographic.py`, `core/copy_generation.py` |
| 4 | 📣 Тексты карточки | SEO-листинг + рекламный копипак | `bot/copy.py`, `core/copy_generation.py` |
| 5 | 🎬 UGC Сценарий | Хук → Микро-история → Польза → CTA + раскадровка | `bot/ugc.py`, `core/copy_generation.py` |

---

## Главное правило — товар не трогать

Фото товара неприкосновенно. Пиксели, цвет, форма, логотип не меняются.

- **Разрешено:** анализировать через vision AI, вырезать фон (только alpha-канал), накладывать как слой поверх сцены
- **Запрещено:** перегенерировать товар, отправлять в API генерации изображений, изменять внешний вид

---

## Сессионная система (ProductData)

`ProductData` — единственный объект данных, путешествующий между всеми модулями.

```python
@dataclass
class ProductData:
    title, category, marketplace, benefits, brand, description
    price, original_price, article_id, rating, reviews_count, images_count
    url, photo_bytes

    def has_content() -> bool   # True если есть title + (benefits или description)
    def to_brief() -> str       # Текстовый бриф для LLM-промтов
    def to_state_dict() / from_state_dict()  # Сериализация в FSM state (без photo_bytes)
    @property discount_pct      # Скидка % от original_price
```

**Поток данных:**
1. Модуль 1 (Аудит) парсит URL → сохраняет полный `ProductData` в FSM state
2. Модули 2–5 проверяют `product.has_content()`:
   - Если True → пропускают вопросы, сразу генерируют
   - Если False → запрашивают минимум: название + преимущества

Хранение: `aiogram MemoryStorage` — данные живут до перезапуска бота.

---

## Парсинг маркетплейсов (v4.2)

### Wildberries — три уровня

**Уровень 1: Basket CDN** (основной, добавлен в v4.2)
- `basket-NN.wbbasket.ru/vol{V}/part{P}/{article}/info/ru/card.json`
- Не rate-limited, возвращает богатые данные: название, бренд, описание, характеристики, количество фото
- Функция `_wb_basket_cdn(article_id)` — параллельный перебор basket 01-43
- Basket-число вычисляется по таблице `_wb_basket_number(vol)`:
  - vol = article // 100000, step ~216 единиц на basket
  - Проверено: vol=2118 → basket-14, vol=6770 → basket-33
  - Сначала пробует approx±5 параллельно, затем оставшиеся

**Уровень 2: Search API** (для цены, рейтинга, отзывов)
- `search.wb.ru/exactmatch/ru/common/v4/search?query={article}&...`
- Может возвращать 429 (rate limiting) — retry 3 раза с backoff 1/2/4 сек
- Обрабатывает `catalog_type`:
  - `product-redirect` → follow-up запрос с `catalog=catalog_value`
  - `preset` → то же самое (добавлено в v4.2)
  - прочие → ищет точное совпадение id в products, берёт первый если нет

**Уровень 3: HTML scrape** (последний резерв)
- WB — SPA с antibot challenge (HTTP 498), обычно бесполезен с VPS IP
- Пробует og:title, og:description, JSON-LD

**Итог по полям:**
- Title, brand, description, category, images_count → из basket CDN
- Price, rating, reviews_count → из search API (опционально)

### Ozon — два уровня

1. `ozon.ru/api/entrypoint-api.bx/page/json/v2?url=/product/...` → парсит widgetStates
2. HTML scraping (og:title, JSON-LD)

### Кэш парсера
In-memory, TTL 60 минут. Ключ: `wb:ARTICLE_ID` или `ozon:ARTICLE_ID`. Только успешно распаршенные (с непустым title). Сбрасывается при рестарте.

### Конкуренты WB
`get_wb_competitors(title, n=5)` — поиск по первым 4 словам из названия через search API. Используется в Аудите.

---

## CTR Score (детерминированный, без LLM)

`services/audit_engine.py` → `calculate_ctr_score(product) -> dict`

Скоринг 0–99 по факторам: длина названия, рейтинг, количество отзывов, количество фото, скидка, бренд. Отдаётся первым сообщением (мгновенно), LLM-анализ — вторым.

Формат: `🟡 Средняя карточка — 54/100`

---

## Визуальный пак — архитектура (v4.1)

```
image_generation.py
  └─> VisualOrchestrator (visual_orchestrator.py)
        ├─ color_extractor: dominant_colors → color_mood ("warm terracotta and cream")
        ├─ card_types: get_card_types(category) → [hero, lifestyle, social, editorial, detail]
        ├─ build_scene_prompt(card_type, color_mood, marketplace, category) → prompt
        ├─> VisualProvider (provider_adapter.py) → generate_scene(brief) → bytes
        │     OpenAIProvider  — gpt-image-1, генерирует пустую сцену без товара
        │     PillowProvider  — returns None → Pillow-градиент из палитры
        │     ExternalProvider — stub для Fabula AI, MPCard и др.
        └─> card_renderer.render_card(card_type, scene_bytes, product_bytes) → PNG
              product_cutout → вырезает фон товара (rembg или corner-sampling)
              compositing → товар поверх сцены + мягкая тень
```

**5 типов карточек по категориям:**
| Тип | Описание |
|---|---|
| hero | Студийный, чистый фон — всегда слот 1 |
| lifestyle | Атмосферный интерьер |
| social | Outdoor / реальный контекст |
| editorial | Драматичный контраст, editorial-стиль |
| detail | Макро-фактура, материал |

Порядок слотов зависит от категории товара (одежда, электроника, красота и т.д.).

**Переключение провайдера:** `VISUAL_PROVIDER=openai|pillow|external` в `.env`

---

## Антигаллюцинационная система v3 (copy_generation.py)

Двухшаговая генерация:
1. LLM перечисляет ТОЛЬКО факты из ProductData (`_facts_inventory`)
2. LLM генерирует текст ИСКЛЮЧИТЕЛЬНО из этого списка

`_HARD_RULE` — вставляется в каждый промт, запрещает придумывать материалы, размеры, сертификаты, технические характеристики, страну производства, отзывы.

---

## Category-aware тон (copy_generation.py, v4.1)

| Категория | Тон |
|---|---|
| clothing | Модный, образный, живой язык |
| electronics | Технически точный, конкретные характеристики |
| beauty | Чувственный, нежный, sensory-язык |
| home | Уютный, тёплый, lifestyle |
| accessories | Статусный, изысканный |
| other | Деловой, чёткий |

`_tone(category)` добавляется в промты листинга и рекламы.

---

## UGC структура (v4.1)

Сценарий строится по схеме: **Хук → Микро-история → Польза → CTA**

JSON-поля ответа LLM: `hook`, `micro_story`, `benefit`, `cta`, `scenes[]`, `duration`, `format`

---

## Инфографика Blueprint v2

5 слайдов с полями для дизайнера:
- `slide_type` (cover/benefit/comparison/feature/cta)
- `visual_direction` — что изображать
- `layout` — расположение элементов
- `icons[]` — какие иконки нужны
- `headline`, `subheadline`, `bullets[]`

Порядок слайдов зависит от категории (одежда, электроника и т.д. — разные сценарии).

---

## Структура файлов

```
bot.py              Точка входа. Регистрирует роутеры, запускает polling.
config.py           .env → переменные. validate() при старте.
states.py           FSM-состояния: Menu, Analysis, Visuals, Copy, Infographic, UGC.
keyboards.py        Inline-клавиатуры.
logger_setup.py     log_event / log_error → logs/dialog.log

bot/                Telegram-обработчики (один файл = один модуль)
  menu.py           /start, /menu, главное меню
  analysis.py       Модуль 1: парсинг URL → CTR score → AI-анализ
  visuals.py        Модуль 2: 5 Premium Visuals (async generator)
  infographic.py    Модуль 3: Blueprint для дизайнера
  copy.py           Модуль 4: SEO-листинг + реклама
  ugc.py            Модуль 5: UGC видео-сценарий

core/               Бизнес-логика (без Telegram)
  analysis_engine.py     analyze_card() → AI-аудит + конкуренты
  copy_generation.py     4 функции: listing, ads, infographic, ugc. Anti-halluc v3.
  image_generation.py    generate_visual_pack() → async generator, 5 изображений
  visual_orchestrator.py VisualOrchestrator — режиссёр визуального пака
  provider_adapter.py    VisualProvider ABC + OpenAI/Pillow/External провайдеры

models/
  product_data.py   ProductData dataclass. Единственный объект данных в системе.

services/
  marketplace_parser.py  parse_url() → ProductData. Basket CDN + Search API + HTML.
  audit_engine.py        calculate_ctr_score() — детерминированный, без LLM.
  openrouter.py          HTTP-клиент: call() + parse_json() (срезает ```json обёртку).
  card_renderer.py       render_card(): scene + product → PNG 800×1000
  card_types.py          5 типов карточек + промты + маппинг по категориям
  card_composer.py       Компоузитинг слоёв
  card_layout.py         Позиционирование товара в кадре
  color_extractor.py     Pillow K-means: dominant_colors → color_mood
  product_cutout.py      Вырезка фона: rembg или corner-sampling
  background_gen.py      Генерация фона
  scene_gen.py           AI-сцены через gpt-image-1
  openai_image.py        OpenAI Images API клиент
  image_gen.py           Обёртка над генерацией изображений
  fonts.py               ensure_fonts() — скачивает Montserrat при первом запуске

utils/
  images.py         Утилиты для работы с изображениями
```

---

## Переменные окружения (.env)

| Переменная | Обязательна | Назначение |
|---|---|---|
| TELEGRAM_BOT_TOKEN | Да | Токен бота |
| OPENROUTER_API_KEY | Да | Все текстовые генерации (аудит, тексты, инфографика, UGC) |
| OPENAI_API_KEY | Нет | AI-сцены для визуалов (gpt-image-1). Без него — Pillow-градиент |
| OPENROUTER_MODEL | Нет | Текстовая модель. Default: `openai/gpt-4o-mini` |
| VISUAL_PROVIDER | Нет | `openai` (default) \| `pillow` \| `external` |
| EXTERNAL_VISUAL_API_KEY | Нет | Ключ для внешнего визуального сервиса (Fabula AI и др.) |
| EXTERNAL_VISUAL_API_URL | Нет | URL внешнего визуального сервиса |
| LOG_LEVEL | Нет | Default: INFO |

---

## Проблема с IP сервера (актуально на март 2026)

**Сервер 31.129.108.93 (Beget) rate-limited WB и заблокирован Ozon.**

| Endpoint | Статус |
|---|---|
| search.wb.ru (Search API) | 429 при частых запросах, иногда 200 |
| wildberries.ru HTML | HTTP 498 + antibot JS challenge |
| basket-NN.wbbasket.ru (CDN) | **200 работает** — основной метод с v4.2 |
| ozon.ru JSON API | 403 Antibot |

**Что работает:** basket CDN не rate-limited — основной источник данных для WB с v4.2.
**Что не работает:** Ozon JSON API и HTML с этого IP.

**Долгосрочное решение для Ozon:** residential proxy (~$5-10/мес).
- Добавить `PROXY_URL` в `.env`
- Передавать `proxy=PROXY_URL` в `aiohttp.ClientSession.get()` только для Ozon-запросов

**При малом числе пользователей (до 20/день):** search API часто работает — запросы разнесены во времени, 429 не триггерится регулярно.

---

## Известные особенности

| Ситуация | Поведение |
|---|---|
| WB basket CDN: формула basket неточна для высоких ID | `_wb_basket_cdn` пробует approx±5 параллельно, затем все 1-43 |
| WB search вернул product-redirect или preset | Follow-up запрос с `catalog=catalog_value` |
| WB search API вернул 429 | Retry 3× с backoff 1/2/4 сек, затем fallback |
| OPENAI_API_KEY не указан | Визуалы через Pillow-градиент |
| rembg не установлен | Фон вырезается через corner-sampling (для студийных фото ОК) |
| URL не распарсился / нет title | Предлагает ввести данные вручную |
| Данные уже есть в сессии | Модули 2–5 пропускают вопросы, сразу генерируют |
| JSON от AI с markdown-обёрткой | `parse_json()` срезает \`\`\`json … \`\`\` автоматически |
| FSM MemoryStorage | Данные сессии теряются при рестарте — это норма |
| Два экземпляра бота (TelegramConflictError) | `ps aux \| grep bot.py` → `kill PID` |

---

## История версий

**v1** — базовый диалог + 5 дизайн-концептов через Pillow.

**v2** — Premium Visuals без текста + Ad Copy Pack. Убрана Pillow-типографика.

**v3** — полный рерайт: AI Studio с 5 модулями, архитектура bot/core/services/models, меню-навигация, парсинг URL, общий ProductData, антигаллюцинационные правила.

**v3.1** — CTR Score (детерминированный). ProductData: `images_count`, `original_price`, `discount_pct`.

**v4** — WB парсер: `search.wb.ru` вместо `card.wb.ru` (endpoint умер). HTML scrape как fallback.

**v4.1** — обработка WB `product-redirect`. Поддержка нового формата WB API. In-memory кэш TTL 60 мин. Архитектура визуалов: VisualOrchestrator + VisualProvider ABC (OpenAI/Pillow/External). Category-aware тон для копирайтинга. UGC: Hook/Micro-story/Benefit/CTA. Инфографика: Blueprint v2 для дизайнера (slide_type, visual_direction, layout, icons).

**v4.2** — WB парсер: basket CDN как основной источник (не rate-limited, богатые данные). `_wb_basket_cdn()` — параллельный перебор basket 01-43. `_wb_basket_number()` — расширенная таблица шардов (до basket-43). Обработка `catalog_type: preset` (наравне с `product-redirect`). Retry на 429 с exponential backoff.
