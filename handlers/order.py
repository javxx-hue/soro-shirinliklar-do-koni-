"""
End-to-end Order Placement FSM flow handlers for the sweet shop Telegram bot.
Manages time selection (now vs scheduled), delivery method (courier vs pickup),
location & delivery cost calculation, contact collection, custom cake notes,
payment method selection, receipt generation, and database order creation.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Union
import aiosqlite

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.exceptions import TelegramBadRequest

from shop_config import Config, load_config
from database import crud
from database.db import get_db_connection
from keyboards.inline import (
    delivery_type_kb,
    order_confirm_kb,
    order_time_kb,
    payment_methods_kb,
)
from keyboards.reply import (
    cancel_kb,
    location_request_kb,
    main_menu_kb,
    phone_request_kb,
    skip_or_cancel_kb,
)
from middlewares.i18n import get_text
from services.delivery import (
    calculate_delivery_cost,
    calculate_distance_km,
    is_store_open,
)

logger = logging.getLogger(__name__)

order_router = Router(name="order")


class OrderFSM(StatesGroup):
    """FSM states representing the sequential steps of checkout and order placement."""
    waiting_for_time = State()
    waiting_for_preorder_time = State()
    waiting_for_delivery_type = State()
    waiting_for_location = State()
    waiting_for_phone = State()
    waiting_for_note = State()
    waiting_for_payment = State()
    confirmation = State()


# ============================================================================
# Helpers
# ============================================================================

async def _resolve_db(db: Optional[aiosqlite.Connection]) -> aiosqlite.Connection:
    """Returns active database connection, opening a new one if not passed."""
    if db is not None:
        return db
    return await get_db_connection()


def _resolve_config(config: Optional[Config]) -> Config:
    """Returns shop config, loading environment defaults if not passed."""
    if config is not None:
        return config
    return load_config()


def _is_cancel_text(text: Optional[str], lang: str = "uz") -> bool:
    """Checks whether text corresponds to cancellation."""
    if not text:
        return False
    t = text.strip()
    return (
        t in [get_text("cancel_btn", "uz"), get_text("cancel_btn", "ru"), "/cancel"]
        or "bekor" in t.lower()
        or "отмена" in t.lower()
    )


def format_order_summary(
    cart_items: List[Dict[str, Any]],
    cart_total: int,
    delivery_cost: int,
    address: str,
    target_time: str,
    phone: str,
    custom_note: Optional[str],
    payment_type: str,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> str:
    """Compiles complete order summary receipt matching the order_confirm_summary template."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    grand_total = cart_total + delivery_cost

    item_lines: List[str] = []
    for idx, item in enumerate(cart_items, start=1):
        name = item.get(f"name_{lang}") or item.get("name_uz") or item.get("name", "")
        qty = item.get("quantity", 1)
        price = item.get("price", 0)
        tot = item.get("total_price", price * qty)
        formatted_price = f"{price:,}".replace(",", " ")
        formatted_total = f"{tot:,}".replace(",", " ")
        item_lines.append(f"{idx}. {name} — {qty} dona x {formatted_price} = {formatted_total} so'm")

    items_text = "\n".join(item_lines)

    pay_names = {
        "click": tr("btn_pay_click"),
        "payme": tr("btn_pay_payme"),
        "cash": tr("btn_pay_cash"),
        "card": "💳 Karta orqali" if lang == "uz" else "💳 Картой",
    }
    payment_label = pay_names.get(payment_type, payment_type.title())

    note_text = custom_note if custom_note else ("Yo'q" if lang == "uz" else "Нет")

    return tr(
        "order_confirm_summary",
        items_text=items_text,
        cart_total=f"{cart_total:,}".replace(",", " "),
        delivery_cost=f"{delivery_cost:,}".replace(",", " "),
        grand_total=f"{grand_total:,}".replace(",", " "),
        address=address or "",
        target_time=target_time or "",
        phone=phone or "",
        custom_note=note_text,
        payment_type=payment_label,
    )


# ============================================================================
# Order Cancellation Handler
# ============================================================================

