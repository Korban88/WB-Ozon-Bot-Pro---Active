"""
WB/Ozon Card Bot — entry point.

Start:
    python bot.py

The bot runs in polling mode (no webhook needed for VPS).
"""

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from handlers import design, dialog, start
from logger_setup import log
from services.fonts import ensure_fonts


async def main() -> None:
    # Validate required environment variables before starting
    try:
        config.validate()
    except EnvironmentError as exc:
        log.error("Configuration error: %s", exc)
        sys.exit(1)

    # Create bot with HTML parse mode as default
    bot = Bot(
        token=config.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # MemoryStorage: dialog states are stored in RAM.
    # Simple and reliable — no external dependencies.
    # Note: states are lost on bot restart (users will need to /start again).
    storage = MemoryStorage()

    # Create dispatcher and register all routers
    dp = Dispatcher(storage=storage)
    dp.include_router(start.router)   # /start command
    dp.include_router(dialog.router)  # main dialog flow
    dp.include_router(design.router)  # design & visual concepts

    log.info("Bot starting...")
    ensure_fonts()   # download Montserrat if not cached
    log.info("Model: %s", config.OPENROUTER_MODEL)
    log.info("Together AI: %s", "enabled" if config.TOGETHER_API_KEY else "disabled (no API key)")

    # Drop any updates that arrived while bot was offline
    await bot.delete_webhook(drop_pending_updates=True)

    log.info("Bot is running. Press Ctrl+C to stop.")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        log.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
