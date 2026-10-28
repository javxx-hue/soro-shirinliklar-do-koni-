"""
Custom Cake Ordering FSM flow handlers for the sweet shop Telegram bot.
Allows customers to order cakes by photo or custom description, specify weight,
filling preferences, event/delivery date and time, and leave phone contact.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Union
import aiosqlite

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from database import crud
from database.db import get_db_connection
from keyboards.inline import order_confirm_kb
from keyboards.reply import cancel_kb, main_menu_kb, phone_request_kb
from middlewares.i18n import get_text

logger = logging.getLogger(__name__)

custom_cake_router = Router(name="custom_cake")


class CustomCakeFSM(StatesGroup):
    """FSM states representing the sequential steps for ordering a custom cake."""
    waiting_for_photo = State()
    waiting_for_details = State()
    waiting_for_target_time = State()
    waiting_for_phone = State()
    confirmation = State()


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
        logger.warning(f"Could not open default DB connection: {e}")
        return None


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


def format_custom_cake_summary(
    custom_image_id: Optional[str],
    photo_desc: str,
    details: str,
    target_time: str,
    phone: str,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> str:
    """Compiles custom cake order preview summary."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    if lang == "ru":
        photo_label = "📸 Фото загружено" if custom_image_id else f"📝 Описание: {photo_desc or 'Без фото'}"
        return (
            "📋 <b>Детали индивидуального заказа торта:</b>\n\n"
            f"{photo_label}\n"
            f"⚖️ <b>Вес и начинка:</b> {details}\n"
            f"⏰ <b>Время готовности:</b> {target_time}\n"
            f"📱 <b>Телефон:</b> {phone}\n"
            "💰 <b>Стоимость:</b> Рассчитает кондитер (по согласованию)\n\n"
            "Всё верно? Подтвердите заказ:"
        )
    else:
        photo_label = "📸 Rasm yuklangan" if custom_image_id else f"📝 Tavsif: {photo_desc or 'Rasmsiz'}"
        return (
            "📋 <b>O'z orzuingizdagi tort buyurtmasi ma'lumotlari:</b>\n\n"
            f"{photo_label}\n"
            f"⚖️ <b>Vazn va nachinka:</b> {details}\n"
            f"⏰ <b>Tayyor bo'lish vaqti:</b> {target_time}\n"
            f"📱 <b>Telefon:</b> {phone}\n"
            "💰 <b>Narxi:</b> Bosh qandolatchi hisoblab aytadi (kelishiladi)\n\n"
            "Barcha ma'lumotlar to'g'rimi? Buyurtmani tasdiqlaysizmi?"
        )


# ============================================================================
# Cancellation Handler (Active in all CustomCakeFSM states)
# ============================================================================

