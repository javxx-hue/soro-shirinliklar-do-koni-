"""
Keyboard generators for administrator panel and order processing workflows.
"""
from __future__ import annotations

from typing import List
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from middlewares.i18n import get_text


def admin_main_kb() -> ReplyKeyboardMarkup:
    """
    Main persistent reply keyboard for admin management actions.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Statistika"),
                KeyboardButton(text="📦 Buyurtmalar"),
            ],
            [
                KeyboardButton(text="🍰 Mahsulotlar"),
                KeyboardButton(text="⬅️ Bosh menyu"),
            ],
        ],
        resize_keyboard=True,
    )


def order_admin_actions_kb(
    order_id: int,
    current_status: str = "new",
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """
    Context-aware action buttons for managing an order's lifecycle.
    Transitions status forward from new -> preparing -> ready -> delivering -> delivered,
    or cancels at any stage.
    """
    rows: List[List[InlineKeyboardButton]] = []

    btn_accept = get_text("admin_btn_accept", lang)
    btn_ready = get_text("admin_btn_ready", lang)
    btn_delivering = get_text("admin_btn_send_delivery", lang)
    btn_delivered = get_text("admin_btn_complete", lang)
    btn_cancel = get_text("admin_btn_cancel", lang)

    status = (current_status or "").lower()

    if status == "new":
        rows.append([
            InlineKeyboardButton(
                text=btn_accept,
                callback_data=f"admin_order:preparing:{order_id}",
            )
        ])
        rows.append([
            InlineKeyboardButton(
                text=btn_cancel,
                callback_data=f"admin_order:cancel:{order_id}",
            )
        ])
    elif status == "preparing":
        rows.append([
            InlineKeyboardButton(
                text=btn_ready,
                callback_data=f"admin_order:ready:{order_id}",
            )
        ])
        rows.append([
            InlineKeyboardButton(
                text=btn_cancel,
                callback_data=f"admin_order:cancel:{order_id}",
            )
        ])
    elif status == "ready":
        rows.append([
            InlineKeyboardButton(
                text=btn_delivering,
                callback_data=f"admin_order:delivering:{order_id}",
            )
        ])
        rows.append([
            InlineKeyboardButton(
                text=btn_cancel,
                callback_data=f"admin_order:cancel:{order_id}",
            )
        ])
    elif status == "delivering":
        rows.append([
            InlineKeyboardButton(
                text=btn_delivered,
                callback_data=f"admin_order:delivered:{order_id}",
            )
        ])
        rows.append([
            InlineKeyboardButton(
                text=btn_cancel,
                callback_data=f"admin_order:cancel:{order_id}",
            )
        ])
    elif status in ("delivered", "completed", "cancelled"):
        # Terminal states have no actionable transition buttons
        pass
    else:  # "all" or unhandled status: expose all lifecycle options
        rows.append([
            InlineKeyboardButton(
                text=btn_accept,
                callback_data=f"admin_order:preparing:{order_id}",
            ),
            InlineKeyboardButton(
                text=btn_ready,
                callback_data=f"admin_order:ready:{order_id}",
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                text=btn_delivering,
                callback_data=f"admin_order:delivering:{order_id}",
            ),
            InlineKeyboardButton(
                text=btn_delivered,
                callback_data=f"admin_order:delivered:{order_id}",
            ),
        ])
        rows.append([
            InlineKeyboardButton(
                text=btn_cancel,
                callback_data=f"admin_order:cancel:{order_id}",
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)
