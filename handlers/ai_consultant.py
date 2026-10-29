"""
AI Sweet Consultant ("Shirinlik Somelyesi") handlers for sweet shop bot.
Guides customers with grounded, delightful confectionery recommendations using Gemini AI.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Callable, Dict, List, Optional, Union
import aiosqlite

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import crud
from database.db import get_db_connection
from keyboards.inline import ai_consultant_result_kb, categories_kb
from keyboards.reply import cancel_kb, main_menu_kb
from middlewares.i18n import get_text
from services.gemini import get_sweet_recommendation
from shop_config import load_config

logger = logging.getLogger(__name__)

ai_consultant_router = Router(name="ai_consultant")


class AIConsultantFSM(StatesGroup):
    """FSM state for interactive dialog with the sweet sommelier AI consultant."""
    waiting_for_query = State()


# ============================================================================
# Helpers
# ============================================================================

async def _resolve_db(db: Optional[aiosqlite.Connection]) -> Optional[aiosqlite.Connection]:
    """Returns active database connection, opening a default connection if None."""
    if db is not None:
        return db
    try:
        return await get_db_connection()
    except Exception as e:
        logger.warning("Could not open default DB connection for AI consultant: %s", e)
        return None


def _is_cancel_text(text: Optional[str]) -> bool:
    """Checks whether user text corresponds to cancellation."""
    if not text:
        return False
    t = text.strip()
    return (
        t in [get_text("cancel_btn", "uz"), get_text("cancel_btn", "ru"), "/cancel"]
        or "bekor" in t.lower()
        or "отмена" in t.lower()
    )


# ============================================================================
# 1. Entry Handlers: Reply Button, Command, or Callback Query
# ============================================================================

@ai_consultant_router.message(Command("ai", "sommelier", "consultant"))
@ai_consultant_router.message(
    F.text.in_([
        get_text("btn_ai_consultant", "uz"),
        get_text("btn_ai_consultant", "ru"),
    ])
    | F.text.regexp(r"(?i).*(shirinlik.*ai|сомелье.*ai).*")
    | F.text.regexp(r"(?i).*(shirinlik.*maslahatchi|сладкий.*консультант|shirinlik.*somelye|сладкий.*сомелье).*")
    | F.text.casefold().contains("shirinlik maslahatchisi")
    | F.text.casefold().contains("сладкий консультант")
    | F.text.casefold().contains("somelye")
    | F.text.casefold().contains("сомелье")
)
async def open_ai_consultant_message(
    message: Message,
    state: Optional[FSMContext] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Activates AI sweet sommelier consultant via message command or menu reply button."""
    if state is not None:
        await state.set_state(AIConsultantFSM.waiting_for_query)

    intro_text = _t("ai_consultant_intro") if _t else get_text("ai_consultant_intro", lang)
    reply_kb = cancel_kb(lang=lang)
    await message.answer(intro_text, reply_markup=reply_kb)


