"""Main entrypoint for the Telegram Business Assistant bot using Gemini."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramUnauthorizedError

from assistant.config import (
    SETTING_KEYS,
    ConfigError,
    Settings,
    env_file_warning,
    load_settings,
)
from assistant.gemini_client import GeminiClient
from assistant.handlers import ALLOWED_UPDATES, build_router
from assistant.language import detect_language
from assistant.prompts import build_system_prompt, build_user_prompt
from assistant.service import build_assistant, make_gemini_client, read_profile
from assistant.store import RuntimeState, ensure_private_dir

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bot")


def settings_from_process_env(require_telegram: bool = True) -> Settings:
    """Read configuration from os.environ and clear keys in a finally block."""
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


async def run_check_gemini(client: GeminiClient) -> int:
    """Run diagnostic checks on Gemini API connectivity and auth."""
    print("Inspecting Google Gemini API connection...")
    info = await client.inspect()
    print(json.dumps(info, indent=2))

    if info.get("status") != "ok":
        print(f"FAILED: Gemini check failed: {info.get('error')}", file=sys.stderr)
        return 1

    print("\nSUCCESS: Gemini API check passed!")
    print(f"Authentication mode: {info.get('auth')}")
    print(f"Active model: {info.get('model')}")
    return 0


async def run_try_message(settings: Settings, text: str) -> int:
    """Simulate a single incoming message and print the Gemini response."""
    client = make_gemini_client(settings)
    lang = detect_language(text)
    profile = read_profile(settings.profile_path)
    sys_prompt = build_system_prompt(profile, datetime.now())
    history = [{"role": "other", "name": "Friend", "text": text, "lang": lang, "ts": 0}]
    user_prompt = build_user_prompt(history, lang)

    print(f"Incoming: {text}")
    print(f"Detected language: {lang or 'unknown'}")
    print(f"Model: {settings.gemini_model}")
    print("Generating reply via Gemini...")
    try:
        reply = await client.run(user_prompt, sys_prompt)
        print(f"\nAssistant Reply:\n{reply}\n")
        return 0
    except Exception as e:
        print(f"FAILED: Error generating reply: {e}", file=sys.stderr)
        return 1


async def start_healthcheck():
    """Start lightweight HTTP server if PORT is provided by hosting (Render/Heroku)."""
    port_str = os.environ.get("PORT")
    if not port_str:
        return
    try:
        port = int(port_str)
        from aiohttp import web
        app = web.Application()
        app.router.add_get("/", lambda req: web.Response(text="OK"))
        app.router.add_get("/health", lambda req: web.Response(text="OK"))
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Healthcheck HTTP server running on port {port}")
    except Exception as e:
        logger.warning(f"Could not start healthcheck server on port {port_str}: {e}")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Telegram Business Personal Assistant with Gemini")
    parser.add_argument(
        "--settings-from-env",
        action="store_true",
        help="Load settings from process environment variables and wipe them afterwards (container mode)",
    )
    parser.add_argument(
        "--check-gemini",
        "--check-claude",
        action="store_true",
        dest="check_gemini",
        help="Check Gemini API connectivity and model settings without starting Telegram",
    )
    parser.add_argument(
        "--try",
        dest="try_text",
        type=str,
        help="Test a single message reply without starting Telegram",
    )
    args = parser.parse_args()

    require_telegram = not (args.check_gemini or args.try_text)

    try:
        if args.settings_from_env:
            settings = settings_from_process_env(require_telegram=require_telegram)
        else:
            env_file = Path(".env")
            warning = env_file_warning(env_file)
            if warning:
                logger.warning(warning)
            settings = load_settings(env_file, require_telegram=require_telegram)
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 2

    ensure_private_dir(settings.data_dir)

    if args.check_gemini:
        client = make_gemini_client(settings)
        return await run_check_gemini(client)

    if args.try_text:
        return await run_try_message(settings, args.try_text)

    # Validate profile.md has content
    profile_text = read_profile(settings.profile_path)
    if not profile_text or profile_text.count("\n") < 5:
        logger.warning(
            f"Warning: '{settings.profile_path}' appears empty or incomplete. "
            "Please fill it in so your assistant knows how to respond on your behalf."
        )

    # Runtime state check
    state = RuntimeState(settings.data_dir / "state.json")
    if state.is_paused():
        logger.warning("Bot is starting in PAUSED state. Send /resume in Telegram to unpause.")

    bot = Bot(token=settings.bot_token)
    try:
        me = await bot.get_me()
    except TelegramUnauthorizedError as e:
        print(f"Telegram unauthorized: {e}. Check your TELEGRAM_BOT_TOKEN.", file=sys.stderr)
        await bot.session.close()
        return 2
    except Exception as e:
        print(f"Failed to connect to Telegram: {e}", file=sys.stderr)
        await bot.session.close()
        return 2

    mode_label = "AUTO-SEND (replies will be sent to Telegram chats!)" if settings.auto_send else "PREVIEW (replies only logged, not sent)"
    logger.info(f"Bot @{me.username} is running!")
    logger.info(f"Mode: {mode_label}")
    logger.info(f"Gemini model: {settings.gemini_model}")
    logger.info(f"Gemini auth: {settings.gemini_auth_mode}")

    assistant = build_assistant(settings)
    await start_healthcheck()
    dp = Dispatcher()
    router = build_router(assistant)
    dp.include_router(router)

    try:
        await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)
    finally:
        await bot.session.close()

    return 0


if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        sys.exit(0)
