"""Telegram update routers and handlers."""
from __future__ import annotations

import logging
from typing import List

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import BusinessConnection, Message

from assistant.service import Assistant

logger = logging.getLogger(__name__)

ALLOWED_UPDATES: List[str] = ["message", "business_connection", "business_message"]

OTHER_USER_START_TEXT = (
    "Salom! Bu shaxsiy yordamchi bot bo'lib, faqat egasi uchun ishlaydi. "
    "Bu yerda suhbatlashib bo'lmaydi. Iltimos, egasiga to'g'ridan-to'g'ri yozing."
)


def build_router(assistant: Assistant) -> Router:
    """Build and configure the Aiogram Router."""
    router = Router()

    @router.business_connection()
    async def handle_business_connection(connection: BusinessConnection) -> None:
        assistant.on_business_connection(connection)

    @router.business_message()
    async def handle_business_message(message: Message, bot: Bot) -> None:
        await assistant.on_business_message(bot, message)

    @router.message(Command("start"))
    async def handle_start(message: Message) -> None:
        if not message.from_user:
            return
        if message.from_user.id == assistant.settings.owner_id:
            await message.answer(assistant.start_text())
        else:
            await message.answer(OTHER_USER_START_TEXT)

    @router.message(Command("pause"))
    async def handle_pause(message: Message) -> None:
        if not message.from_user or message.from_user.id != assistant.settings.owner_id:
            return
        assistant.pause()
        await message.answer("⏸ Bot faoliyati vaqtincha to'xtatildi (pauza). Davom ettirish uchun /resume bosing.")

    @router.message(Command("resume"))
    async def handle_resume(message: Message) -> None:
        if not message.from_user or message.from_user.id != assistant.settings.owner_id:
            return
        assistant.resume()
        await message.answer("▶️ Bot faoliyati qayta tiklandi.")

    @router.message(Command("status"))
    async def handle_status(message: Message) -> None:
        if not message.from_user or message.from_user.id != assistant.settings.owner_id:
            return
        await message.answer(assistant.status_text())

    @router.message()
    async def handle_other_messages(message: Message) -> None:
        # Silently ignore non-command messages sent directly to the bot by anyone
        pass

    return router
