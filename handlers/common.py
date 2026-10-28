"""
Common navigation handlers: /start, language selection, about & contacts,
order history, and help for the sweet shop Telegram bot.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
import aiosqlite

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import CallbackQuery, Message

from database import crud
from database.db import get_db_connection
from keyboards.inline import language_kb
from keyboards.reply import main_menu_kb
from middlewares.i18n import get_text
from shop_config import Config, load_config

logger = logging.getLogger(__name__)

common_router = Router(name="common")

STATUS_NAMES: Dict[str, Dict[str, str]] = {
    "uz": {
        "new": "Yangi",
        "pending": "Kutilmoqda",
        "accepted": "Qabul qilingan",
        "confirmed": "Tasdiqlangan",
        "preparing": "Tayyorlanmoqda",
        "ready": "Tayyor",
        "delivering": "Yetkazilmoqda",
        "completed": "Yetkazildi (Yakunlangan)",
        "delivered": "Yetkazildi",
        "cancelled": "Bekor qilingan",
    },
    "ru": {
        "new": "Новый",
        "pending": "В ожидании",
        "accepted": "Принят",
        "confirmed": "Подтвержден",
        "preparing": "Готовится",
        "ready": "Готов",
        "delivering": "Доставляется",
        "completed": "Доставлен (Завершен)",
        "delivered": "Доставлен",
        "cancelled": "Отменен",
    },
}


async def _resolve_db(db: Optional[aiosqlite.Connection]) -> aiosqlite.Connection:
    """Returns active database connection, creating one if not supplied."""
    if db is not None:
        return db
    return await get_db_connection()


def _resolve_config(config: Optional[Config]) -> Config:
    """Returns shop configuration, loading environment defaults if not passed."""
    if config is not None:
        return config
    return load_config()


# ============================================================================
# 1. /start Handler
# ============================================================================

@common_router.message(CommandStart())
@common_router.message(Command("start"))
async def start_handler(
    message: Message,
    command: Optional[CommandObject] = None,
    db: Optional[aiosqlite.Connection] = None,
    config: Optional[Config] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Handles /start command:
    - Upserts user details in database.
    - If user has no language or wants language selection, prompts language_kb.
    - Otherwise greets the user and displays the main menu reply keyboard.
    """
    conn = await _resolve_db(db)
    cfg = _resolve_config(config)
    user = message.from_user
    if not user:
        return

    # Check if user already exists in DB before upserting
    existing_user = await crud.get_user(conn, user.id)
    is_new = existing_user is None or not existing_user.get("language")

    await crud.upsert_user(
        conn,
        telegram_id=user.id,
        full_name=user.full_name or "Mijoz",
        username=user.username,
    )

    # Check if deep-link arg requested language change
    cmd_args = (command.args or "").strip().lower() if command and getattr(command, "args", None) else ""
    wants_lang = cmd_args in ("lang", "language", "til")

    if is_new or wants_lang:
        prompt_text = _t("choose_language") if _t else get_text("choose_language", lang="uz")
        await message.answer(prompt_text, reply_markup=language_kb())
        return

    user_lang = existing_user.get("language") or lang or "uz"
    is_admin = user.id in cfg.admin_ids

    cart_items = await crud.get_cart(conn, user.id)
    cart_count = sum(item.get("quantity", 1) for item in cart_items)

    welcome_text = _t("welcome_msg", lang=user_lang) if _t else get_text("welcome_msg", lang=user_lang)
    menu_kb = main_menu_kb(lang=user_lang, cart_count=cart_count, is_admin=is_admin)

    await message.answer(welcome_text, reply_markup=menu_kb)


# ============================================================================
# 2. Language Selection Handlers
# ============================================================================

