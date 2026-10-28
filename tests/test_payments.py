"""
Unit and integration tests for Telegram Payments router (handlers/payments.py).
Tests Click and Payme invoices, PreCheckoutQuery validation, and SuccessfulPayment processing.
"""
from unittest.mock import AsyncMock, MagicMock
import pytest
import aiosqlite
from aiogram import Router, Bot
from aiogram.types import (
    CallbackQuery,
    Message,
    PreCheckoutQuery,
    SuccessfulPayment,
    User,
    Chat,
    LabeledPrice,
)

from shop_config import Config
from database.db import init_db
from database import crud
from middlewares.i18n import get_text
from keyboards.reply import main_menu_kb


@pytest.fixture
def test_config():
    """Shop configuration with test payment tokens."""
    return Config(
        bot_token="123456:TEST_TOKEN",
        admin_ids=[9999],
        click_token="TEST_CLICK_PROVIDER_TOKEN",
        payme_token="TEST_PAYME_PROVIDER_TOKEN",
    )


@pytest.fixture
def empty_token_config():
    """Shop configuration with empty payment tokens (demo mode)."""
    return Config(
        bot_token="123456:TEST_TOKEN",
        admin_ids=[9999],
        click_token="",
        payme_token="",
    )


@pytest.fixture
async def memory_db():
    """In-memory SQLite database initialized with tables and schema."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    await init_db(db)
    yield db
    await db.close()


def fake_t(lang="uz"):
    """Helper to mock i18n translation callable."""
    return lambda key, **kwargs: get_text(key, lang=kwargs.pop("lang", lang), **kwargs)


# ============================================================================
# 1. Router Definition & Export
# ============================================================================

def test_payments_router_definition():
    """Verify payments_router is defined as an aiogram Router and exported in handlers."""
    from handlers.payments import payments_router
    from handlers import payments_router as exported_router

    assert isinstance(payments_router, Router)
    assert payments_router.name == "payments"
    assert exported_router is payments_router


# ============================================================================
# 2. send_order_invoice Tests
# ============================================================================

@pytest.mark.asyncio
async def test_send_order_invoice_click_success(test_config):
    """When Click token is present, bot.send_invoice is called with correct parameters."""
    from handlers.payments import send_order_invoice

    bot = MagicMock(spec=Bot)
    bot.send_invoice = AsyncMock()

    order = {
        "id": 42,
        "total_amount": 150000,
    }

    await send_order_invoice(
        bot=bot,
        chat_id=1234567,
        order=order,
        provider="click",
        config=test_config,
        lang="uz",
    )

    bot.send_invoice.assert_awaited_once()
    call_kwargs = bot.send_invoice.call_args[1]

    assert call_kwargs["chat_id"] == 1234567
    assert "42" in call_kwargs["title"]
    assert call_kwargs["payload"] == "order_42"
    assert call_kwargs["provider_token"] == "TEST_CLICK_PROVIDER_TOKEN"
    assert call_kwargs["currency"] == "UZS"
    assert len(call_kwargs["prices"]) == 1
    # 150 000 UZS * 100 = 15 000 000 tiyin
    assert call_kwargs["prices"][0].amount == 15000000
    assert call_kwargs["prices"][0].label == "Shirinliklar"


@pytest.mark.asyncio
async def test_send_order_invoice_payme_success(test_config):
    """When Payme token is present, bot.send_invoice uses payme_token and Russian strings."""
    from handlers.payments import send_order_invoice

    bot = MagicMock(spec=Bot)
    bot.send_invoice = AsyncMock()

    order = {
        "id": 77,
        "total_amount": 220000,
    }

    await send_order_invoice(
        bot=bot,
        chat_id=9876543,
        order=order,
        provider="payme",
        config=test_config,
        lang="ru",
    )

    bot.send_invoice.assert_awaited_once()
    call_kwargs = bot.send_invoice.call_args[1]

    assert call_kwargs["chat_id"] == 9876543
    assert "77" in call_kwargs["title"]
    assert call_kwargs["payload"] == "order_77"
    assert call_kwargs["provider_token"] == "TEST_PAYME_PROVIDER_TOKEN"
    assert call_kwargs["currency"] == "UZS"
    assert len(call_kwargs["prices"]) == 1
    # 220 000 UZS * 100 = 22 000 000 tiyin
    assert call_kwargs["prices"][0].amount == 22000000


@pytest.mark.asyncio
async def test_send_order_invoice_fallback_when_token_empty(empty_token_config):
    """When provider token is missing, falls back to graceful text message without raising error."""
    from handlers.payments import send_order_invoice

    bot = MagicMock(spec=Bot)
    bot.send_invoice = AsyncMock()
    bot.send_message = AsyncMock()

    order = {
        "id": 105,
        "total_amount": 95000,
    }

    await send_order_invoice(
        bot=bot,
        chat_id=1234567,
        order=order,
        provider="click",
        config=empty_token_config,
        lang="uz",
    )

    bot.send_invoice.assert_not_called()
    bot.send_message.assert_awaited_once()
    call_kwargs = bot.send_message.call_args[1]

    assert call_kwargs["chat_id"] == 1234567
    text = call_kwargs["text"].lower()
    assert ("test" in text or "demo" in text or "qabul" in text or "naqd" in text or "karta" in text)
    assert call_kwargs.get("reply_markup") is not None


# ============================================================================
# 3. PreCheckoutQuery Handler Tests
# ============================================================================

@pytest.mark.asyncio
async def test_pre_checkout_query_valid_order(memory_db):
    """PreCheckoutQuery responds ok=True when the order exists and is valid."""
    from handlers.payments import handle_pre_checkout_query

    # Create an order in DB
    order_id = await crud.create_order(
        db=memory_db,
        user_id=1001,
        order_type="standard",
        total_amount=100000,
        delivery_cost=12000,
        delivery_type="delivery",
        target_time="hozir",
        address="Amir Temur 10",
        latitude=41.31,
        longitude=69.24,
        distance_km=2.5,
        phone="+998901234567",
        custom_note=None,
        payment_type="click",
    )

    query = MagicMock(spec=PreCheckoutQuery)
    query.id = "pcq_123"
    query.invoice_payload = f"order_{order_id}"
    query.from_user = User(id=1001, is_bot=False, first_name="Ali")
    query.answer = AsyncMock()

    await handle_pre_checkout_query(
        query=query,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    query.answer.assert_awaited_once_with(ok=True)


@pytest.mark.asyncio
async def test_pre_checkout_query_nonexistent_order(memory_db):
    """PreCheckoutQuery responds ok=False with error_message if order does not exist."""
    from handlers.payments import handle_pre_checkout_query

    query = MagicMock(spec=PreCheckoutQuery)
    query.id = "pcq_999"
    query.invoice_payload = "order_999999"
    query.from_user = User(id=1001, is_bot=False, first_name="Ali")
    query.answer = AsyncMock()

    await handle_pre_checkout_query(
        query=query,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    query.answer.assert_awaited_once()
    args, kwargs = query.answer.call_args
    assert kwargs.get("ok") is False
    assert kwargs.get("error_message") is not None
    assert len(kwargs.get("error_message")) > 0


@pytest.mark.asyncio
async def test_pre_checkout_query_invalid_payload_format(memory_db):
    """PreCheckoutQuery responds ok=False if payload is malformed."""
    from handlers.payments import handle_pre_checkout_query

    query = MagicMock(spec=PreCheckoutQuery)
    query.id = "pcq_bad"
    query.invoice_payload = "invalid_format_string"
    query.from_user = User(id=1001, is_bot=False, first_name="Ali")
    query.answer = AsyncMock()

    await handle_pre_checkout_query(
        query=query,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    query.answer.assert_awaited_once()
    _, kwargs = query.answer.call_args
    assert kwargs.get("ok") is False
    assert kwargs.get("error_message") is not None


@pytest.mark.asyncio
async def test_pre_checkout_query_cancelled_order(memory_db):
    """PreCheckoutQuery responds ok=False if the order was cancelled."""
    from handlers.payments import handle_pre_checkout_query

    order_id = await crud.create_order(
        db=memory_db,
        user_id=1001,
        order_type="standard",
        total_amount=100000,
        delivery_cost=12000,
        delivery_type="delivery",
        target_time="hozir",
        address="Toshkent",
        latitude=None,
        longitude=None,
        distance_km=0.0,
        phone="+998901234567",
        custom_note=None,
        payment_type="click",
    )
    await crud.update_order_status(memory_db, order_id=order_id, status="cancelled")

    query = MagicMock(spec=PreCheckoutQuery)
    query.id = "pcq_cancelled"
    query.invoice_payload = f"order_{order_id}"
    query.from_user = User(id=1001, is_bot=False, first_name="Ali")
    query.answer = AsyncMock()

    await handle_pre_checkout_query(
        query=query,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    query.answer.assert_awaited_once()
    _, kwargs = query.answer.call_args
    assert kwargs.get("ok") is False


@pytest.mark.asyncio
async def test_pre_checkout_query_already_paid_order(memory_db):
    """PreCheckoutQuery responds ok=False if the order is already marked as paid."""
    from handlers.payments import handle_pre_checkout_query

    order_id = await crud.create_order(
        db=memory_db,
        user_id=1001,
        order_type="standard",
        total_amount=100000,
        delivery_cost=12000,
        delivery_type="delivery",
        target_time="hozir",
        address="Toshkent",
        latitude=None,
        longitude=None,
        distance_km=0.0,
        phone="+998901234567",
        custom_note=None,
        payment_type="click",
    )
    await crud.update_payment_status(memory_db, order_id=order_id, payment_status="paid")

    query = MagicMock(spec=PreCheckoutQuery)
    query.id = "pcq_already_paid"
    query.invoice_payload = f"order_{order_id}"
    query.from_user = User(id=1001, is_bot=False, first_name="Ali")
    query.answer = AsyncMock()

    await handle_pre_checkout_query(
        query=query,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    query.answer.assert_awaited_once()
    _, kwargs = query.answer.call_args
    assert kwargs.get("ok") is False


# ============================================================================
# 4. SuccessfulPayment Handler Tests
# ============================================================================

@pytest.mark.asyncio
async def test_successful_payment_updates_order_and_confirms(memory_db):
    """SuccessfulPayment handler marks order payment_status='paid' and sends confirmation with main menu."""
    from handlers.payments import handle_successful_payment

    order_id = await crud.create_order(
        db=memory_db,
        user_id=1002,
        order_type="standard",
        total_amount=180000,
        delivery_cost=0,
        delivery_type="pickup",
        target_time="hozir",
        address=None,
        latitude=None,
        longitude=None,
        distance_km=0.0,
        phone="+998901112233",
        custom_note="Olib ketish",
        payment_type="click",
    )

    initial_order = await crud.get_order(memory_db, order_id)
    assert initial_order["payment_status"] == "pending"

    # Construct mock SuccessfulPayment message
    sp = MagicMock(spec=SuccessfulPayment)
    sp.currency = "UZS"
    sp.total_amount = 18000000
    sp.invoice_payload = f"order_{order_id}"
    sp.provider_payment_charge_id = "click_tx_12345"
    sp.telegram_payment_charge_id = "tg_tx_67890"

    message = MagicMock(spec=Message)
    message.from_user = User(id=1002, is_bot=False, first_name="Nodir")
    message.chat = Chat(id=1002, type="private")
    message.successful_payment = sp
    message.answer = AsyncMock()

    await handle_successful_payment(
        message=message,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    # 1. Verify DB order updated to paid
    updated_order = await crud.get_order(memory_db, order_id)
    assert updated_order["payment_status"] == "paid"

    # 2. Verify confirmation message answered with main_menu_kb
    message.answer.assert_awaited_once()
    msg_args, msg_kwargs = message.answer.call_args
    receipt_text = msg_args[0] if msg_args else msg_kwargs.get("text", "")

    assert str(order_id) in receipt_text
    assert ("to'lov" in receipt_text.lower() or "muvaffaqiyatli" in receipt_text.lower() or "qabul" in receipt_text.lower())
    assert msg_kwargs.get("reply_markup") is not None


@pytest.mark.asyncio
async def test_successful_payment_russian_localization(memory_db):
    """SuccessfulPayment handler correctly formats receipt message in Russian."""
    from handlers.payments import handle_successful_payment

    order_id = await crud.create_order(
        db=memory_db,
        user_id=1005,
        order_type="standard",
        total_amount=70000,
        delivery_cost=12000,
        delivery_type="delivery",
        target_time="hozir",
        address="Tashkent",
        latitude=None,
        longitude=None,
        distance_km=0.0,
        phone="+998909998877",
        custom_note=None,
        payment_type="payme",
    )

    sp = MagicMock(spec=SuccessfulPayment)
    sp.currency = "UZS"
    sp.total_amount = 8200000
    sp.invoice_payload = f"order_{order_id}"
    sp.provider_payment_charge_id = "payme_tx_555"
    sp.telegram_payment_charge_id = "tg_tx_999"

    message = MagicMock(spec=Message)
    message.from_user = User(id=1005, is_bot=False, first_name="Dmitriy")
    message.chat = Chat(id=1005, type="private")
    message.successful_payment = sp
    message.answer = AsyncMock()

    await handle_successful_payment(
        message=message,
        db=memory_db,
        lang="ru",
        _t=fake_t("ru"),
    )

    updated_order = await crud.get_order(memory_db, order_id)
    assert updated_order["payment_status"] == "paid"

    message.answer.assert_awaited_once()
    msg_args, msg_kwargs = message.answer.call_args
    receipt_text = msg_args[0] if msg_args else msg_kwargs.get("text", "")

    assert str(order_id) in receipt_text
    assert ("оплата" in receipt_text.lower() or "принята" in receipt_text.lower() or "заказ" in receipt_text.lower())
