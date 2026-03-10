# Деплой и запуск бота на VPS

Сервер: VPS Ubuntu
Папка на сервере: `/root/wb-ozon-bot`
Репозиторий: `https://github.com/Korban88/WB-Ozon-Bot-Pro---Active`

---

## Первый запуск (новый сервер)

### 1. Зайди на сервер

```bash
ssh root@IP_СЕРВЕРА
```

### 2. Скачай проект

```bash
cd /root
git clone https://github.com/Korban88/WB-Ozon-Bot-Pro---Active wb-ozon-bot
cd wb-ozon-bot
```

### 3. Проверь Python (нужна версия 3.11+)

```bash
python3 --version
```

Если старше — установи:
```bash
apt update && apt install -y python3.11 python3.11-venv python3-pip
```

### 4. Создай виртуальное окружение и установи зависимости

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Создай файл .env с ключами

```bash
cp .env.example .env
nano .env
```

Заполни:
```
TELEGRAM_BOT_TOKEN=токен_от_BotFather
OPENROUTER_API_KEY=ключ_от_openrouter.ai
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENAI_API_KEY=ключ_от_openai.com
LOG_LEVEL=INFO
```

- `OPENAI_API_KEY` — нужен для генерации Premium Visuals (gpt-image-1).
  Без него бот работает, но вместо AI-сцен будет Pillow-градиент.

Сохрани: `Ctrl+O` → Enter → `Ctrl+X`

### 6. Проверь запуск вручную

```bash
source venv/bin/activate
python bot.py
```

Нормальный вывод:
```
[INFO] Bot starting...
[INFO] Model: openai/gpt-4o-mini
[INFO] Bot is running. Press Ctrl+C to stop.
```

Если всё ок — останови: `Ctrl+C`

### 7. Настрой автозапуск через systemd

Создай файл сервиса:
```bash
nano /etc/systemd/system/wb-ozon-bot.service
```

Вставь:
```ini
[Unit]
Description=WB/Ozon Card Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/wb-ozon-bot
ExecStart=/root/wb-ozon-bot/venv/bin/python bot.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Сохрани: `Ctrl+O` → Enter → `Ctrl+X`

Активируй и запусти:
```bash
systemctl daemon-reload
systemctl enable wb-ozon-bot
systemctl start wb-ozon-bot
```

Проверь что запустился:
```bash
systemctl status wb-ozon-bot
```

Должно быть `Active: active (running)`.

---

## Обновление кода (после git push)

```bash
cd /root/wb-ozon-bot
git pull
systemctl restart wb-ozon-bot
```

Готово. Бот перезапустится с новым кодом.

---

## Полезные команды

**Статус бота:**
```bash
systemctl status wb-ozon-bot
```

**Лог в реальном времени:**
```bash
journalctl -u wb-ozon-bot -f
```

**Лог диалогов (JSON):**
```bash
tail -f /root/wb-ozon-bot/logs/dialog.log
```

**Остановить:**
```bash
systemctl stop wb-ozon-bot
```

**Перезапустить:**
```bash
systemctl restart wb-ozon-bot
```

---

## Если что-то сломалось

**Бот не стартует — смотри ошибку:**
```bash
journalctl -u wb-ozon-bot -n 50
```

**Частые причины:**
- Неверный `TELEGRAM_BOT_TOKEN` → ошибка `Unauthorized`
- Не заполнен `OPENROUTER_API_KEY` → бот упадёт на старте с `EnvironmentError`
- Нет виртуального окружения → `ExecStart` в systemd должен вести на `venv/bin/python`
- Шрифты не скачались → запусти `python bot.py` вручную один раз, бот их скачает сам

**Проверить .env:**
```bash
cat /root/wb-ozon-bot/.env
```

**Переустановить зависимости:**
```bash
cd /root/wb-ozon-bot
source venv/bin/activate
pip install -r requirements.txt
systemctl restart wb-ozon-bot
```