@order_router.callback_query(
    F.data.in_(["order_cancel", "cancel_order", "order_confirm:cancel"])
)
@order_router.message(
    F.text.in_([
        get_text("cancel_btn", "uz"),
        get_text("cancel_btn", "ru"),
    ])
    | Command("cancel")
    | F.text.casefold().contains("bekor qilish")
    | F.text.casefold().contains("отмена")
)
async def handle_order_cancellation(
    event: Union[CallbackQuery, Message],
    state: Optional[FSMContext] = None,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Cancels active order placement, clears FSM state, and restores main menu."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    conn = await _resolve_db(db)
    user_id = event.from_user.id if event.from_user else 0

    if state is not None:
        await state.clear()

    cart_items = await crud.get_cart(conn, user_id=user_id)
    cart_count = sum(item.get("quantity", 1) for item in cart_items)
    kb = main_menu_kb(lang=lang, cart_count=cart_count)
    cancel_text = tr("action_cancelled")

    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(cancel_text, reply_markup=kb)
    else:
        await event.answer(cancel_text, reply_markup=kb)


# ============================================================================
# Start Checkout Flow
# ============================================================================

@order_router.callback_query(
    F.data.in_(["checkout", "order_checkout", "cart_checkout", "start_order"])
)
@order_router.message(
    F.text.in_([
        get_text("btn_checkout", "uz"),
        get_text("btn_checkout", "ru"),
    ])
    | Command("checkout")
    | Command("order")
)
async def start_order_checkout(
    event: Union[CallbackQuery, Message],
    db: Optional[aiosqlite.Connection] = None,
    state: Optional[FSMContext] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
    config: Optional[Config] = None,
) -> None:
    """
    Validates user cart. If empty, alerts user and halts.
    If populated, enters OrderFSM.waiting_for_time and prompts for delivery timing.
    """
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    conn = await _resolve_db(db)
    cfg = _resolve_config(config)
    user_id = event.from_user.id if event.from_user else 0

    cart_items = await crud.get_cart(conn, user_id=user_id)
    if not cart_items:
        empty_text = tr("cart_empty")
        if isinstance(event, CallbackQuery):
            await event.answer(empty_text, show_alert=True)
        else:
            await event.answer(empty_text)
        return

    cart_total = sum(item.get("total_price", item.get("price", 0) * item.get("quantity", 1)) for item in cart_items)

    if state is not None:
        await state.set_state(OrderFSM.waiting_for_time)
        await state.update_data(cart_total=cart_total, user_id=user_id)

    store_open = is_store_open(cfg)
    kb = order_time_kb(lang=lang, store_open=store_open)
    prompt_text = tr("order_time_prompt")

    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            try:
                await event.message.edit_text(prompt_text, reply_markup=kb)
            except (TelegramBadRequest, Exception):
                await event.message.answer(prompt_text, reply_markup=kb)
    else:
        await event.answer(prompt_text, reply_markup=kb)


# ============================================================================
# Step 1: Time Selection Handlers
# ============================================================================

@order_router.callback_query(
    OrderFSM.waiting_for_time,
    F.data.startswith("order_time:") | F.data.in_(["time_now", "time_preorder", "time_scheduled"]),
)
async def handle_order_time(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
    config: Optional[Config] = None,
) -> None:
    """Processes instant ('now') vs scheduled ('scheduled') delivery time selection."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    data = callback.data or ""
    await callback.answer()

    if data in ("order_time:now", "time_now"):
        await state.update_data(target_time="hozir")
        await state.set_state(OrderFSM.waiting_for_delivery_type)

        text = tr("order_delivery_type_prompt")
        kb = delivery_type_kb(lang=lang)

        if callback.message:
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except (TelegramBadRequest, Exception):
                await callback.message.answer(text, reply_markup=kb)
    else:
        await state.set_state(OrderFSM.waiting_for_preorder_time)
        text = tr("order_time_input_prompt")
        kb = cancel_kb(lang=lang)

        if callback.message:
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except (TelegramBadRequest, Exception):
                await callback.message.answer(text, reply_markup=kb)


@order_router.message(OrderFSM.waiting_for_preorder_time)
async def handle_preorder_time_input(
    message: Message,
    state: FSMContext,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Stores custom scheduled preorder date and time string, then prompts for delivery type."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    if _is_cancel_text(message.text, lang=lang):
        await handle_order_cancellation(message, state=state, lang=lang, _t=_t)
        return

    target_time = (message.text or "").strip()
    await state.update_data(target_time=target_time)
    await state.set_state(OrderFSM.waiting_for_delivery_type)

    text = tr("order_delivery_type_prompt")
    kb = delivery_type_kb(lang=lang)
    await message.answer(text, reply_markup=kb)


# ============================================================================
# Step 2: Delivery Type Handlers
# ============================================================================

@order_router.callback_query(
    OrderFSM.waiting_for_delivery_type,
    F.data.startswith("delivery_type:") | F.data.in_(["delivery_courier", "delivery_pickup", "delivery", "pickup"]),
)
async def handle_delivery_type(
    callback: CallbackQuery,
    state: FSMContext,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Handles courier delivery (prompts for location) vs self-pickup (skips location, cost=0, prompts for phone).
    """
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    data = callback.data or ""
    await callback.answer()

    if "pickup" in data:
        # Pickup chosen: delivery cost is 0, distance is 0, fixed address
        await state.update_data(
            delivery_type="pickup",
            delivery_cost=0,
            distance_km=0,
            address="Do'kondan olib ketish",
            latitude=None,
            longitude=None,
        )
        await state.set_state(OrderFSM.waiting_for_phone)
        text = tr("order_phone_prompt")
        kb = phone_request_kb(lang=lang)
        if callback.message:
            await callback.message.answer(text, reply_markup=kb)
    else:
        await state.update_data(delivery_type="delivery")
        await state.set_state(OrderFSM.waiting_for_location)
        text = tr("order_location_prompt")
        kb = location_request_kb(lang=lang)
        if callback.message:
            await callback.message.answer(text, reply_markup=kb)


# ============================================================================
# Step 3: Location Handlers
# ============================================================================

@order_router.message(OrderFSM.waiting_for_location, F.location | F.text)
async def handle_location_input(
    message: Message,
    state: FSMContext,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
    config: Optional[Config] = None,
) -> None:
    """
    Accepts GPS location or text address.
    Calculates distance and delivery cost, warns or congratulates for free delivery,
    and advances to waiting_for_phone.
    """
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    if _is_cancel_text(message.text, lang=lang):
        await handle_order_cancellation(message, state=state, db=db, lang=lang, _t=_t)
        return

    cfg = _resolve_config(config)
    fsm_data = await state.get_data()
    cart_total = fsm_data.get("cart_total", 0)

    if message.location:
        lat = message.location.latitude
        lon = message.location.longitude
        distance_km = calculate_distance_km(cfg.store_lat, cfg.store_lon, lat, lon)
        delivery_cost, is_free = calculate_delivery_cost(distance_km, cart_total, cfg)
        address = f"Lokatsiya: https://maps.google.com/?q={lat},{lon}"
    else:
        lat = None
        lon = None
        distance_km = 0.0
        address = (message.text or "").strip()
        is_free = cart_total >= cfg.free_delivery_threshold
        delivery_cost = 0 if is_free else cfg.base_delivery_price

    if is_free:
        congrats = tr("delivery_free_congrats")
        if distance_km > 0:
            calc_text = tr("delivery_calc_info", distance_km=distance_km, delivery_cost=0)
            info_text = f"{calc_text}\n{congrats}"
        else:
            info_text = congrats
    else:
        formatted_cost = f"{delivery_cost:,}".replace(",", " ")
        info_text = tr("delivery_calc_info", distance_km=distance_km, delivery_cost=formatted_cost)

    await state.update_data(
        address=address,
        latitude=lat,
        longitude=lon,
        distance_km=distance_km,
        delivery_cost=delivery_cost,
    )
    await state.set_state(OrderFSM.waiting_for_phone)

    prompt = tr("order_phone_prompt")
    combined_msg = f"{info_text}\n\n{prompt}"
    kb = phone_request_kb(lang=lang)
    await message.answer(combined_msg, reply_markup=kb)


# ============================================================================
# Step 4: Phone Input Handlers
# ============================================================================

@order_router.message(OrderFSM.waiting_for_phone, F.contact | F.text)
async def handle_phone_input(
    message: Message,
    state: FSMContext,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Accepts phone contact or string, updates user profile in DB, and prompts for note/postcard."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    if _is_cancel_text(message.text, lang=lang):
        await handle_order_cancellation(message, state=state, db=db, lang=lang, _t=_t)
        return

    conn = await _resolve_db(db)
    user_id = message.from_user.id if message.from_user else 0

    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = (message.text or "").strip()

    await crud.set_user_phone(conn, telegram_id=user_id, phone=phone)
    await state.update_data(phone=phone)
    await state.set_state(OrderFSM.waiting_for_note)

    prompt = tr("order_note_prompt")
    kb = skip_or_cancel_kb(lang=lang)
    await message.answer(prompt, reply_markup=kb)


# ============================================================================
# Step 5: Cake Note / Tabriknoma Handlers
# ============================================================================

@order_router.message(OrderFSM.waiting_for_note, F.text)
async def handle_note_input(
    message: Message,
    state: FSMContext,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Accepts optional greeting note/postcard text or skip button, advances to payment method."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    if _is_cancel_text(message.text, lang=lang):
        await handle_order_cancellation(message, state=state, lang=lang, _t=_t)
        return

    text = (message.text or "").strip()
    skip_labels = [
        tr("btn_skip"),
        get_text("btn_skip", "uz"),
        get_text("btn_skip", "ru"),
    ]

    if text in skip_labels or text.lower() in ("skip", "o'tkazib yuborish", "пропустить"):
        custom_note = None
    else:
        custom_note = text

    await state.update_data(custom_note=custom_note)
    await state.set_state(OrderFSM.waiting_for_payment)

    prompt = tr("order_payment_prompt")
    kb = payment_methods_kb(lang=lang)
    await message.answer(prompt, reply_markup=kb)


# ============================================================================
# Step 6: Payment Selection Handlers
# ============================================================================

@order_router.callback_query(
    OrderFSM.waiting_for_payment,
    F.data.startswith("pay_method:") | F.data.in_(["pay_cash", "pay_card", "pay_click", "pay_payme"]),
)
async def handle_payment_method(
    callback: CallbackQuery,
    state: FSMContext,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Saves payment choice, renders complete order receipt summary, and prompts for final confirmation."""
    conn = await _resolve_db(db)
    user_id = callback.from_user.id if callback.from_user else 0
    data_str = callback.data or ""
    await callback.answer()

    if "click" in data_str:
        payment_type = "click"
    elif "payme" in data_str:
        payment_type = "payme"
    elif "card" in data_str:
        payment_type = "card"
    else:
        payment_type = "cash"

    await state.update_data(payment_type=payment_type)
    fsm_data = await state.get_data()

    cart_items = await crud.get_cart(conn, user_id=user_id)
    cart_total = sum(item.get("total_price", item.get("price", 0) * item.get("quantity", 1)) for item in cart_items)
    delivery_cost = fsm_data.get("delivery_cost", 0)

    summary_text = format_order_summary(
        cart_items=cart_items,
        cart_total=cart_total,
        delivery_cost=delivery_cost,
        address=fsm_data.get("address", ""),
        target_time=fsm_data.get("target_time", "hozir"),
        phone=fsm_data.get("phone", ""),
        custom_note=fsm_data.get("custom_note"),
        payment_type=payment_type,
        lang=lang,
        _t=_t,
    )

    await state.set_state(OrderFSM.confirmation)
    kb = order_confirm_kb(lang=lang)

    if callback.message:
        try:
            await callback.message.edit_text(summary_text, reply_markup=kb)
        except (TelegramBadRequest, Exception):
            await callback.message.answer(summary_text, reply_markup=kb)


# ============================================================================
# Step 7: Order Confirmation & DB Persistence
# ============================================================================

@order_router.callback_query(
    OrderFSM.confirmation,
    F.data.in_(["order_confirm:yes", "confirm_order", "order_confirm"]),
)
async def handle_order_confirmation(
    callback: CallbackQuery,
    state: FSMContext,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Creates new order in database, clears user cart, resets FSM state,
    and returns celebratory order confirmation with tracking info and main menu.
    """
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    conn = await _resolve_db(db)
    user_id = callback.from_user.id if callback.from_user else 0
    fsm_data = await state.get_data()

    cart_items = await crud.get_cart(conn, user_id=user_id)
    cart_total = sum(item.get("total_price", item.get("price", 0) * item.get("quantity", 1)) for item in cart_items)
    delivery_cost = fsm_data.get("delivery_cost", 0)
    total_amount = cart_total + delivery_cost

    order_id = await crud.create_order(
        db=conn,
        user_id=user_id,
        order_type="standard",
        total_amount=total_amount,
        delivery_cost=delivery_cost,
        delivery_type=fsm_data.get("delivery_type", "delivery"),
        target_time=fsm_data.get("target_time", "hozir"),
        address=fsm_data.get("address"),
        latitude=fsm_data.get("latitude"),
        longitude=fsm_data.get("longitude"),
        distance_km=fsm_data.get("distance_km", 0.0),
        phone=fsm_data.get("phone", ""),
        custom_note=fsm_data.get("custom_note"),
        payment_type=fsm_data.get("payment_type", "cash"),
        custom_image_id=None,
        cart_items=cart_items,
    )

    await crud.clear_cart(conn, user_id=user_id)
    await state.clear()
    await callback.answer()

    success_msg = tr("order_confirmed_msg", order_id=order_id)
    kb = main_menu_kb(lang=lang, cart_count=0)

    if callback.message:
        await callback.message.answer(success_msg, reply_markup=kb)