@common_router.message(Command("language"))
@common_router.message(Command("lang"))
@common_router.message(
    F.text.in_([
        get_text("btn_change_lang", "uz"),
        get_text("btn_change_lang", "ru"),
    ])
    | F.text.casefold().contains("tilni o'zgartirish")
    | F.text.casefold().contains("сменить язык")
)
async def change_language_handler(
    message: Message,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Prompts language selection inline keyboard."""
    prompt_text = _t("choose_language") if _t else get_text("choose_language", lang=lang)
    await message.answer(prompt_text, reply_markup=language_kb())


@common_router.callback_query(
    F.data.startswith("set_lang:") | F.data.in_(["lang_uz", "lang_ru"])
)
async def set_language_callback(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    config: Optional[Config] = None,
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Saves chosen language to user profile, confirms selection,
    and displays the main navigation menu in that language.
    """
    conn = await _resolve_db(db)
    cfg = _resolve_config(config)
    user = callback.from_user
    if not user:
        return

    cb_data = callback.data or ""
    chosen_lang = "ru" if "ru" in cb_data else "uz"

    await crud.set_user_language(conn, user.id, chosen_lang)

    confirm_key = f"lang_selected_{chosen_lang}"
    confirm_text = get_text(confirm_key, lang=chosen_lang)

    is_admin = user.id in cfg.admin_ids
    cart_items = await crud.get_cart(conn, user.id)
    cart_count = sum(item.get("quantity", 1) for item in cart_items)
    menu_kb = main_menu_kb(lang=chosen_lang, cart_count=cart_count, is_admin=is_admin)

    await callback.answer(confirm_text)

    if callback.message:
        welcome_text = get_text("welcome_msg", lang=chosen_lang)
        await callback.message.answer(
            f"{confirm_text}\n\n{welcome_text}",
            reply_markup=menu_kb,
        )


# ============================================================================
# 3. About & Contacts Handler
# ============================================================================

@common_router.message(Command("about"))
@common_router.message(Command("contact"))
@common_router.message(
    F.text.in_([
        get_text("btn_contact", "uz"),
        get_text("btn_contact", "ru"),
    ])
    | F.text.casefold().contains("aloqa")
    | F.text.casefold().contains("kontakt")
    | F.text.casefold().contains("контакт")
    | F.text.casefold().contains("haqida")
    | F.text.casefold().contains("о нас")
)
@common_router.callback_query(F.data.in_(["to_about", "to_contact"]))
async def about_handler(
    event: Optional[Message | CallbackQuery] = None,
    message: Optional[Message] = None,
    callback: Optional[CallbackQuery] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Displays sweet shop information, working hours, address, and phone contact."""
    ev = message or callback or event
    if ev is None:
        return
    text = _t("contact_info") if _t else get_text("contact_info", lang=lang)
    if isinstance(ev, CallbackQuery):
        await ev.answer()
        if ev.message:
            await ev.message.answer(text)
    else:
        await ev.answer(text)


# ============================================================================
# 4. My Orders (Order History) Handler
# ============================================================================

@common_router.message(Command("my_orders"))
@common_router.message(Command("orders"))
@common_router.message(
    F.text.in_([
        get_text("btn_my_orders", "uz"),
        get_text("btn_my_orders", "ru"),
    ])
    | F.text.casefold().contains("buyurtmalarim")
    | F.text.casefold().contains("мои заказы")
)
@common_router.callback_query(F.data.in_(["to_my_orders", "my_orders"]))
async def my_orders_handler(
    event: Optional[Message | CallbackQuery] = None,
    message: Optional[Message] = None,
    callback: Optional[CallbackQuery] = None,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Lists recent orders created by the user with their status and total."""
    ev = message or callback or event
    if ev is None:
        return
    conn = await _resolve_db(db)
    user = getattr(ev, "from_user", None)
    user_id = user.id if user else 0

    orders = await crud.get_user_orders(conn, user_id=user_id, limit=10)

    if not orders:
        empty_text = _t("my_orders_empty") if _t else get_text("my_orders_empty", lang=lang)
        if isinstance(ev, CallbackQuery):
            await ev.answer()
            if ev.message:
                await ev.message.answer(empty_text)
        else:
            await ev.answer(empty_text)
        return

    title = _t("my_orders_title") if _t else get_text("my_orders_title", lang=lang)
    lines: List[str] = [f"<b>{title}</b>\n"]

    lang_status_map = STATUS_NAMES.get(lang, STATUS_NAMES["uz"])
    for ord_row in orders:
        oid = ord_row.get("id")
        raw_status = (ord_row.get("status") or "new").strip().lower()
        status_label = lang_status_map.get(raw_status, raw_status)
        created_at = str(ord_row.get("created_at") or "")[:16]
        total_amount = f"{ord_row.get('total_amount', 0):,}".replace(",", " ")

        item_text = get_text(
            "order_tracking_format",
            lang=lang,
            order_id=oid,
            created_at=created_at,
            status_text=status_label,
            total_amount=total_amount,
        )
        lines.append(item_text)
        lines.append("────────────────")

    full_text = "\n".join(lines).strip()
    if isinstance(ev, CallbackQuery):
        await ev.answer()
        if ev.message:
            await ev.message.answer(full_text)
    else:
        await ev.answer(full_text)


# ============================================================================
# 5. Help Handler
# ============================================================================

@common_router.message(Command("help"))
async def help_handler(
    message: Message,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Displays user help guide."""
    text = _t("help_msg") if _t else get_text("help_msg", lang=lang)
    await message.answer(text)
