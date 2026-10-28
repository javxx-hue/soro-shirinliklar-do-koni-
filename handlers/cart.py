"""
Shopping cart handlers for viewing cart contents, incrementing/decrementing item quantities,
deleting items, clearing the cart, and advancing to checkout.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, List, Optional
import aiosqlite

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from database import crud
from database.db import get_db_connection
from keyboards.inline import cart_kb, delivery_type_kb
from middlewares.i18n import get_text

cart_router = Router(name="cart")


async def _resolve_db(db: Optional[aiosqlite.Connection]) -> aiosqlite.Connection:
    """Returns active database connection, creating one if not supplied."""
    if db is not None:
        return db
    return await get_db_connection()


def _extract_product_id(data: str) -> Optional[int]:
    """Extracts integer product ID from callback query data using either '_' or ':' as delimiter."""
    parts = re.split(r"[_:]", data)
    try:
        return int(parts[-1])
    except (IndexError, ValueError):
        return None


def format_cart_receipt(
    cart_items: List[Dict[str, Any]],
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> str:
    """
    Renders an appetizing, cleanly formatted receipt text of cart items,
    unit prices, sub-totals, and total sum.
    """
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    if not cart_items:
        return tr("cart_empty")

    title = tr("cart_title")
    lines = [title, ""]

    total_sum = 0
    total_qty = 0

    for idx, item in enumerate(cart_items, start=1):
        name = item.get(f"name_{lang}") or item.get("name_uz") or item.get("name", "")
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        item_total = item.get("total_price", price * qty)

        total_sum += item_total
        total_qty += qty

        formatted_price = f"{price:,}".replace(",", " ")
        formatted_total = f"{item_total:,}".replace(",", " ")

        line = tr(
            "cart_item_format",
            index=idx,
            name=name,
            quantity=qty,
            price=formatted_price,
            total=formatted_total,
        )
        lines.append(line)

    formatted_total_amount = f"{total_sum:,}".replace(",", " ")
    summary = tr(
        "cart_summary",
        items_count=total_qty,
        total_amount=formatted_total_amount,
    )
    lines.append(summary)

    return "\n".join(lines)


# ============================================================================
# 1. View / Open Cart Handlers
# ============================================================================

@cart_router.message(Command("cart"))
@cart_router.message(
    F.text.regexp(r"(?i).*(?:savatcha|корзина).*")
    | F.text.in_([
        get_text("btn_cart", "uz"),
        get_text("btn_cart", "ru"),
    ])
)
async def open_cart_message(
    message: Message,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Displays cart contents or empty notice upon /cart command or menu reply button click."""
    conn = await _resolve_db(db)
    user_id = message.from_user.id if message.from_user else 0
    cart_items = await crud.get_cart(conn, user_id=user_id)

    if not cart_items:
        text = _t("cart_empty") if _t else get_text("cart_empty", lang)
        kb = cart_kb([], lang=lang)
    else:
        text = format_cart_receipt(cart_items, lang=lang, _t=_t)
        kb = cart_kb(cart_items, lang=lang)

    await message.answer(text, reply_markup=kb)


