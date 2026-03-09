# Деплой на VPS (Beget или любой другой)

## 1. Загрузи файлы на сервер

```bash
# С локальной машины (через scp или rsync)
scp -r ./wb-ozon-bot user@your-server:/home/user/wb-ozon-bot
```

Или через Git:
```bash
git clone https://github.com/your-repo/wb-ozon-bot
cd wb-ozon-bot
```

## 2. Установи Python и зависимости

```bash
# Проверь версию Python (нужна 3.11+)
python3 --version

# Создай виртуальное окружение
python3 -m venv venv
source venv/bin/activate

# Установи зависимости
pip install -r requirements.txt
```

## 3. Создай файл .env

```bash
cp .env.example .env
nano .env
```

Заполни значения:
```
TELEGRAM_BOT_TOKEN=токен_от_BotFather
OPENROUTER_API_KEY=ключ_OpenRouter
OPENROUTER_MODEL=openai/gpt-4o-mini
TOGETHER_API_KEY=ключ_TogetherAI  # опционально, для генерации изображений
LOG_LEVEL=INFO
```

## 4. Проверь запуск вручную

```bash
source venv/bin/activate
python bot.py
```

Ожидаемый вывод:
```
2026-03-09 12:00:00 [INFO] bot: Bot starting...
2026-03-09 12:00:00 [INFO] bot: Model: openai/gpt-4o-mini
2026-03-09 12:00:00 [INFO] bot: Together AI: enabled
2026-03-09 12:00:00 [INFO] bot: Bot is running. Press Ctrl+C to stop.
```

Нажми Ctrl+C для остановки.

## 5. Запусти как systemd-сервис (работает после перезагрузки)

Создай файл сервиса:
```bash
sudo nano /etc/systemd/system/wb-ozon-bot.service
```

Содержимое (замени пути и пользователя на свои):
```ini
[Unit]
Description=WB/Ozon Card Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/wb-ozon-bot
ExecStart=/home/your_username/wb-ozon-bot/venv/bin/python bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Активируй и запусти:
```bash
sudo systemctl daemon-reload
sudo systemctl enable wb-ozon-bot
sudo systemctl start wb-ozon-bot
```

Проверь статус:
```bash
sudo systemctl status wb-ozon-bot
```

## 6. Просмотр логов

Системный журнал (stdout бота):
```bash
sudo journalctl -u wb-ozon-bot -f
```

Логи диалогов (JSON строки):
```bash
tail -f logs/dialog.log
# или красиво:
tail -f logs/dialog.log | python3 -m json.tool
```

## 7. Перезапуск после обновления кода

```bash
git pull
sudo systemctl restart wb-ozon-bot
```

## Структура логов

Каждая строка в `logs/dialog.log` — JSON объект:

```json
{"time": "2026-03-09T12:00:01.234", "user_id": 123456, "username": "ivan", "event": "step_completed", "step": "enter_title", "data": {"title": "Беспроводные наушники"}, "error": null}
```

Типы событий:
- `bot_started` — пользователь нажал /start
- `step_completed` — завершён шаг диалога (поле `step` = название шага)
- `ai_call` — вызов AI API (поле `data.success`, `data.duration_ms`)
- `card_generated` — карточка успешно сгенерирована
- `design_concepts_shown` — текстовые концепты показаны
- `visual_concepts_done` — визуальные концепты готовы
- `error` — ошибка (поле `error` содержит описание)
- `restart` — пользователь нажал «Сделать новую карточку»
