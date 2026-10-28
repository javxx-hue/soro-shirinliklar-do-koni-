"""
Telegram Payments handlers for Click and Payme provider integration.
Supports invoice generation, pre-checkout query verification, and successful payment receipts.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional
import aiosqlite

from aiogram import Bot, F, Router
from aiogram.types import LabeledPrice, Message, PreCheckoutQuery

from database import crud
from database.db import get_db_connection
from keyboards.reply import main_menu_kb
from middlewares.i18n import get_text
from shop_config import Config, load_config

logger = logging.getLogger(__name__)

payments_router = Router(name="payments")


async def _resolve_db(db: Optional[aiosqlite.Connection]) -> aiosqlite.Connection:
    """Returns active database connection, opening a default connection if None."""
    if db is not None:
        return db
    return await get_db_connection()


async def send_order_invoice(
    bot: Bot,
    chat_id: int,
    order: Dict[str, Any],
    provider: str,
    config: Config,
    lang: str = "uz",
) -> None:
    """
    Sends a Telegram payment invoice using Click or Payme provider token.
    If provider token is not configured (demo/test mode), gracefully falls back
    to a message indicating payment upon receipt.
    """
    prov = (provider or "").strip().lower()
    provider_token = config.click_token if prov == "click" else config.payme_token
    order_id = order.get("id")

    if not provider_token:
        provider_name = "Click" if prov == "click" else "Payme"
        fallback_msg = get_text("payment_demo_mode", lang=lang, provider=provider_name)
        await bot.send_message(
            chat_id=chat_id,
            text=fallback_msg,
            reply_markup=main_menu_kb(lang=lang, cart_count=0),
        )
        return

    title = get_text("payment_invoice_title", lang=lang, order_id=order_id)
    description = get_text("payment_invoice_desc", lang=lang, order_id=order_id)
    payload = f"order_{order_id}"
    currency = "UZS"

    # UZS is formatted in tiyin (1 UZS = 100 tiyin)
    amount_tiyin = int(order.get("total_amount", 0)) * 100
    prices = [LabeledPrice(label="Shirinliklar", amount=amount_tiyin)]

    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token=provider_token,
        currency=currency,
        prices=prices,
    )


@payments_router.pre_checkout_query()
async def handle_pre_checkout_query(
    query: PreCheckoutQuery,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Validates pre-checkout queries sent by Telegram before charging the user.
    Ensures order exists, is not cancelled, and is not already paid.
    """
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    conn = await _resolve_db(db)
    payload = query.invoice_payload or ""

    if not payload.startswith("order_"):
        await query.answer(ok=False, error_message=tr("payment_order_not_found"))
        return

    try:
        order_id = int(payload.split("_")[1])
    except (IndexError, ValueError):
        await query.answer(ok=False, error_message=tr("payment_order_not_found"))
        return

    order = await crud.get_order(conn, order_id)
    if not order:
        await query.answer(ok=False, error_message=tr("payment_order_not_found"))
        return

    if order.get("status") == "cancelled":
        await query.answer(ok=False, error_message=tr("payment_order_not_found"))
        return

    if order.get("payment_status") == "paid":
        await query.answer(ok=False, error_message=tr("payment_order_already_paid"))
        return

    await query.answer(ok=True)


@payments_router.message(F.successful_payment)
async def handle_successful_payment(
    message: Message,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Processes successful payment confirmation from Telegram.
    Updates database order payment status to 'paid' and sends a confirmation receipt.
    """
    def tr(key: str, **kwargs: Any) -> str:
        if _t:
            return _t(key, lang=lang, **kwargs)
        return get_text(key, lang=lang, **kwargs)

    conn = await _resolve_db(db)
    sp = message.successful_payment
    payload = sp.invoice_payload if sp else ""

    order_id: Optional[int] = None
    if payload and payload.startswith("order_"):
        try:
            order_id = int(payload.split("_")[1])
        except (IndexError, ValueError):
            pass

    if order_id is not None:
        await crud.update_payment_status(conn, order_id, "paid")

    receipt_text = tr("payment_success_receipt", order_id=order_id or "")
    await message.answer(
        receipt_text,
        reply_markup=main_menu_kb(lang=lang, cart_count=0),
    )
