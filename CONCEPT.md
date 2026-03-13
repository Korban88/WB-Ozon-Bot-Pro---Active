# WB/Ozon AI Studio — Концепция и архитектура (v4.1)

> Читай этот файл в начале нового диалога, чтобы сразу войти в контекст.

---

## Быстрый старт (новый компьютер / новый диалог)

1. Репозиторий: `git clone` → локальная папка `C:\Claude Code Projects\wb-ozon-bot\`
2. Сервер: VPS Beget Ubuntu, IP `31.129.108.93`, пользователь `root`
3. Бот запущен через `systemd`: `systemctl restart wb-ozon-bot`
4. Деплой: локально `git push`, на сервере `cd /root/wb-ozon-bot && git pull && systemctl restart wb-ozon-bot`
5. SSH-ключи добавлены на GitHub — сервер тянет репо напрямую

Если что-то не работает — читай раздел «Известные особенности» и «Проблема с IP» ниже.

---

## Что за продукт и зачем он нужен

Telegram-бот для продавцов на Wildberries и Ozon. Работает как AI-студия: принимает ссылку на карточку товара или описание от продавца и генерирует пять видов контента через отдельные модули с общим меню.

---

## Пять модулей

| # | Кнопка | Что делает |
|---|---|---|
| 1 | 🔍 Аудит карточки | Парсит URL с WB или Ozon, выдаёт CTR-скор (без LLM) + AI-анализ с конкурентами |
| 2 | 🖼 5 визуалов | Генерирует 5 изображений для карточки (атмосферные сцены с товаром) |
| 3 | 📊 Инфографика | ТЗ для 5 инфографических слайдов (текстовый бриф для дизайнера) |
| 4 | 📣 Тексты карточки | SEO-листинг: название, описание, буллеты |
| 5 | 🎬 Сценарий видео | Сценарий короткого ролика для соцсетей (хук + сцены + CTA) |

---

## Главное правило — товар не трогать

Фото товара — неприкосновенный объект. Пиксели, цвет, форма, логотип — не меняются.

Что разрешено с фото товара:
- Отправить в OpenRouter для анализа (только чтение)
- Вырезать фон (только alpha-канал, пиксели товара не меняются)
- Наложить как слой поверх сгенерированной сцены

Что запрещено:
- Перегенерировать товар
- Отправлять фото товара в API генерации изображений
- Изменять форму, цвет, принт, логотип

---

## Умное повторное использование данных

Данные о товаре сохраняются в FSM-сессии. Если пользователь уже сделал анализ карточки — все остальные модули пропускают вопросы и сразу генерируют, используя те же данные.

Порядок заполнения данных:
- Модуль 1 (Аудит) → парсит URL и сохраняет полную ProductData
- Модули 2–5 → проверяют `product.has_content()` и пропускают ввод если данные есть
- Если данных нет → каждый модуль собирает минимум: название + преимущества

---

## Антигаллюцинационное правило

Все промты для генерации текста содержат явный запрет:

> ЗАПРЕЩЕНО: придумывать материалы, размеры, сертификаты, технические характеристики, страну производства, отзывы, сравнения с конкурентами — если это не указано в ТЗ.

Это встроено в каждую функцию генерации как константа `_NO_HALLUCINATION`.

---

## Как работает парсинг URL (v4.1)

### Wildberries
1. Regex извлекает `article_id` из URL (например `387710847` из `/catalog/387710847/detail.aspx`)
2. **Основной метод:** запрос к `search.wb.ru/exactmatch/ru/common/v4/search` с артикулом как query
3. **Обработка product-redirect:** WB возвращает `catalog_type: product-redirect` + `catalog_value` когда ищешь по точному артикулу — делаем второй запрос с параметром `catalog=<catalog_value>` (добавлено в v4.1)
4. **Поддержка двух форматов ответа:** `data.products` (старый) и корневой `products` (новый формат WB API) — добавлено в v4.1
5. **Fallback:** HTML scraping страницы товара (og:title, og:description, JSON-LD)
6. **Почему не card.wb.ru:** `card.wb.ru/cards/v2/detail` → 404 с марта 2026, WB убрали публичный API
7. **Почему не basket CDN:** `basket-NN.wb.ru` — часть доменов не резолвится с сервера Beget; `static-basket-NN.wbbasket.ru` — резолвится только basket-01..09, современные артикулы (>~43M) лежат на basket-22+

### Ozon
1. Regex извлекает `article_id` из URL
2. **Основной метод:** внутренний Ozon JSON API (`/api/entrypoint-api.bx/page/json/v2?url=/product/...`) — парсит widgetStates (webProductHeading → title, webPrice → price, webRatingBar → rating)
3. **Fallback:** HTML scraping страницы (og:title, JSON-LD)

Если парсинг не дал title — бот предлагает ввести данные вручную.

### Конкуренты WB
`get_wb_competitors(title, n=5)` — поиск через search.wb.ru по первым 4 словам из названия. Используется в Аудите для сравнения.

### Кэш парсера (v4.1)
`services/marketplace_parser.py` содержит in-memory кэш с TTL 60 минут.
Ключ: `wb:ARTICLE_ID` или `ozon:ARTICLE_ID`. Кэшируются только карточки с непустым title.
Сбрасывается при перезапуске бота. Снижает нагрузку на WB/Ozon API при повторных запросах одного артикула.

---

## CTR Score (детерминированный, без LLM)

`services/audit_engine.py`:
- `calculate_ctr_score(product)` — скоринг 0-99 по 6 факторам: длина названия, рейтинг, количество отзывов, количество фото, скидка, бренд
- `format_ctr_block(ctr)` — HTML-блок с прогресс-баром `█████░░░░░  54/100`

Отправляется первым сообщением (быстро), LLM-анализ — вторым (после ожидания).

---

## Как генерируются Premium Visuals

**Шаг 1.** Из фото товара извлекают доминирующие цвета (Pillow). Получают строку вроде `"warm terracotta and cream"` — это `color_mood`.

**Шаг 2.** Отправляют запрос в OpenAI gpt-image-1: "сгенерируй пустую сцену-фон в таком-то стиле, в такой палитре". Товар в промт не попадает. Получают фоновую картинку без товара.

**Шаг 3.** Вырезают фон из фото товара — остаётся RGBA-вырезка. Если rembg не установлен — используется Pillow corner-sampling (достаточно для студийных фото).

**Шаг 4.** Накладывают RGBA-вырезку товара поверх сцены, добавляют мягкую тень. Никакого текста. Сохраняют PNG 800×1000.

Если `OPENAI_API_KEY` не указан — вместо AI-сцены генерируется Pillow-градиент из цветов товара.

5 слотов: hero(1) + lifestyle(2) + ad_creative(2). Изображения отправляются по мере готовности через async generator.

---

## Структура файлов

```
bot.py              Точка входа. Регистрирует 6 роутеров, запускает polling.
config.py           Читает .env, валидирует обязательные переменные.
states.py           FSM-состояния: Menu, Analysis, Visuals, Copy, Infographic, UGC.
keyboards.py        Inline-клавиатуры для каждого экрана.
logger_setup.py     Логирование: log_event/log_error → logs/dialog.log

