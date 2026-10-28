"""
Comprehensive unit tests for Admin Panel, Order Lifecycle, and Live Customer Notifications.
"""
from __future__ import annotations

import aiosqlite
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import Bot, Router
from aiogram.types import CallbackQuery, Message, User
from database import crud
from database.db import init_db
from middlewares.i18n import get_text, load_locales
from shop_config import Config


@pytest.fixture(autouse=True)
def reload_translations():
    """Ensure translations cache is fresh before tests."""
    load_locales()


@pytest.fixture
async def memory_db():
    """In-memory SQLite database initialized with tables and seeded products."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    await init_db(db)
    yield db
    await db.close()


@pytest.fixture
def admin_config() -> Config:
    return Config(
        bot_token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
        admin_ids=[1001, 1002],
    )


# ============================================================================
# Router Definition & Export Tests
# ============================================================================

def test_admin_router_definition():
    """Verify admin_router is an aiogram.Router named 'admin' and exported from handlers."""
    from handlers import admin_router

    assert isinstance(admin_router, Router)
    assert admin_router.name == "admin"


# ============================================================================
# Notifier Service Tests
# ============================================================================

@pytest.mark.asyncio
async def test_notify_admins_new_order_text(admin_config):
    """Test notifying all admins for a standard text-based order."""
    from services.notifier import notify_admins_new_order

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()

    order = {
        "id": 101,
        "user_id": 555,
        "customer_name": "Alisher Navoiy",
        "phone": "+998901234567",
        "total_amount": 135000,
        "delivery_type": "delivery",
        "delivery_cost": 15000,
        "address": "Toshkent, Chilonzor 9",
        "latitude": 41.2855,
        "longitude": 69.2035,
        "distance_km": 4.5,
        "target_time": "hozir",
        "payment_type": "click",
        "custom_note": "Tug'ilgan kuningiz bilan!",
        "custom_image_id": None,
        "order_type": "standard",
    }
    order_items = [
        {"name_uz": "Medovik", "name_ru": "Медовик", "quantity": 1, "price_at_purchase": 120000}
    ]

    await notify_admins_new_order(bot, order, admin_config, order_items)

    assert bot.send_message.call_count == len(admin_config.admin_ids)
    assert bot.send_photo.call_count == 0

    called_chat_ids = [call.kwargs["chat_id"] for call in bot.send_message.call_args_list]
    assert set(called_chat_ids) == set(admin_config.admin_ids)

    msg_text = bot.send_message.call_args_list[0].kwargs["text"]
    assert "#101" in msg_text
    assert "+998901234567" in msg_text
    assert any(x in msg_text for x in ("135000", "135,000"))
    assert "Medovik" in msg_text
    assert "Toshkent, Chilonzor 9" in msg_text
    assert "maps.google.com" in msg_text
    assert "Tug'ilgan kuningiz bilan!" in msg_text

    markup = bot.send_message.call_args_list[0].kwargs.get("reply_markup")
    assert markup is not None


@pytest.mark.asyncio
async def test_notify_admins_new_order_with_custom_image(admin_config):
    """Test sending photo message when custom_image_id is present."""
    from services.notifier import notify_admins_new_order

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()
    bot.send_photo = AsyncMock()

    order = {
        "id": 102,
        "user_id": 556,
        "customer_name": "Madina",
        "phone": "+998919876543",
        "total_amount": 250000,
        "delivery_type": "pickup",
        "delivery_cost": 0,
        "address": None,
        "latitude": None,
        "longitude": None,
        "distance_km": 0.0,
        "target_time": "30-oktabr 15:00",
        "payment_type": "custom_quote",
        "custom_note": "Shokoladli va bananli nachinka",
        "custom_image_id": "telegram_file_id_custom_cake_123",
        "order_type": "custom_cake",
    }

    await notify_admins_new_order(bot, order, admin_config, None)

    assert bot.send_photo.call_count == len(admin_config.admin_ids)
    assert bot.send_message.call_count == 0

    photo_call = bot.send_photo.call_args_list[0]
    assert photo_call.kwargs["photo"] == "telegram_file_id_custom_cake_123"
    caption = photo_call.kwargs["caption"]
    assert "#102" in caption
    assert "Madina" in caption or "556" in caption
    assert "Shokoladli va bananli" in caption
    assert photo_call.kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_notify_customer_status_change_uzbek():
    """Verify customer receives localized Uzbek status notifications for all progression states."""
    from services.notifier import notify_customer_status_change

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    user_id = 777
    order_id = 99

    # Confirmed
    await notify_customer_status_change(bot, user_id=user_id, order_id=order_id, new_status="confirmed", lang="uz")
    assert bot.send_message.call_count == 1
    text = bot.send_message.call_args.kwargs["text"]
    assert "#99" in text
    assert any(w in text.lower() for w in ("tasdiqlandi", "qabul qilindi"))

    # Preparing
    bot.send_message.reset_mock()
    await notify_customer_status_change(bot, user_id=user_id, order_id=order_id, new_status="preparing", lang="uz")
    text = bot.send_message.call_args.kwargs["text"]
    assert "#99" in text
    assert "tayyorlash" in text.lower()

    # Delivering
    bot.send_message.reset_mock()
    await notify_customer_status_change(bot, user_id=user_id, order_id=order_id, new_status="delivering", lang="uz")
    text = bot.send_message.call_args.kwargs["text"]
    assert "#99" in text
    assert any(w in text.lower() for w in ("kuryer", "yo'lga chiqdi"))

    # Completed
    bot.send_message.reset_mock()
    await notify_customer_status_change(bot, user_id=user_id, order_id=order_id, new_status="completed", lang="uz")
    text = bot.send_message.call_args.kwargs["text"]
    assert "#99" in text
    assert any(w in text.lower() for w in ("yetkazildi", "yakunlandi", "ishtaha"))

    # Cancelled with reason
    bot.send_message.reset_mock()
    await notify_customer_status_change(
        bot,
        user_id=user_id,
        order_id=order_id,
        new_status="cancelled",
        lang="uz",
        cancel_reason="Mahsulot tugagan",
    )
    text = bot.send_message.call_args.kwargs["text"]
    assert "#99" in text
    assert "bekor qilindi" in text.lower()
    assert "Mahsulot tugagan" in text


@pytest.mark.asyncio
async def test_notify_customer_status_change_russian():
    """Verify customer receives localized Russian status notifications."""
    from services.notifier import notify_customer_status_change

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    user_id = 888
    order_id = 100

    await notify_customer_status_change(bot, user_id=user_id, order_id=order_id, new_status="confirmed", lang="ru")
    text = bot.send_message.call_args.kwargs["text"]
    assert "#100" in text
    assert any(w in text.lower() for w in ("принят", "подтвержден"))

    bot.send_message.reset_mock()
    await notify_customer_status_change(
        bot,
        user_id=user_id,
        order_id=order_id,
        new_status="cancelled",
        lang="ru",
        cancel_reason="Техническая причина",
    )
    text = bot.send_message.call_args.kwargs["text"]
    assert "#100" in text
    assert "отменен" in text.lower()
    assert "Техническая причина" in text


# ============================================================================
# Admin Order Status Transition Callbacks Tests
# ============================================================================

@pytest.mark.asyncio
async def test_admin_order_lifecycle_transitions(memory_db, admin_config):
    """
    Test the full order lifecycle through admin callbacks:
    new -> adm_confirm_<id> (confirmed)
        -> adm_ready_<id> (preparing)
        -> adm_dispatch_<id> (delivering)
        -> adm_complete_<id> (completed)
    """
    from handlers.admin.orders import handle_admin_order_callback

    # Create customer user and order
    customer_id = 2001
    await crud.upsert_user(memory_db, telegram_id=customer_id, full_name="Xaridor", language="uz")

    order_id = await crud.create_order(
        db=memory_db,
        user_id=customer_id,
        order_type="standard",
        total_amount=150000,
        delivery_cost=12000,
        delivery_type="delivery",
        target_time="hozir",
        address="Amir Temur 10",
        latitude=41.3,
        longitude=69.2,
        distance_km=2.0,
        phone="+998901234567",
        custom_note=None,
        payment_type="cash",
    )

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    def make_callback(data: str, admin_id: int = 1001) -> CallbackQuery:
        cb = MagicMock(spec=CallbackQuery)
        cb.data = data
        cb.bot = bot
        cb.from_user = MagicMock(spec=User)
        cb.from_user.id = admin_id
        cb.message = MagicMock(spec=Message)
        cb.message.edit_reply_markup = AsyncMock()
        cb.message.edit_text = AsyncMock()
        cb.answer = AsyncMock()
        return cb

    # 1. Confirm order: adm_confirm_<id> -> 'confirmed'
    cb = make_callback(f"adm_confirm_{order_id}")
    await handle_admin_order_callback(cb, db=memory_db, config=admin_config)

    order = await crud.get_order(memory_db, order_id)
    assert order["status"] == "confirmed"
    assert bot.send_message.call_count == 1
    assert "tasdiqlandi" in bot.send_message.call_args.kwargs["text"].lower()
    cb.answer.assert_called_once()

    # 2. Mark preparing: adm_ready_<id> -> 'preparing'
    bot.send_message.reset_mock()
    cb = make_callback(f"adm_ready_{order_id}")
    await handle_admin_order_callback(cb, db=memory_db, config=admin_config)

    order = await crud.get_order(memory_db, order_id)
    assert order["status"] == "preparing"
    assert bot.send_message.call_count == 1
    assert "tayyorlash" in bot.send_message.call_args.kwargs["text"].lower()

    # 3. Dispatch delivery: adm_dispatch_<id> -> 'delivering'
    bot.send_message.reset_mock()
    cb = make_callback(f"adm_dispatch_{order_id}")
    await handle_admin_order_callback(cb, db=memory_db, config=admin_config)

    order = await crud.get_order(memory_db, order_id)
    assert order["status"] == "delivering"
    assert bot.send_message.call_count == 1
    assert "kuryer" in bot.send_message.call_args.kwargs["text"].lower()

    # 4. Complete order: adm_complete_<id> -> 'completed'
    bot.send_message.reset_mock()
    cb = make_callback(f"adm_complete_{order_id}")
    await handle_admin_order_callback(cb, db=memory_db, config=admin_config)

    order = await crud.get_order(memory_db, order_id)
    assert order["status"] == "completed"
    assert bot.send_message.call_count == 1
    assert any(w in bot.send_message.call_args.kwargs["text"].lower() for w in ("yetkazildi", "yakunlandi"))


@pytest.mark.asyncio
async def test_admin_order_cancel_callback(memory_db, admin_config):
    """Test cancelling an order via adm_cancel_<id> callback."""
    from handlers.admin.orders import handle_admin_order_callback

    customer_id = 2002
    await crud.upsert_user(memory_db, telegram_id=customer_id, full_name="Mijoz", language="uz")

    order_id = await crud.create_order(
        db=memory_db,
        user_id=customer_id,
        order_type="standard",
        total_amount=80000,
        delivery_cost=0,
        delivery_type="pickup",
        target_time="hozir",
        address=None,
        latitude=None,
        longitude=None,
        distance_km=0.0,
        phone="+998909998877",
        custom_note=None,
        payment_type="cash",
    )

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    cb = MagicMock(spec=CallbackQuery)
    cb.data = f"adm_cancel_{order_id}"
    cb.bot = bot
    cb.from_user = MagicMock(spec=User)
    cb.from_user.id = 1001
    cb.message = MagicMock(spec=Message)
    cb.message.edit_reply_markup = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()

    await handle_admin_order_callback(cb, db=memory_db, config=admin_config)

    order = await crud.get_order(memory_db, order_id)
    assert order["status"] == "cancelled"
    assert bot.send_message.call_count == 1
    assert "bekor qilindi" in bot.send_message.call_args.kwargs["text"].lower()


@pytest.mark.asyncio
async def test_admin_order_colon_prefix_callbacks(memory_db, admin_config):
    """Test compatibility with 'admin_order:<action>:<id>' callbacks from admin_kb."""
    from handlers.admin.orders import handle_admin_order_callback

    customer_id = 2003
    await crud.upsert_user(memory_db, telegram_id=customer_id, full_name="Mijoz 3", language="uz")

    order_id = await crud.create_order(
        db=memory_db,
        user_id=customer_id,
        order_type="standard",
        total_amount=50000,
        delivery_cost=0,
        delivery_type="pickup",
        target_time="hozir",
        address=None,
        latitude=None,
        longitude=None,
        distance_km=0.0,
        phone="+998901234567",
        custom_note=None,
        payment_type="cash",
    )

    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()

    cb = MagicMock(spec=CallbackQuery)
    cb.data = f"admin_order:preparing:{order_id}"
    cb.bot = bot
    cb.from_user = MagicMock(spec=User)
    cb.from_user.id = 1001
    cb.message = MagicMock(spec=Message)
    cb.message.edit_reply_markup = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()

    await handle_admin_order_callback(cb, db=memory_db, config=admin_config)

    order = await crud.get_order(memory_db, order_id)
    assert order["status"] in ("confirmed", "preparing")


# ============================================================================
# Non-Admin Security & Rejection Tests
# ============================================================================

@pytest.mark.asyncio
async def test_non_admin_access_rejected_in_panel(memory_db, admin_config):
    """Verify non-admin user is rejected from opening admin panel."""
    from handlers.admin.panel import admin_panel_command

    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 999999  # Not in config.admin_ids
    msg.answer = AsyncMock()

    await admin_panel_command(msg, config=admin_config)

    msg.answer.assert_called_once()
    reply_text = msg.answer.call_args[0][0]
    assert any(w in reply_text.lower() for w in ("ruxsat", "admin emassiz", "yo'q", "denied"))


@pytest.mark.asyncio
async def test_non_admin_order_callback_rejected(memory_db, admin_config):
    """Verify non-admin user cannot advance or cancel orders via callbacks."""
    from handlers.admin.orders import handle_admin_order_callback

    cb = MagicMock(spec=CallbackQuery)
    cb.data = "adm_confirm_1"
    cb.from_user = MagicMock(spec=User)
    cb.from_user.id = 999999  # Not an admin
    cb.answer = AsyncMock()

    await handle_admin_order_callback(cb, db=memory_db, config=admin_config)

    cb.answer.assert_called_once()
    answer_text = cb.answer.call_args.kwargs.get("text", "") or (cb.answer.call_args.args[0] if cb.answer.call_args.args else "")
    assert any(w in answer_text.lower() for w in ("ruxsat", "admin", "mumkin emas", "denied"))


@pytest.mark.asyncio
async def test_admin_filter():
    """Verify AdminFilter correctly checks user ID against config.admin_ids."""
    from handlers.admin import AdminFilter

    admin_filter = AdminFilter()
    cfg = Config(bot_token="tok", admin_ids=[1001, 1002])

    admin_event = MagicMock()
    admin_event.from_user = MagicMock(id=1001)

    non_admin_event = MagicMock()
    non_admin_event.from_user = MagicMock(id=5555)

    assert await admin_filter(admin_event, config=cfg) is True
    assert await admin_filter(non_admin_event, config=cfg) is False


# ============================================================================
# Admin Panel & Statistics Tests
# ============================================================================

@pytest.mark.asyncio
async def test_admin_panel_open_for_admin(admin_config):
    """Verify authorized admin can open admin menu and gets admin reply keyboard."""
    from handlers.admin.panel import admin_panel_command

    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 1001
    msg.answer = AsyncMock()

    await admin_panel_command(msg, config=admin_config)

    msg.answer.assert_called_once()
    args, kwargs = msg.answer.call_args
    assert "admin" in args[0].lower() or "boshqaruv" in args[0].lower()
    kb = kwargs.get("reply_markup")
    assert kb is not None
    button_texts = [btn.text for row in kb.keyboard for btn in row]
    assert any("Statistika" in t for t in button_texts)
    assert any("Buyurtmalar" in t for t in button_texts)


@pytest.mark.asyncio
async def test_admin_statistics(memory_db, admin_config):
    """Verify admin statistics command displays order counts and sales amounts."""
    from handlers.admin.panel import admin_statistics

    # Seed orders into DB
    await crud.create_order(
        db=memory_db,
        user_id=1,
        order_type="standard",
        total_amount=100000,
        delivery_cost=10000,
        delivery_type="delivery",
        target_time="hozir",
        address="Test 1",
        latitude=None,
        longitude=None,
        distance_km=0,
        phone="+998901111111",
        custom_note=None,
        payment_type="cash",
    )
    await crud.create_order(
        db=memory_db,
        user_id=2,
        order_type="standard",
        total_amount=150000,
        delivery_cost=0,
        delivery_type="pickup",
        target_time="hozir",
        address=None,
        latitude=None,
        longitude=None,
        distance_km=0,
        phone="+998902222222",
        custom_note=None,
        payment_type="click",
    )

    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 1001
    msg.answer = AsyncMock()

    await admin_statistics(msg, db=memory_db, config=admin_config)

    msg.answer.assert_called_once()
    text = msg.answer.call_args[0][0]
    assert "Statistika" in text or "statistika" in text.lower()
    assert "2" in text  # Total orders count
    assert "250" in text  # Total revenue sum (250,000)


@pytest.mark.asyncio
async def test_admin_new_orders_list(memory_db, admin_config):
    """Verify admin can list pending/active orders."""
    from handlers.admin.panel import admin_new_orders

    order_id = await crud.create_order(
        db=memory_db,
        user_id=1,
        order_type="standard",
        total_amount=120000,
        delivery_cost=12000,
        delivery_type="delivery",
        target_time="hozir",
        address="Manzil 123",
        latitude=None,
        longitude=None,
        distance_km=0,
        phone="+998903333333",
        custom_note=None,
        payment_type="cash",
    )

    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 1001
    msg.answer = AsyncMock()

    await admin_new_orders(msg, db=memory_db, config=admin_config)

    assert msg.answer.call_count >= 1
    # Check that the order is listed with action buttons
    first_call_args = msg.answer.call_args_list[0]
    found_order_id = any(f"#{order_id}" in str(call) or "120000" in str(call) for call in msg.answer.call_args_list)
    assert found_order_id is True


# ============================================================================
# Product Stop-List Management Tests
# ============================================================================

@pytest.mark.asyncio
async def test_admin_products_stoplist_view_and_toggle(memory_db, admin_config):
    """Test viewing product stop-list and toggling availability."""
    from handlers.admin.products import admin_products_stoplist, handle_toggle_product

    # Initial view of stoplist
    msg = MagicMock(spec=Message)
    msg.from_user = MagicMock(spec=User)
    msg.from_user.id = 1001
    msg.answer = AsyncMock()

    await admin_products_stoplist(msg, db=memory_db, config=admin_config)

    msg.answer.assert_called_once()
    kb = msg.answer.call_args.kwargs.get("reply_markup")
    assert kb is not None
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert any(btn.callback_data.startswith("toggle_prod_") for btn in buttons)

    # Pick first product
    target_btn = [btn for btn in buttons if btn.callback_data.startswith("toggle_prod_")][0]
    prod_id = int(target_btn.callback_data.replace("toggle_prod_", ""))

    prod_before = await crud.get_product(memory_db, prod_id)
    assert prod_before["is_available"] == 1

    # Toggle to 0 (stop-list)
    cb = MagicMock(spec=CallbackQuery)
    cb.data = f"toggle_prod_{prod_id}"
    cb.from_user = MagicMock(spec=User)
    cb.from_user.id = 1001
    cb.message = MagicMock(spec=Message)
    cb.message.edit_reply_markup = AsyncMock()
    cb.answer = AsyncMock()

    await handle_toggle_product(cb, db=memory_db, config=admin_config)

    prod_after = await crud.get_product(memory_db, prod_id)
    assert prod_after["is_available"] == 0
    cb.answer.assert_called_once()
    cb.message.edit_reply_markup.assert_called_once()

    # Toggle back to 1 (available)
    cb.message.edit_reply_markup.reset_mock()
    cb.answer.reset_mock()
    await handle_toggle_product(cb, db=memory_db, config=admin_config)

    prod_restored = await crud.get_product(memory_db, prod_id)
    assert prod_restored["is_available"] == 1
    cb.answer.assert_called_once()
    cb.message.edit_reply_markup.assert_called_once()