@ai_consultant_router.callback_query(
    F.data.in_(["open_ai_consultant", "ai_consultant", "to_ai_consultant"])
)
async def open_ai_consultant_callback(
    callback: CallbackQuery,
    state: Optional[FSMContext] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Activates AI sweet sommelier consultant via inline callback button."""
    if state is not None:
        await state.set_state(AIConsultantFSM.waiting_for_query)

    intro_text = _t("ai_consultant_intro") if _t else get_text("ai_consultant_intro", lang)
    reply_kb = cancel_kb(lang=lang)

    await callback.answer()
    if callback.message:
        await callback.message.answer(intro_text, reply_markup=reply_kb)


# ============================================================================
# 2. Cancellation Handler
# ============================================================================

@ai_consultant_router.callback_query(
    AIConsultantFSM.waiting_for_query,
    F.data.in_(["cancel_ai_consultant", "ai_cancel", "order_cancel"]),
)
@ai_consultant_router.message(
    AIConsultantFSM.waiting_for_query,
    F.text.in_([
        get_text("cancel_btn", "uz"),
        get_text("cancel_btn", "ru"),
    ])
    | F.text.casefold().contains("bekor qilish")
    | F.text.casefold().contains("отмена"),
)
@ai_consultant_router.message(
    AIConsultantFSM.waiting_for_query,
    Command("cancel"),
)
async def cancel_ai_consultant(
    event: Union[CallbackQuery, Message],
    state: Optional[FSMContext] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Cancels AI consultant mode, clears FSM state, and restores main menu navigation."""
    if state is not None:
        await state.clear()

    cancel_text = _t("action_cancelled") if _t else get_text("action_cancelled", lang)
    menu_kb = main_menu_kb(lang=lang)

    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(cancel_text, reply_markup=menu_kb)
    else:
        await event.answer(cancel_text, reply_markup=menu_kb)


# ============================================================================
# 3. Query Processing Handler
# ============================================================================

@ai_consultant_router.message(AIConsultantFSM.waiting_for_query, F.text)
async def process_ai_query(
    message: Message,
    state: Optional[FSMContext] = None,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Processes customer's question in waiting_for_query state.
    Shows typing status, queries available products, gets grounded recommendation,
    and replies with action buttons [ Vitrinani ko'rish ] & [ Bosh menyu ].
    """
    if _is_cancel_text(message.text):
        if state is not None:
            await state.clear()
        cancel_text = _t("action_cancelled") if _t else get_text("action_cancelled", lang)
        await message.answer(cancel_text, reply_markup=main_menu_kb(lang=lang))
        return

    # Indicate typing action
    if getattr(message, "bot", None) and getattr(message, "chat", None):
        try:
            await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
        except Exception as e:
            logger.debug("Could not send chat action typing: %s", e)

    # Fetch available products strictly from DB
    conn = await _resolve_db(db)
    available_products: List[Dict[str, Any]] = []
    if conn:
        try:
            available_products = await crud.get_all_available_products(conn)
        except Exception as e:
            logger.warning("Could not load products for AI consultant: %s", e)

    # Resolve Gemini configuration
    cfg = load_config()
    api_key = cfg.gemini_api_key
    model_name = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

    # Generate grounded recommendation
    recommendation = await get_sweet_recommendation(
        user_prompt=message.text or "",
        available_products=available_products,
        user_lang=lang,
        api_key=api_key,
        model_name=model_name,
    )

    # Send response with inline navigation keyboard
    result_kb = ai_consultant_result_kb(lang=lang)
    await message.answer(recommendation, reply_markup=result_kb)


# ============================================================================
# 4. Result Keyboard Callback Handlers
# ============================================================================

@ai_consultant_router.callback_query(
    AIConsultantFSM.waiting_for_query,
    F.data.in_(["open_catalog", "to_catalog"]),
)
async def handle_ai_open_catalog(
    callback: CallbackQuery,
    state: Optional[FSMContext] = None,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Navigates user from AI recommendation to the sweet shop catalogue."""
    if state is not None:
        await state.clear()

    conn = await _resolve_db(db)
    categories = []
    if conn:
        try:
            categories = await crud.get_categories(conn, only_active=True)
        except Exception as e:
            logger.warning("Could not fetch categories: %s", e)

    prompt_text = _t("select_category") if _t else get_text("select_category", lang)
    kb = categories_kb(categories=categories, lang=lang)

    await callback.answer()
    if callback.message:
        await callback.message.answer(prompt_text, reply_markup=kb)


@ai_consultant_router.callback_query(
    AIConsultantFSM.waiting_for_query,
    F.data == "to_main_menu",
)
async def handle_ai_to_main_menu(
    callback: CallbackQuery,
    state: Optional[FSMContext] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Returns user from AI recommendation back to main menu."""
    if state is not None:
        await state.clear()

    main_text = _t("main_menu") if _t else get_text("main_menu", lang)
    menu_kb = main_menu_kb(lang=lang)

    await callback.answer()
    if callback.message:
        await callback.message.answer(main_text, reply_markup=menu_kb)
