"""
Admin panel router handling main menu, dashboard navigation, and business statistics.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional
import aiosqlite

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import crud
from database.db import get_db_connection
from keyboards.admin_kb import admin_main_kb, order_admin_actions_kb
from keyboards.reply import main_menu_kb
from middlewares.i18n import get_text
from services.notifier import format_order_admin_text
from shop_config import Config, load_config

logger = logging.getLogger(__name__)

panel_router = Router(name="admin_panel")


async def _resolve_db(db: Optional[aiosqlite.Connection]) -> aiosqlite.Connection:
    if db is not None:
        return db
    return await get_db_connection()


@panel_router.message(Command("admin", "panel"))
@panel_router.message(
    F.text.in_([
        "👑 Admin boshqaruv paneli",
        "👑 Панель управления администратора",
        "👑 Admin panel",
        "Admin panel",
        "Admin paneli",
        "Admin",
        "/admin",
        "Панель администратора",
        "Админ панель",
        "Админ",
        get_text("admin_panel_title", "uz"),
        get_text("admin_panel_title", "ru"),
    ])
)
@panel_router.message(F.text.regexp(r"(?i)^(/admin|admin\s*panel|👑\s*admin.*|панель\s*админ.*)$"))
async def admin_panel_command(
    message: Message,
    state: Optional[FSMContext] = None,
    config: Optional[Config] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Verifies admin access, clears any FSM state, and displays persistent admin management keyboard."""
    if state is not None:
        await state.clear()

    cfg = config or load_config()
    user_id = message.from_user.id if message.from_user else 0

    if user_id not in cfg.admin_ids:
        reject_msg = "Sizda admin huquqi yo'q! Bu bo'lim faqat do'kon ma'murlari uchun mo'ljallangan."
        await message.answer(reject_msg)
        return

    title = _t("admin_panel_title", lang=lang) if _t else get_text("admin_panel_title", lang=lang)
    welcome_text = f"👑 <b>{title}</b>\n\nDo'kon boshqaruv bo'limiga xush kelibsiz. Kerakli amalni tanlang:"
    await message.answer(welcome_text, reply_markup=admin_main_kb())


@panel_router.message(
    F.text.in_([
        "📊 Statistika",
        "Statistika",
        "📊 Статистика",
        "Статистика",
    ])
)
@panel_router.message(Command("stats", "statistika"))
@panel_router.message(F.text.regexp(r"(?i)^(/stats|.*statistika|.*статистика)$"))
async def admin_statistics(
    message: Message,
    db: Optional[aiosqlite.Connection] = None,
    config: Optional[Config] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Displays business metrics: total orders, today's sales, and revenue."""
    cfg = config or load_config()
    user_id = message.from_user.id if message.from_user else 0

    if user_id not in cfg.admin_ids:
        await message.answer("Sizda admin huquqi yo'q!")
        return

    conn = await _resolve_db(db)
    stats = await crud.get_order_statistics(conn)

    total_orders = stats.get("total_orders", 0)
    total_revenue = stats.get("total_revenue", 0)
    today_orders = stats.get("today_orders", 0)
    today_revenue = stats.get("today_revenue", 0)
    total_users = stats.get("total_users", 0)

    stats_text = (
        "📊 <b>Do'kon statistikasi:</b>\n\n"
        f"📦 Jami buyurtmalar: <b>{total_orders} ta</b>\n"
        f"🗓 Bugungi buyurtmalar: <b>{today_orders} ta</b>\n"
        f"💰 Jami tushum: <b>{total_revenue:,} so'm</b>\n"
        f"💵 Bugungi tushum: <b>{today_revenue:,} so'm</b>\n"
        f"👥 Foydalanuvchilar: <b>{total_users} ta</b>"
    )

    await message.answer(stats_text, reply_markup=admin_main_kb())


@panel_router.message(
    F.text.in_([
        "📦 Yangi buyurtmalar",
        "📦 Buyurtmalar",
        "Buyurtmalar",
        "📦 Новые заказы",
        "📦 Заказы",
        "Заказы",
    ])
)
@panel_router.message(Command("orders", "buyurtmalar"))
@panel_router.message(F.text.regexp(r"(?i)^(/orders|.*buyurtma.*|.*заказ.*)$"))
async def admin_new_orders(
    message: Message,
    db: Optional[aiosqlite.Connection] = None,
    config: Optional[Config] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Lists recent active or pending orders with inline action buttons."""
    cfg = config or load_config()
    user_id = message.from_user.id if message.from_user else 0

    if user_id not in cfg.admin_ids:
        await message.answer("Sizda admin huquqi yo'q!")
        return

    conn = await _resolve_db(db)
    all_orders = await crud.get_all_orders(conn, limit=20)

    active_orders = [
        o for o in all_orders if o.get("status") in ("new", "confirmed", "preparing", "delivering")
    ]

    if not active_orders:
        await message.answer(
            "📦 Hozircha faol yoki yangi buyurtmalar yo'q. Barchasi yakunlangan! ✨",
            reply_markup=admin_main_kb(),
        )
        return

    for order in active_orders:
        order_items = await crud.get_order_items(conn, order["id"])
        text = format_order_admin_text(order, order_items)
        kb = order_admin_actions_kb(order_id=order["id"], current_status=order.get("status", "new"), lang=lang)

        if order.get("custom_image_id"):
            try:
                await message.answer_photo(
                    photo=order["custom_image_id"],
                    caption=text,
                    reply_markup=kb,
                )
                continue
            except Exception:
                pass

        await message.answer(text, reply_markup=kb)


@panel_router.message(Command("menu"))
@panel_router.message(
    F.text.in_([
        "⬅️ Bosh menyu",
        "Bosh menyu",
        "⬅️ Главное меню",
        "Главное меню",
        "Menyu",
        "Меню",
    ])
)
async def admin_back_to_main_menu(
    message: Message,
    state: Optional[FSMContext] = None,
    db: Optional[aiosqlite.Connection] = None,
    config: Optional[Config] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Returns admin from admin panel back to client main menu."""
    if state is not None:
        await state.clear()

    cfg = config or load_config()
    user_id = message.from_user.id if message.from_user else 0
    is_admin = user_id in cfg.admin_ids

    conn = await _resolve_db(db)
    cart_items = await crud.get_cart(conn, user_id)
    cart_count = sum(item.get("quantity", 1) for item in cart_items)

    main_text = _t("main_menu", lang=lang) if _t else get_text("main_menu", lang=lang)
    await message.answer(
        main_text,
        reply_markup=main_menu_kb(lang=lang, cart_count=cart_count, is_admin=is_admin),
    )
