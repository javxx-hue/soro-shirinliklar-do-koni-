"""
Admin order processing handlers for lifecycle progression and customer alerts.
"""
from __future__ import annotations

import logging
from typing import Callable, Optional
import aiosqlite

from aiogram import F, Router
from aiogram.types import CallbackQuery

from database import crud
from database.db import get_db_connection
from keyboards.admin_kb import order_admin_actions_kb
from services.notifier import notify_customer_status_change
from shop_config import Config, load_config

logger = logging.getLogger(__name__)

orders_router = Router(name="admin_orders")


async def _resolve_db(db: Optional[aiosqlite.Connection]) -> aiosqlite.Connection:
    if db is not None:
        return db
    return await get_db_connection()


@orders_router.callback_query(
    F.data.startswith("adm_") | F.data.startswith("admin_order:")
)
async def handle_admin_order_callback(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    config: Optional[Config] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Handles order lifecycle transition callbacks from administrators:
    - adm_confirm_<id> / admin_order:preparing:<id> -> 'confirmed'
    - adm_ready_<id> / admin_order:ready:<id> -> 'preparing'
    - adm_dispatch_<id> / admin_order:delivering:<id> -> 'delivering'
    - adm_complete_<id> / admin_order:delivered:<id> -> 'completed'
    - adm_cancel_<id> / admin_order:cancel:<id> -> 'cancelled'
    """
    cfg = config or load_config()
    user_id = callback.from_user.id if callback.from_user else 0

    if user_id not in cfg.admin_ids:
        await callback.answer("Ruxsat berilmagan! Siz admin emassiz.", show_alert=True)
        return

    data = callback.data or ""
    order_id: Optional[int] = None
    new_status: Optional[str] = None

    if data.startswith("adm_"):
        parts = data.split("_")
        if len(parts) >= 3:
            action = parts[1]
            try:
                order_id = int(parts[2])
            except ValueError:
                pass

            if action == "confirm":
                new_status = "confirmed"
            elif action == "ready":
                new_status = "preparing"
            elif action == "dispatch":
                new_status = "delivering"
            elif action == "complete":
                new_status = "completed"
            elif action == "cancel":
                new_status = "cancelled"

    elif data.startswith("admin_order:"):
        parts = data.split(":")
        if len(parts) >= 3:
            action = parts[1]
            try:
                order_id = int(parts[2])
            except ValueError:
                pass

            if action in ("preparing", "confirm"):
                new_status = "confirmed"
            elif action == "ready":
                new_status = "preparing"
            elif action == "delivering":
                new_status = "delivering"
            elif action in ("delivered", "complete"):
                new_status = "completed"
            elif action == "cancel":
                new_status = "cancelled"

    if order_id is None or new_status is None:
        await callback.answer("Noto'g'ri buyurtma ma'lumoti.")
        return

    conn = await _resolve_db(db)
    order = await crud.get_order(conn, order_id)
    if not order:
        await callback.answer(f"Buyurtma #{order_id} topilmadi!", show_alert=True)
        return

    # Update database status
    await crud.update_order_status(conn, order_id, new_status)

    # Determine customer user_id and preferred language
    customer_id = order.get("user_id", 0)
    customer_lang = "uz"
    if customer_id:
        user = await crud.get_user(conn, customer_id)
        if user:
            customer_lang = user.get("language") or "uz"

    # Send live localized status alert to customer
    if callback.bot and customer_id:
        await notify_customer_status_change(
            bot=callback.bot,
            user_id=customer_id,
            order_id=order_id,
            new_status=new_status,
            lang=customer_lang,
            cancel_reason="",
        )

    # Update admin inline action keyboard
    if callback.message:
        try:
            if new_status in ("completed", "cancelled"):
                await callback.message.edit_reply_markup(reply_markup=None)
            else:
                next_kb = order_admin_actions_kb(order_id, current_status=new_status, lang=lang)
                await callback.message.edit_reply_markup(reply_markup=next_kb)
        except Exception as exc:
            logger.debug("Could not edit reply markup for order #%s: %s", order_id, exc)

    status_labels = {
        "confirmed": "Tasdiqlandi",
        "preparing": "Tayyorlanmoqda",
        "delivering": "Yetkazilmoqda",
        "completed": "Yetkazildi (Yakunlandi)",
        "cancelled": "Bekor qilindi",
    }
    label = status_labels.get(new_status, new_status)
    await callback.answer(f"Buyurtma #{order_id}: {label}")
