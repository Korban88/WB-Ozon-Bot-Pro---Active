"""
WB/Ozon AI Studio — точка входа.

Регистрирует роутеры всех модулей и запускает polling.
"""

import asyncio
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import config
from bot.menu        import router as menu_router
from bot.analysis    import router as analysis_router
from bot.visuals     import router as visuals_router
from bot.infographic import router as infographic_router
from bot.copy        import router as copy_router
from bot.ugc         import router as ugc_router
from logger_setup    import log
from services.fonts  import ensure_fonts


async def main() -> None:
    try:
        config.validate()
    except EnvironmentError as exc:
        log.error("Configuration error: %s", exc)
        sys.exit(1)

    bot = Bot(
        token   = config.TELEGRAM_BOT_TOKEN,
        default = DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Порядок важен: menu первым (обрабатывает /start и menu:main из любого состояния)
    dp.include_router(menu_router)
    dp.include_router(analysis_router)
    dp.include_router(visuals_router)
    dp.include_router(infographic_router)
    dp.include_router(copy_router)
    dp.include_router(ugc_router)

    ensure_fonts()
    log.info("WB/Ozon AI Studio starting. Model: %s", config.OPENROUTER_MODEL)
    log.info("OpenAI visuals: %s", "enabled" if config.OPENAI_API_KEY else "disabled (Pillow fallback)")

    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Bot is running. Press Ctrl+C to stop.")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        log.info("Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