@custom_cake_router.callback_query(
    CustomCakeFSM(),
    F.data.in_(["order_cancel", "cancel_custom_cake", "order_confirm:cancel", "cancel_order"]),
)
@custom_cake_router.message(
    CustomCakeFSM(),
    F.text.in_([
        get_text("cancel_btn", "uz"),
        get_text("cancel_btn", "ru"),
    ])
    | F.text.casefold().contains("bekor qilish")
    | F.text.casefold().contains("отмена"),
)
@custom_cake_router.message(
    CustomCakeFSM(),
    Command("cancel"),
)
async def handle_custom_cake_cancel(
    event: Union[CallbackQuery, Message],
    state: Optional[FSMContext] = None,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Cancels custom cake ordering flow, clears FSM state, and restores main menu."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    conn = await _resolve_db(db)
    user_id = event.from_user.id if event.from_user else 0

    if state is not None:
        await state.clear()

    cart_count = 0
    if conn:
        try:
            cart_items = await crud.get_cart(conn, user_id=user_id)
            cart_count = sum(item.get("quantity", 1) for item in cart_items)
        except Exception:
            cart_count = 0

    kb = main_menu_kb(lang=lang, cart_count=cart_count)
    cancel_text = tr("action_cancelled")

    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(cancel_text, reply_markup=kb)
    else:
        await event.answer(cancel_text, reply_markup=kb)


# ============================================================================
# Entry Point: Trigger Custom Cake Flow
# ============================================================================

@custom_cake_router.message(Command("custom_cake"))
@custom_cake_router.message(
    F.text.regexp(r"(?i).*o'?z tortingizga.*")
    | F.text.regexp(r"(?i).*заказ торта по фото.*")
    | F.text.in_([
        get_text("btn_custom_cake", "uz"),
        get_text("btn_custom_cake", "ru"),
    ])
)
@custom_cake_router.callback_query(
    F.data.in_(["custom_cake", "start_custom_cake"])
)
async def start_custom_cake(
    event: Union[CallbackQuery, Message],
    state: FSMContext,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Initiates custom cake ordering flow and prompts user to upload a photo or write description."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    await state.clear()
    await state.set_state(CustomCakeFSM.waiting_for_photo)

    prompt = f"{tr('custom_cake_intro')}\n\n{tr('custom_cake_send_photo')}"
    kb = cancel_kb(lang=lang)

    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(prompt, reply_markup=kb)
    else:
        await event.answer(prompt, reply_markup=kb)


# ============================================================================
# Step 1: Photo or Text Description
# ============================================================================

@custom_cake_router.message(CustomCakeFSM.waiting_for_photo, F.photo | F.text)
async def handle_custom_cake_photo(
    message: Message,
    state: FSMContext,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Accepts uploaded photo (capturing highest-res file_id) or text description, moves to details."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    if _is_cancel_text(message.text, lang=lang):
        await handle_custom_cake_cancel(message, state=state, db=db, lang=lang, _t=_t)
        return

    if message.photo:
        photo_id = message.photo[-1].file_id
        photo_desc = (message.caption or "").strip()
    else:
        photo_id = None
        photo_desc = (message.text or "").strip()

    await state.update_data(
        custom_image_id=photo_id,
        photo_desc=photo_desc,
    )
    await state.set_state(CustomCakeFSM.waiting_for_details)

    prompt = f"{tr('custom_cake_send_weight')}\n\n{tr('custom_cake_send_desc')}"
    kb = cancel_kb(lang=lang)
    await message.answer(prompt, reply_markup=kb)


# ============================================================================
# Step 2: Weight and Filling Details
# ============================================================================

@custom_cake_router.message(CustomCakeFSM.waiting_for_details, F.text)
async def handle_custom_cake_details(
    message: Message,
    state: FSMContext,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Captures desired cake weight and filling preferences, moves to target time."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    if _is_cancel_text(message.text, lang=lang):
        await handle_custom_cake_cancel(message, state=state, db=db, lang=lang, _t=_t)
        return

    details = (message.text or "").strip()
    await state.update_data(details=details)
    await state.set_state(CustomCakeFSM.waiting_for_target_time)

    prompt = tr("custom_cake_send_date")
    kb = cancel_kb(lang=lang)
    await message.answer(prompt, reply_markup=kb)


# ============================================================================
# Step 3: Target Date and Time
# ============================================================================

@custom_cake_router.message(CustomCakeFSM.waiting_for_target_time, F.text)
async def handle_custom_cake_target_time(
    message: Message,
    state: FSMContext,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Captures target delivery or event date/time, prompts for contact phone."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    if _is_cancel_text(message.text, lang=lang):
        await handle_custom_cake_cancel(message, state=state, db=db, lang=lang, _t=_t)
        return

    target_time = (message.text or "").strip()
    await state.update_data(target_time=target_time)
    await state.set_state(CustomCakeFSM.waiting_for_phone)

    prompt = tr("order_phone_prompt")
    kb = phone_request_kb(lang=lang)
    await message.answer(prompt, reply_markup=kb)


# ============================================================================
# Step 4: Phone Contact Input
# ============================================================================

@custom_cake_router.message(CustomCakeFSM.waiting_for_phone, F.contact | F.text)
async def handle_custom_cake_phone(
    message: Message,
    state: FSMContext,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Accepts phone contact or text, stores in DB & state, displays order preview summary."""
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    if _is_cancel_text(message.text, lang=lang):
        await handle_custom_cake_cancel(message, state=state, db=db, lang=lang, _t=_t)
        return

    conn = await _resolve_db(db)
    user_id = message.from_user.id if message.from_user else 0

    if message.contact:
        phone = message.contact.phone_number
    else:
        phone = (message.text or "").strip()

    if conn and user_id:
        try:
            await crud.set_user_phone(conn, telegram_id=user_id, phone=phone)
        except Exception:
            pass

    await state.update_data(phone=phone)
    await state.set_state(CustomCakeFSM.confirmation)

    data = await state.get_data()
    summary = format_custom_cake_summary(
        custom_image_id=data.get("custom_image_id"),
        photo_desc=data.get("photo_desc", ""),
        details=data.get("details", ""),
        target_time=data.get("target_time", ""),
        phone=phone,
        lang=lang,
        _t=_t,
    )

    kb = order_confirm_kb(lang=lang)
    await message.answer(summary, reply_markup=kb)


# ============================================================================
# Step 5: Order Confirmation & Persistence
# ============================================================================

@custom_cake_router.callback_query(
    CustomCakeFSM.confirmation,
    F.data.in_(["order_confirm:yes", "confirm_custom_cake", "confirm_order"]),
)
@custom_cake_router.message(
    CustomCakeFSM.confirmation,
    F.text.in_([
        get_text("btn_confirm_order", "uz"),
        get_text("btn_confirm_order", "ru"),
    ])
    | F.text.casefold().contains("tasdiqlash")
    | F.text.casefold().contains("подтвердить")
)
async def handle_custom_cake_confirmation(
    event: Union[CallbackQuery, Message],
    state: FSMContext,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Saves custom cake order to DB with order_type='custom_cake', total_amount=0,
    payment_type='custom_quote', resets state, and notifies user with order number.
    """
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    conn = await _resolve_db(db)
    user_id = event.from_user.id if event.from_user else 0
    data = await state.get_data()

    custom_image_id = data.get("custom_image_id")
    photo_desc = data.get("photo_desc", "")
    details = data.get("details", "")
    target_time = data.get("target_time", "")
    phone = data.get("phone", "")

    note_parts = []
    if photo_desc:
        note_parts.append(f"Tavsif: {photo_desc}")
    if details:
        note_parts.append(f"Vazn va nachinka: {details}")
    custom_note = "\n".join(note_parts) if note_parts else (details or "Maxsus tort")

    order_id = 0
    if conn:
        order_id = await crud.create_order(
            db=conn,
            user_id=user_id,
            order_type="custom_cake",
            total_amount=0,
            delivery_cost=0,
            delivery_type="custom",
            target_time=target_time,
            address=None,
            latitude=None,
            longitude=None,
            distance_km=0.0,
            phone=phone,
            custom_note=custom_note,
            payment_type="custom_quote",
            custom_image_id=custom_image_id,
        )

    await state.clear()

    cart_count = 0
    if conn:
        try:
            cart_items = await crud.get_cart(conn, user_id=user_id)
            cart_count = sum(item.get("quantity", 1) for item in cart_items)
        except Exception:
            cart_count = 0

    kb = main_menu_kb(lang=lang, cart_count=cart_count)
    success_msg = tr("custom_cake_received", order_id=order_id)

    if isinstance(event, CallbackQuery):
        await event.answer()
        if event.message:
            await event.message.answer(success_msg, reply_markup=kb)
    else:
        await event.answer(success_msg, reply_markup=kb)