bot/                Обработчики Telegram (по одному на модуль)
  menu.py           /start, /menu, menu:main — показывает главное меню.
  analysis.py       Модуль 1: парсинг URL + CTR score + AI-анализ.
  visuals.py        Модуль 2: генерация 5 Premium Visuals.
  infographic.py    Модуль 3: бриф для 5 инфографических слайдов.
  copy.py           Модуль 4: SEO-листинг + рекламный копипак.
  ugc.py            Модуль 5: UGC видео-сценарий.

core/               Бизнес-логика (без Telegram)
  analysis_engine.py   analyze_card() → структурированный AI-анализ + конкуренты.
  copy_generation.py   4 функции генерации текста с _NO_HALLUCINATION.
  image_generation.py  generate_visual_pack() → async generator, 5 изображений.

models/
  product_data.py   ProductData dataclass. to_state_dict() / from_state_dict().
                    has_content() → bool. to_brief() → строка для LLM.
                    discount_pct (property). Поля: images_count, original_price.

services/
  marketplace_parser.py  parse_url() → ProductData. WB search API + HTML scrape.
  audit_engine.py        calculate_ctr_score() + format_ctr_block(). Без LLM.
  openrouter.py          Тонкий HTTP-клиент: call() + parse_json().
  scene_gen.py           Генерирует фон через gpt-image-1 (товар не попадает).
  card_renderer.py       render_card(): сцена + товар → PNG. Без текста.
  card_types.py          5 типов визуальных карточек + маппинг по категориям.
  color_extractor.py     Извлекает доминирующие цвета из фото (Pillow K-means).
  product_cutout.py      Вырезает фон: rembg или Pillow corner-sampling.
  fonts.py               ensure_fonts() — скачивает Montserrat при первом запуске.
