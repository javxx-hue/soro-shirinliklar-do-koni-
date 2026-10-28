"""
Admin handlers for managing product stop-lists and immediate stock availability toggling.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional
import aiosqlite

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from database import crud
from database.db import get_db_connection
from shop_config import Config, load_config

logger = logging.getLogger(__name__)

products_router = Router(name="admin_products")


async def _resolve_db(db: Optional[aiosqlite.Connection]) -> aiosqlite.Connection:
    if db is not None:
        return db
    return await get_db_connection()


def build_stoplist_kb(products: List[Dict[str, Any]], lang: str = "uz") -> InlineKeyboardMarkup:
    """Creates inline keyboard showing current availability and toggle buttons for all products."""
    rows: List[List[InlineKeyboardButton]] = []
    for p in products:
        name = p.get("name_uz") or p.get("name_ru") or "Mahsulot"
        status_tag = "[✅ Sotuvda bor]" if p.get("is_available", 1) else "[⛔️ Tugadi (Stop-list)]"
        btn_text = f"{name} {status_tag}"
        rows.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"toggle_prod_{p['id']}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@products_router.message(
    F.text.in_(["🍰 Mahsulotlar", "🧁 Mahsulotlar (Stop-list)", "Mahsulotlar", "Stop-list"]) | Command("stoplist")
)
async def admin_products_stoplist(
    message: Message,
    db: Optional[aiosqlite.Connection] = None,
    config: Optional[Config] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Displays product list with real-time toggle buttons to activate or disable sales."""
    cfg = config or load_config()
    user_id = message.from_user.id if message.from_user else 0

    if user_id not in cfg.admin_ids:
        await message.answer("Sizda admin huquqi yo'q!")
        return

    conn = await _resolve_db(db)
    products = await crud.get_all_products(conn)

    if not products:
        await message.answer("Hozircha tizimda birorta ham mahsulot mavjud emas.")
        return

    kb = build_stoplist_kb(products, lang=lang)
    info_text = (
        "🧁 <b>Mahsulotlar holati (Stop-list):</b>\n\n"
        "Mahsulot tugagan bo'lsa yoki sotuvga qaytgan bo'lsa, ustiga bosing. "
        "U bir zumda mijozlar katalogida yangilanadi:"
    )
    await message.answer(info_text, reply_markup=kb)


@products_router.callback_query(F.data.startswith("toggle_prod_"))
async def handle_toggle_product(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    config: Optional[Config] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Toggles product availability between 1 (available) and 0 (stop-list)."""
    cfg = config or load_config()
    user_id = callback.from_user.id if callback.from_user else 0

    if user_id not in cfg.admin_ids:
        await callback.answer("Ruxsat berilmagan! Siz admin emassiz.", show_alert=True)
        return

    data = callback.data or ""
    try:
        prod_id = int(data.replace("toggle_prod_", ""))
    except ValueError:
        await callback.answer("Noto'g'ri mahsulot identifikatori.")
        return

    conn = await _resolve_db(db)
    prod = await crud.get_product(conn, prod_id)
    if not prod:
        await callback.answer("Mahsulot topilmadi!", show_alert=True)
        return

    current_avail = prod.get("is_available", 1)
    new_avail = 0 if current_avail else 1
    await crud.set_product_availability(conn, prod_id, new_avail)

    # Re-render keyboard with updated availability
    products = await crud.get_all_products(conn)
    updated_kb = build_stoplist_kb(products, lang=lang)

    if callback.message:
        try:
            await callback.message.edit_reply_markup(reply_markup=updated_kb)
        except Exception as exc:
            logger.debug("Could not edit reply markup for products stoplist: %s", exc)

    status_str = "Sotuvda mavjud ✅" if new_avail else "Stop-listga kiritildi ⛔️"
    prod_name = prod.get("name_uz") or prod.get("name_ru") or "Mahsulot"
    await callback.answer(f"{prod_name}: {status_str}")
