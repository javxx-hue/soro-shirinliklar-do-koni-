"""
Main entrypoint for the Sweet Shop Telegram Bot.
Configures database lifecycle, internationalization middlewares,
bot menu commands, and aggregates all feature routers.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional, Tuple
import aiosqlite
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

from database.db import get_db_connection, init_db
from handlers import (
    admin_router,
    ai_consultant_router,
    cart_router,
    catalog_router,
    common_router,
    custom_cake_router,
    order_router,
    payments_router,
)
from middlewares.i18n import I18nMiddleware
from shop_config import Config, load_config

# Backward compatibility helper for assistant test suite
def settings_from_process_env(require_telegram: bool = True):
    """Read configuration from os.environ and clear keys in a finally block."""
    import os
    from typing import Any, Dict
    from assistant.config import SETTING_KEYS, load_settings
    env_vars: Dict[str, Any] = {}
    for key in SETTING_KEYS:
        if key in os.environ:
            env_vars[key] = os.environ[key]
    try:
        return load_settings(
            require_telegram=require_telegram,
            source=env_vars,
        )
    finally:
        for key in SETTING_KEYS:
            os.environ.pop(key, None)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("sweet_shop_bot")

DEFAULT_MOCK_TOKEN = "123456789:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQR"


def build_app(
    config: Optional[Config] = None,
    db_connection: Optional[aiosqlite.Connection] = None,
) -> Tuple[Bot, Dispatcher]:
    """
    Constructs and returns configured Bot and Dispatcher instances:
    - Injects config and active DB connection into dispatcher workflow data.
    - Registers I18nMiddleware on message and callback_query events.
    - Includes all 8 application routers in correct matching order.
    """
    cfg = config or load_config()
    token = cfg.bot_token if (cfg.bot_token and ":" in cfg.bot_token) else DEFAULT_MOCK_TOKEN

    bot = Bot(
        token=token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Inject dependency context
    dp["config"] = cfg
    if db_connection is not None:
        dp["db"] = db_connection

    # Setup internationalization middleware
    i18n_middleware = I18nMiddleware(db=db_connection)
    dp.message.middleware(i18n_middleware)
    dp.callback_query.middleware(i18n_middleware)

    # Register all 8 application routers
    dp.include_router(common_router)
    dp.include_router(admin_router)
    dp.include_router(catalog_router)
    dp.include_router(cart_router)
    dp.include_router(order_router)
    dp.include_router(custom_cake_router)
    dp.include_router(payments_router)
    dp.include_router(ai_consultant_router)

    return bot, dp


async def setup_bot_commands(bot: Bot) -> None:
    """
    Configures official Telegram bot menu commands for user discovery.
    """
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish / Перезапустить бота"),
        BotCommand(command="catalog", description="Shirinliklar katalogi / Каталог сладостей"),
        BotCommand(command="cart", description="Savatcha / Корзина"),
        BotCommand(command="custom_cake", description="O'z tortingizga buyurtma / Торт на заказ"),
        BotCommand(command="my_orders", description="Buyurtmalarim / Мои заказы"),
        BotCommand(command="ai", description="Shirinlik maslahatchisi / ИИ-консультант"),
        BotCommand(command="language", description="Tilni o'zgartirish / Сменить язык"),
        BotCommand(command="about", description="Do'kon haqida va aloqa / О нас и контакты"),
        BotCommand(command="help", description="Yordam / Помощь"),
    ]
    await bot.set_my_commands(commands)


async def handle_health_check(request: web.Request) -> web.Response:
    """HTTP Health Check endpoint for cloud platforms like Render.com."""
    return web.json_response({
        "status": "ok",
        "service": "SORO Shirinliklari Telegram Bot",
        "store": "SORO - SHIRINLIKLARI (Samarqand)",
        "channel": "@sorosamarkand",
    })


async def start_health_server(port: int) -> web.AppRunner:
    """
    Starts an aiohttp HTTP server on 0.0.0.0:port to satisfy Render.com Web Service
    health check requirements while aiogram runs long-polling concurrently.
    """
    app = web.Application()
    app.router.add_get("/", handle_health_check)
    app.router.add_get("/health", handle_health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=port)
    await site.start()
    logger.info("Render health check HTTP server listening on http://0.0.0.0:%d", port)
    return runner


async def main() -> None:
    """
    Initializes application dependencies and starts long-polling event loop.
    If PORT environment variable is set (e.g. Render.com), starts an HTTP health server.
    """
    config = load_config()
    db = await get_db_connection("data/shop.db")
    await init_db(db)

    bot, dp = build_app(config=config, db_connection=db)

    port_env = os.getenv("PORT")
    web_runner: Optional[web.AppRunner] = None
    if port_env:
        try:
            port = int(port_env)
            web_runner = await start_health_server(port)
        except Exception as e:
            logger.warning("Could not start HTTP health server on port %s: %s", port_env, e)

    try:
        await setup_bot_commands(bot)
        logger.info("Bot commands configured. Starting sweet shop bot polling...")
        await dp.start_polling(bot)
    finally:
        logger.info("Shutting down bot session and closing database...")
        if web_runner:
            try:
                await web_runner.cleanup()
            except Exception as e:
                logger.warning("Error cleaning up HTTP runner: %s", e)
        await bot.session.close()
        await db.close()
        logger.info("Bot successfully stopped.")


if __name__ == "__main__":
    asyncio.run(main())