```

---

## Переменные окружения

| Переменная | Обязательна | Зачем |
|---|---|---|
| TELEGRAM_BOT_TOKEN | Да | Токен бота от @BotFather |
| OPENROUTER_API_KEY | Да | Все текстовые генерации (анализ, копипак, инфографика, UGC) |
| OPENAI_API_KEY | Нет | Генерация AI-сцен для визуалов (gpt-image-1). Без него — Pillow-градиент |
| OPENROUTER_MODEL | Нет | Модель для текста. Default: openai/gpt-4o-mini |
| LOG_LEVEL | Нет | Default: INFO |

---

## ⚠️ Проблема с IP сервера (актуально на март 2026)

**Сервер Beget (31.129.108.93) заблокирован обоими маркетплейсами.**

Проверено 13.03.2026:

| Метод | WB | Ozon |
|---|---|---|
| search.wb.ru / JSON API | 429 при нагрузке, иначе 200 с пустым результатом | 403 Antibot |
| HTML scraping | Antibot JS challenge ("Почти готово...") | 403 Antibot Challenge Page |
| basket CDN (wbbasket.ru) | basket-22+ не резолвится | — |

**Причина:** IP датацентра Beget находится в блок-листах WB и Ozon как известный VPS-провайдер.

**При малом числе пользователей (до 20/день) парсинг может работать** — запросы естественно разнесены во времени и 429 не триггерится. Проблемы начались из-за ~40 тестовых запросов за 2 часа в одной сессии отладки.

**Долгосрочное решение — residential proxy:**
- Добавить переменную `PROXY_URL` в `.env`
- Передавать `proxy=PROXY_URL` в `aiohttp.ClientSession.get()`
- Только для запросов к WB/Ozon, не для OpenRouter/OpenAI
- Стоимость: ~$5-10/мес (SmartProxy, ProxyEmpire и др.)

**Для тестирования логики** — запустить бота локально на домашнем компьютере (домашний IP не в бане).

---

## Известные особенности

| Ситуация | Как работает |
|---|---|
| WB search вернул product-redirect | Делаем follow-up запрос с параметром `catalog=catalog_value` |
| WB search API вернул 429 (rate limit) | Пробуем HTML scraping страницы товара |
| card.wb.ru/cards/v2 → 404 | Ожидаемо — WB убрали этот endpoint. Используется search API |
| Ozon заблокировал по IP (Cloudflare 403) | Оба метода (JSON API и HTML) могут блокироваться с VPS IP |
| OPENAI_API_KEY не указан | Визуалы генерируются через Pillow-градиент вместо AI-сцен |
| rembg не установлен | Фон вырезается через Pillow corner-sampling (для студийных фото ОК) |
| URL не распарсился | Бот сообщает об ошибке, предлагает ввести данные вручную |
| Данные уже есть в сессии | Модули 2–5 пропускают вопросы и генерируют сразу |
| JSON от AI с markdown-обёрткой | parse_json() автоматически срезает ```json ... ``` |
| FSM MemoryStorage | Данные сессии теряются при перезапуске бота — это норма |
| Два экземпляра бота (TelegramConflictError) | Убить старый процесс: `ps aux \| grep bot.py`, затем `kill PID` |

---

## История версий

**v1** — базовый диалог с текстом карточки + 5 дизайн-концептов через Pillow.
**v2** — Premium Visuals без текста + Ad Copy Pack. Убрана Pillow-типографика.
**v3** — полный рерайт: AI Studio с 5 модулями, новая архитектура bot/core/services/models, меню-навигация, парсинг URL маркетплейсов, общий ProductData между модулями, антигаллюцинационные правила в каждом промте.
**v3.1** — CTR Score (детерминированный, без LLM). Интеграция в Аудит. ProductData: поля images_count, original_price, discount_pct. Упрощён текст меню (убраны термины Visual Pack, UGC, blueprint).
**v4** — WB парсер переписан: search.wb.ru вместо card.wb.ru (endpoint умер). Добавлен HTML scrape как fallback для WB. Убран _resolve_redirects (не нужен). Ozon: dual-strategy без изменений.
**v4.1** — Обработка WB product-redirect (follow-up запрос с `catalog` параметром). Поддержка нового формата ответа WB API (products на корневом уровне). In-memory кэш парсера TTL 60 минут. Задокументирована проблема блокировки IP сервера Beget.
