"""
Real-time notification service for admin alerts and customer order lifecycle tracking.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from aiogram import Bot
from keyboards.admin_kb import order_admin_actions_kb
from middlewares.i18n import get_text
from shop_config import Config

logger = logging.getLogger(__name__)


def format_order_admin_text(order: Dict[str, Any], order_items: Optional[List[Dict[str, Any]]] = None) -> str:
    """Formats full order details for administrative review and action."""
    order_id = order.get("id", 0)
    customer = order.get("customer_name") or order.get("user_id", "Noma'lum")
    phone = order.get("phone", "Ko'rsatilmagan")
    delivery_type = order.get("delivery_type", "delivery")
    deliv_type_text = "🚗 Yetkazib berish" if delivery_type == "delivery" else "🏃 Olib ketish (Samovivoz)"
    address = order.get("address") or "Ko'rsatilmagan"
    target_time = order.get("target_time", "Hozir")
    total_amount = order.get("total_amount", 0)
    delivery_cost = order.get("delivery_cost", 0)
    distance_km = order.get("distance_km", 0.0)
    payment_type = order.get("payment_type", "cash")
    custom_note = order.get("custom_note")
    order_type = order.get("order_type", "standard")

    lines = [
        f"🚨 <b>Yangi buyurtma #{order_id}!</b>",
        f"📋 Turi: <b>{'🎨 O\'z tortingiz' if order_type == 'custom_cake' else '🍰 Standart buyurtma'}</b>",
        f"👤 Mijoz: <b>{customer}</b>",
        f"📱 Telefon: <b>{phone}</b>",
        f"🚗 Yetkazish: <b>{deliv_type_text}</b>",
        f"⏰ Vaqt: <b>{target_time}</b>",
    ]

    if delivery_type == "delivery":
        lines.append(f"📍 Manzil: <b>{address}</b>")
        if distance_km:
            lines.append(f"📏 Masofa: <b>{distance_km} km</b>")
        lat = order.get("latitude")
        lon = order.get("longitude")
        if lat and lon:
            lines.append(f"🗺 Xarita: https://maps.google.com/?q={lat},{lon}")

    if order_items:
        lines.append("\n📦 <b>Tarkibi:</b>")
        for i, item in enumerate(order_items, 1):
            name = item.get("name_uz") or item.get("name_ru") or item.get("name", "Mahsulot")
            qty = item.get("quantity", 1)
            price = item.get("price_at_purchase", item.get("price", 0))
            item_total = price * qty
            lines.append(f"  {i}. {name} — {qty} dona x {price:,} = {item_total:,} so'm")

    if delivery_cost:
        lines.append(f"🚗 Yetkazish haqi: <b>{delivery_cost:,} so'm</b>")

    lines.append(f"💰 Jami summa: <b>{total_amount:,} so'm</b>")
    lines.append(f"💳 To'lov: <b>{payment_type.upper()}</b>")

    if custom_note:
        lines.append(f"💌 Izoh/yozuv: <i>{custom_note}</i>")

    return "\n".join(lines)


async def notify_admins_new_order(
    bot: Bot,
    order: Dict[str, Any],
    config: Config,
    order_items: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Sends new order alert to all configured administrators.
    If the order contains a custom reference cake image, sends a photo with action keyboard.
    Otherwise sends a formatted text message with action keyboard.
    """
    order_id = order.get("id", 0)
    text = format_order_admin_text(order, order_items)
    custom_image_id = order.get("custom_image_id")
    kb = order_admin_actions_kb(order_id=order_id, current_status="new")

    for admin_id in config.admin_ids:
        try:
            if custom_image_id:
                await bot.send_photo(
                    chat_id=admin_id,
                    photo=custom_image_id,
                    caption=text,
                    reply_markup=kb,
                )
            else:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    reply_markup=kb,
                )
        except Exception as exc:
            logger.warning("Failed to send order #%s alert to admin %s: %s", order_id, admin_id, exc)


async def notify_customer_status_change(
    bot: Bot,
    user_id: int,
    order_id: int,
    new_status: str,
    lang: str = "uz",
    cancel_reason: str = "",
) -> None:
    """
    Sends localized live status update message to customer when their order progresses.
    """
    target_lang = lang if lang in ("uz", "ru") else "uz"
    status_lower = (new_status or "").strip().lower()

    if status_lower in ("confirmed", "accepted"):
        text = get_text("status_confirmed", lang=target_lang, order_id=order_id)
    elif status_lower in ("preparing", "ready"):
        text = get_text("status_preparing", lang=target_lang, order_id=order_id)
    elif status_lower in ("delivering", "dispatch", "sent"):
        text = get_text("status_delivering", lang=target_lang, order_id=order_id)
    elif status_lower in ("completed", "delivered"):
        text = get_text("status_completed", lang=target_lang, order_id=order_id)
    elif status_lower in ("cancelled", "canceled"):
        reason_text = cancel_reason
        text = get_text("status_cancelled", lang=target_lang, order_id=order_id, reason=reason_text, cancel_reason=reason_text)
    else:
        text = f"Buyurtmangiz #{order_id} holati yangilandi: {new_status}"

    try:
        await bot.send_message(chat_id=user_id, text=text)
    except Exception as exc:
        logger.warning("Failed to notify customer %s of order #%s status %s: %s", user_id, order_id, new_status, exc)