@cart_router.callback_query(
    F.data.in_(["view_cart", "to_cart", "open_cart", "cart"])
)
async def open_cart_callback(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Displays cart contents or empty notice upon inline button callback."""
    conn = await _resolve_db(db)
    user_id = callback.from_user.id if callback.from_user else 0
    cart_items = await crud.get_cart(conn, user_id=user_id)

    if not cart_items:
        text = _t("cart_empty") if _t else get_text("cart_empty", lang)
        kb = cart_kb([], lang=lang)
    else:
        text = format_cart_receipt(cart_items, lang=lang, _t=_t)
        kb = cart_kb(cart_items, lang=lang)

    await callback.answer()
    if callback.message:
        photo = getattr(callback.message, "photo", None)
        # In aiogram, photo is a list of PhotoSize objects when the message contains a photo
        if isinstance(photo, (list, tuple)):
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, reply_markup=kb)
        else:
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except (TelegramBadRequest, Exception):
                await callback.message.answer(text, reply_markup=kb)


# ============================================================================
# 2. Cart Item Quantity & Modification Handlers
# ============================================================================

@cart_router.callback_query(
    F.data.startswith("inc_cart_")
    | F.data.startswith("inc_cart:")
    | F.data.startswith("cart_plus:")
    | F.data.startswith("cart_plus_")
)
async def handle_cart_increment(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Increments product quantity in cart by 1, updating receipt and inline buttons."""
    conn = await _resolve_db(db)
    user_id = callback.from_user.id if callback.from_user else 0
    prod_id = _extract_product_id(callback.data or "")

    if prod_id is not None:
        await crud.add_to_cart(conn, user_id=user_id, product_id=prod_id, quantity=1)

    cart_items = await crud.get_cart(conn, user_id=user_id)
    text = format_cart_receipt(cart_items, lang=lang, _t=_t)
    kb = cart_kb(cart_items, lang=lang)

    await callback.answer()
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except (TelegramBadRequest, Exception):
            pass


@cart_router.callback_query(
    F.data.startswith("dec_cart_")
    | F.data.startswith("dec_cart:")
    | F.data.startswith("cart_minus:")
    | F.data.startswith("cart_minus_")
)
async def handle_cart_decrement(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Decrements product quantity in cart. If quantity reaches 0, removes the product."""
    conn = await _resolve_db(db)
    user_id = callback.from_user.id if callback.from_user else 0
    prod_id = _extract_product_id(callback.data or "")

    if prod_id is not None:
        cart_items = await crud.get_cart(conn, user_id=user_id)
        current_item = next((item for item in cart_items if item["product_id"] == prod_id), None)
        if current_item:
            current_qty = current_item["quantity"]
            if current_qty > 1:
                await crud.set_cart_item_quantity(conn, user_id=user_id, product_id=prod_id, quantity=current_qty - 1)
            else:
                await crud.remove_from_cart(conn, user_id=user_id, product_id=prod_id)

    updated_cart = await crud.get_cart(conn, user_id=user_id)
    if not updated_cart:
        text = _t("cart_empty") if _t else get_text("cart_empty", lang)
        kb = cart_kb([], lang=lang)
    else:
        text = format_cart_receipt(updated_cart, lang=lang, _t=_t)
        kb = cart_kb(updated_cart, lang=lang)

    await callback.answer()
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except (TelegramBadRequest, Exception):
            pass


@cart_router.callback_query(
    F.data.startswith("del_cart_")
    | F.data.startswith("del_cart:")
    | F.data.startswith("cart_del:")
    | F.data.startswith("cart_del_")
    | F.data.startswith("cart_delete:")
)
async def handle_cart_delete(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Removes a product completely from user's cart."""
    conn = await _resolve_db(db)
    user_id = callback.from_user.id if callback.from_user else 0
    prod_id = _extract_product_id(callback.data or "")

    if prod_id is not None:
        await crud.remove_from_cart(conn, user_id=user_id, product_id=prod_id)

    updated_cart = await crud.get_cart(conn, user_id=user_id)
    if not updated_cart:
        text = _t("cart_empty") if _t else get_text("cart_empty", lang)
        kb = cart_kb([], lang=lang)
    else:
        text = format_cart_receipt(updated_cart, lang=lang, _t=_t)
        kb = cart_kb(updated_cart, lang=lang)

    await callback.answer()
    if callback.message:
        try:
            await callback.message.edit_text(text, reply_markup=kb)
        except (TelegramBadRequest, Exception):
            pass


@cart_router.callback_query(
    F.data.in_(["clear_cart", "cart_clear"])
)
async def handle_clear_cart(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Clears all items in user's cart and displays empty cart view with alert."""
    conn = await _resolve_db(db)
    user_id = callback.from_user.id if callback.from_user else 0
    await crud.clear_cart(conn, user_id=user_id)

    alert_text = _t("cart_cleared") if _t else get_text("cart_cleared", lang)
    await callback.answer(alert_text, show_alert=True)

    empty_text = _t("cart_empty") if _t else get_text("cart_empty", lang)
    kb = cart_kb([], lang=lang)

    if callback.message:
        try:
            await callback.message.edit_text(empty_text, reply_markup=kb)
        except (TelegramBadRequest, Exception):
            pass


@cart_router.callback_query(
    F.data.in_(["checkout", "order_checkout", "cart_checkout"])
)
async def handle_cart_checkout(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    state: Optional[FSMContext] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Validates cart before advancing to checkout.
    If empty, alerts the user. If populated, prompts for delivery choice to begin order flow.
    """
    conn = await _resolve_db(db)
    user_id = callback.from_user.id if callback.from_user else 0
    cart_items = await crud.get_cart(conn, user_id=user_id)

    if not cart_items:
        alert_text = _t("cart_empty") if _t else get_text("cart_empty", lang)
        await callback.answer(alert_text, show_alert=True)
        return

    await callback.answer()
    prompt_text = _t("order_delivery_type_prompt") if _t else get_text("order_delivery_type_prompt", lang)
    kb = delivery_type_kb(lang=lang)

    if callback.message:
        try:
            await callback.message.edit_text(prompt_text, reply_markup=kb)
        except (TelegramBadRequest, Exception):
            await callback.message.answer(prompt_text, reply_markup=kb)


@cart_router.callback_query(F.data.startswith("cart_item:"))
async def handle_cart_item_click(callback: CallbackQuery) -> None:
    """Answers clicks on the cart item title button without changing state."""
    await callback.answer()
