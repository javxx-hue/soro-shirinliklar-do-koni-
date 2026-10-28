"""
Unit and integration tests for the Order Placement FSM flow (handlers/order.py).
"""
import pytest
import aiosqlite
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Message, Location, Contact

from shop_config import Config
from database.db import init_db
from database import crud
from middlewares.i18n import get_text
from keyboards.inline import order_time_kb, delivery_type_kb, payment_methods_kb, order_confirm_kb
from keyboards.reply import location_request_kb, phone_request_kb, skip_or_cancel_kb, main_menu_kb


@pytest.fixture
def test_config():
    """Default shop configuration for testing."""
    return Config(
        bot_token="123456:TEST_TOKEN",
        admin_ids=[9999],
        store_lat=41.311081,
        store_lon=69.240562,
        base_delivery_price=12000,
        price_per_km=2500,
        free_delivery_threshold=250000,
        work_start="09:00",
        work_end="22:00",
    )


@pytest.fixture
async def memory_db():
    """In-memory SQLite database initialized with tables and sample data."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    await init_db(db)
    yield db
    await db.close()


def fake_t(lang="uz"):
    """Helper to mock i18n translation callable."""
    return lambda key, **kwargs: get_text(key, lang=kwargs.pop("lang", lang), **kwargs)


def make_fsm_context(user_id: int = 1001, chat_id: int = 1001) -> FSMContext:
    """Creates a real FSMContext with in-memory storage."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


# ============================================================================
# 1. Router & FSM Definition Tests
# ============================================================================

def test_order_router_and_fsm_definition():
    """Verify order_router is defined and OrderFSM has all required states."""
    from handlers.order import order_router, OrderFSM
    from handlers import order_router as exported_router

    assert isinstance(order_router, Router)
    assert order_router.name == "order"
    assert exported_router is order_router

    # Verify all 8 states exist
    assert hasattr(OrderFSM, "waiting_for_time")
    assert hasattr(OrderFSM, "waiting_for_preorder_time")
    assert hasattr(OrderFSM, "waiting_for_delivery_type")
    assert hasattr(OrderFSM, "waiting_for_location")
    assert hasattr(OrderFSM, "waiting_for_phone")
    assert hasattr(OrderFSM, "waiting_for_note")
    assert hasattr(OrderFSM, "waiting_for_payment")
    assert hasattr(OrderFSM, "confirmation")


# ============================================================================
# 2. Checkout Entry Handler Tests
# ============================================================================

@pytest.mark.asyncio
async def test_start_checkout_empty_cart_alerts_user(memory_db, test_config):
    """When cart is empty, user is alerted and FSM is not started."""
    from handlers.order import start_order_checkout

    user_id = 1002
    state = make_fsm_context(user_id=user_id)

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "order_checkout"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock(spec=Message)
    callback.answer = AsyncMock()

    await start_order_checkout(
        callback,
        db=memory_db,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
        config=test_config,
    )

    callback.answer.assert_called_once()
    assert get_text("cart_empty", "uz") in callback.answer.call_args[0][0]
    assert callback.answer.call_args[1].get("show_alert") is True
    assert await state.get_state() is None


@pytest.mark.asyncio
async def test_start_checkout_populated_cart_initiates_fsm(memory_db, test_config):
    """When cart has items, prompts for time and sets waiting_for_time state."""
    from handlers.order import start_order_checkout, OrderFSM

    user_id = 1003
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=2)
    state = make_fsm_context(user_id=user_id)

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "order_checkout"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await start_order_checkout(
        callback,
        db=memory_db,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
        config=test_config,
    )

    callback.answer.assert_called_once()
    callback.message.edit_text.assert_called_once()
    text = callback.message.edit_text.call_args[0][0]
    assert get_text("order_time_prompt", "uz") in text
    assert await state.get_state() == OrderFSM.waiting_for_time.state

    data = await state.get_data()
    assert data["cart_total"] == 300000  # 150 000 * 2


# ============================================================================
# 3. Step 1: Time Selection Tests
# ============================================================================

@pytest.mark.asyncio
async def test_time_now_selection(memory_db, test_config):
    """Selecting 'now' sets target_time to 'hozir' and moves to waiting_for_delivery_type."""
    from handlers.order import handle_order_time, OrderFSM

    user_id = 1004
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_time)
    await state.update_data(cart_total=150000)

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "order_time:now"
    callback.from_user = MagicMock(id=user_id)
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await handle_order_time(
        callback,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
        config=test_config,
    )

    callback.answer.assert_called_once()
    assert await state.get_state() == OrderFSM.waiting_for_delivery_type.state
    data = await state.get_data()
    assert data["target_time"] == "hozir"
    text = callback.message.edit_text.call_args[0][0]
    assert get_text("order_delivery_type_prompt", "uz") in text


@pytest.mark.asyncio
async def test_time_scheduled_selection_and_input(memory_db, test_config):
    """Selecting 'scheduled' prompts for custom date/time text, which advances to delivery type."""
    from handlers.order import handle_order_time, handle_preorder_time_input, OrderFSM

    user_id = 1005
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_time)

    # 1. Click scheduled button
    callback = MagicMock(spec=CallbackQuery)
    callback.data = "order_time:scheduled"
    callback.from_user = MagicMock(id=user_id)
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await handle_order_time(
        callback,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
        config=test_config,
    )

    assert await state.get_state() == OrderFSM.waiting_for_preorder_time.state
    text = callback.message.edit_text.call_args[0][0]
    assert get_text("order_time_input_prompt", "uz") in text

    # 2. User enters date and time string
    message = MagicMock(spec=Message)
    message.text = "Ertaga soat 17:00 ga"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_preorder_time_input(
        message,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
    )

    assert await state.get_state() == OrderFSM.waiting_for_delivery_type.state
    data = await state.get_data()
    assert data["target_time"] == "Ertaga soat 17:00 ga"
    assert get_text("order_delivery_type_prompt", "uz") in message.answer.call_args[0][0]


# ============================================================================
# 4. Step 2: Delivery Type Selection Tests
# ============================================================================

@pytest.mark.asyncio
async def test_delivery_type_courier(memory_db, test_config):
    """Courier choice moves to waiting_for_location with location_request_kb."""
    from handlers.order import handle_delivery_type, OrderFSM

    user_id = 1006
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_delivery_type)

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "delivery_type:delivery"
    callback.from_user = MagicMock(id=user_id)
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()

    await handle_delivery_type(
        callback,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
    )

    assert await state.get_state() == OrderFSM.waiting_for_location.state
    data = await state.get_data()
    assert data["delivery_type"] == "delivery"
    callback.message.answer.assert_called_once()
    text = callback.message.answer.call_args[0][0]
    assert get_text("order_location_prompt", "uz") in text


@pytest.mark.asyncio
async def test_delivery_type_pickup_skips_location(memory_db, test_config):
    """Pickup choice sets cost=0, distance=0, address='Do'kondan olib ketish' and moves to phone."""
    from handlers.order import handle_delivery_type, OrderFSM

    user_id = 1007
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_delivery_type)

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "delivery_type:pickup"
    callback.from_user = MagicMock(id=user_id)
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()

    await handle_delivery_type(
        callback,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
    )

    assert await state.get_state() == OrderFSM.waiting_for_phone.state
    data = await state.get_data()
    assert data["delivery_type"] == "pickup"
    assert data["delivery_cost"] == 0
    assert data["distance_km"] == 0
    assert data["address"] == "Do'kondan olib ketish"
    assert get_text("order_phone_prompt", "uz") in callback.message.answer.call_args[0][0]


# ============================================================================
# 5. Step 3: Location Tests
# ============================================================================

@pytest.mark.asyncio
async def test_location_gps_with_delivery_fee(memory_db, test_config):
    """GPS location calculates distance, delivery cost, and advances to waiting_for_phone."""
    from handlers.order import handle_location_input, OrderFSM

    user_id = 1008
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_location)
    await state.update_data(cart_total=100000)

    # Coords ~6.1 km away from store (41.311081, 69.240562)
    message = MagicMock(spec=Message)
    message.location = Location(latitude=41.350000, longitude=69.290000)
    message.text = None
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_location_input(
        message,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
        config=test_config,
    )

    assert await state.get_state() == OrderFSM.waiting_for_phone.state
    data = await state.get_data()
    assert data["distance_km"] > 0
    assert data["delivery_cost"] > test_config.base_delivery_price
    assert "maps.google.com" in data["address"]
    text = message.answer.call_args[0][0]
    assert get_text("order_phone_prompt", "uz") in text


@pytest.mark.asyncio
async def test_location_gps_free_delivery_threshold(memory_db, test_config):
    """When cart_total >= free_delivery_threshold, delivery_cost is 0 and congratulations shown."""
    from handlers.order import handle_location_input, OrderFSM

    user_id = 1009
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_location)
    await state.update_data(cart_total=300000)  # > 250 000

    message = MagicMock(spec=Message)
    message.location = Location(latitude=41.350000, longitude=69.290000)
    message.text = None
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_location_input(
        message,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
        config=test_config,
    )

    assert await state.get_state() == OrderFSM.waiting_for_phone.state
    data = await state.get_data()
    assert data["delivery_cost"] == 0
    text = message.answer.call_args[0][0]
    assert get_text("delivery_free_congrats", "uz") in text


@pytest.mark.asyncio
async def test_location_text_address(memory_db, test_config):
    """Text address sets address string, base delivery cost, and advances to waiting_for_phone."""
    from handlers.order import handle_location_input, OrderFSM

    user_id = 1010
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_location)
    await state.update_data(cart_total=100000)

    message = MagicMock(spec=Message)
    message.location = None
    message.text = "Toshkent sh., Yunusobod 14, 25-uy"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_location_input(
        message,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
        config=test_config,
    )

    assert await state.get_state() == OrderFSM.waiting_for_phone.state
    data = await state.get_data()
    assert data["address"] == "Toshkent sh., Yunusobod 14, 25-uy"
    assert data["delivery_cost"] == test_config.base_delivery_price
    text = message.answer.call_args[0][0]
    assert get_text("order_phone_prompt", "uz") in text


# ============================================================================
# 6. Step 4: Phone Input Tests
# ============================================================================

@pytest.mark.asyncio
async def test_phone_input_contact_and_save_db(memory_db):
    """Phone via contact updates user in DB, stores phone, and advances to waiting_for_note."""
    from handlers.order import handle_phone_input, OrderFSM

    user_id = 1011
    await crud.upsert_user(memory_db, telegram_id=user_id, full_name="Vali Ali")
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_phone)

    message = MagicMock(spec=Message)
    message.contact = Contact(phone_number="+998901112233", first_name="Vali")
    message.text = None
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_phone_input(
        message,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    assert await state.get_state() == OrderFSM.waiting_for_note.state
    data = await state.get_data()
    assert data["phone"] == "+998901112233"

    user_in_db = await crud.get_user(memory_db, user_id)
    assert user_in_db["phone"] == "+998901112233"

    text = message.answer.call_args[0][0]
    assert get_text("order_note_prompt", "uz") in text


@pytest.mark.asyncio
async def test_phone_input_text_format(memory_db):
    """Phone via text string updates user in DB and moves to waiting_for_note."""
    from handlers.order import handle_phone_input, OrderFSM

    user_id = 1012
    await crud.upsert_user(memory_db, telegram_id=user_id, full_name="Guli")
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_phone)

    message = MagicMock(spec=Message)
    message.contact = None
    message.text = "+998939998877"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_phone_input(
        message,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    assert await state.get_state() == OrderFSM.waiting_for_note.state
    data = await state.get_data()
    assert data["phone"] == "+998939998877"


# ============================================================================
# 7. Step 5: Cake Note / Tabriknoma Tests
# ============================================================================

@pytest.mark.asyncio
async def test_note_custom_text(memory_db):
    """Providing a custom greeting note saves note and moves to waiting_for_payment."""
    from handlers.order import handle_note_input, OrderFSM

    user_id = 1013
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_note)

    message = MagicMock(spec=Message)
    message.text = "Tug'ilgan kuningiz bilan, onajon!"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_note_input(
        message,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
    )

    assert await state.get_state() == OrderFSM.waiting_for_payment.state
    data = await state.get_data()
    assert data["custom_note"] == "Tug'ilgan kuningiz bilan, onajon!"
    text = message.answer.call_args[0][0]
    assert get_text("order_payment_prompt", "uz") in text


@pytest.mark.asyncio
async def test_note_skip_button(memory_db):
    """Clicking skip sets custom_note to None and moves to waiting_for_payment."""
    from handlers.order import handle_note_input, OrderFSM

    user_id = 1014
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_note)

    message = MagicMock(spec=Message)
    message.text = get_text("btn_skip", "uz")
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_note_input(
        message,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
    )

    assert await state.get_state() == OrderFSM.waiting_for_payment.state
    data = await state.get_data()
    assert data["custom_note"] is None


# ============================================================================
# 8. Step 6: Payment Selection & Order Summary Tests
# ============================================================================

@pytest.mark.asyncio
async def test_payment_method_displays_full_summary(memory_db):
    """Selecting payment compiles summary receipt with all order details and confirm kb."""
    from handlers.order import handle_payment_method, OrderFSM

    user_id = 1015
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=1)  # 150 000
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_payment)
    await state.update_data(
        cart_total=150000,
        delivery_type="delivery",
        target_time="hozir",
        address="Toshkent, Mustaqillik shoh ko'chasi 1",
        latitude=41.31,
        longitude=69.25,
        distance_km=2.5,
        delivery_cost=12000,
        phone="+998901112233",
        custom_note="Tabrik bilan",
    )

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "pay_method:click"
    callback.from_user = MagicMock(id=user_id)
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await handle_payment_method(
        callback,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    callback.answer.assert_called_once()
    assert await state.get_state() == OrderFSM.confirmation.state
    data = await state.get_data()
    assert data["payment_type"] == "click"

    # Verify summary message contains crucial receipt components
    summary_text = (
        callback.message.edit_text.call_args[0][0]
        if callback.message.edit_text.called
        else callback.message.answer.call_args[0][0]
    )
    assert "150 000" in summary_text
    assert "12 000" in summary_text
    assert "162 000" in summary_text
    assert "+998901112233" in summary_text
    assert "Tabrik bilan" in summary_text


# ============================================================================
# 9. Step 7: Order Confirmation & DB Persistence Tests
# ============================================================================

@pytest.mark.asyncio
async def test_order_confirmation_persists_to_db_and_clears_cart(memory_db):
    """Confirming creates order in DB, clears cart, resets FSM, and sends success message."""
    from handlers.order import handle_order_confirmation, OrderFSM

    user_id = 1016
    await crud.upsert_user(memory_db, telegram_id=user_id, full_name="Botir")
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=2)  # 300 000
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.confirmation)
    await state.update_data(
        cart_total=300000,
        delivery_type="delivery",
        target_time="hozir",
        address="Toshkent, Chilonzor 1-mavze",
        latitude=41.28,
        longitude=69.21,
        distance_km=4.0,
        delivery_cost=14500,
        phone="+998971234567",
        custom_note="Ehtiyotkorlik bilan",
        payment_type="cash",
    )

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "order_confirm:yes"
    callback.from_user = MagicMock(id=user_id)
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()

    await handle_order_confirmation(
        callback,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()

    # 1. State cleared
    assert await state.get_state() is None

    # 2. Cart cleared in DB
    remaining_cart = await crud.get_cart(memory_db, user_id=user_id)
    assert len(remaining_cart) == 0

    # 3. Order created in DB
    orders = await crud.get_user_orders(memory_db, user_id=user_id)
    assert len(orders) == 1
    new_order = orders[0]
    assert new_order["user_id"] == user_id
    assert new_order["total_amount"] == 314500
    assert new_order["delivery_cost"] == 14500
    assert new_order["delivery_type"] == "delivery"
    assert new_order["phone"] == "+998971234567"
    assert new_order["custom_note"] == "Ehtiyotkorlik bilan"
    assert new_order["payment_type"] == "cash"
    assert new_order["status"] == "new"

    # 4. Success message sent with order id
    sent_text = callback.message.answer.call_args[0][0]
    assert f"#{new_order['id']}" in sent_text


# ============================================================================
# 10. Cancellation Tests
# ============================================================================

@pytest.mark.asyncio
async def test_order_cancellation_callback(memory_db):
    """Canceling via inline callback resets FSM and sends cancellation message."""
    from handlers.order import handle_order_cancellation, OrderFSM

    user_id = 1017
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_location)
    await state.update_data(target_time="hozir")

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "order_cancel"
    callback.from_user = MagicMock(id=user_id)
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()

    await handle_order_cancellation(
        callback,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    callback.answer.assert_called_once()
    assert await state.get_state() is None
    callback.message.answer.assert_called_once()
    sent_text = callback.message.answer.call_args[0][0]
    assert get_text("action_cancelled", "uz") in sent_text


@pytest.mark.asyncio
async def test_order_cancellation_reply_message(memory_db):
    """Canceling via reply text button resets FSM and restores main menu."""
    from handlers.order import handle_order_cancellation, OrderFSM

    user_id = 1018
    state = make_fsm_context(user_id=user_id)
    await state.set_state(OrderFSM.waiting_for_phone)

    message = MagicMock(spec=Message)
    message.text = get_text("cancel_btn", "uz")
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_order_cancellation(
        message,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    assert await state.get_state() is None
    message.answer.assert_called_once()
    sent_text = message.answer.call_args[0][0]
    assert get_text("action_cancelled", "uz") in sent_text


# ============================================================================
# 11. Full End-to-End Pickup Flow Integration Test
# ============================================================================

@pytest.mark.asyncio
async def test_full_pickup_flow(memory_db, test_config):
    """
    End-to-end integration test of self-pickup order flow:
    Checkout -> Scheduled time -> Pickup -> Phone -> Skip note -> Payme -> Confirm -> Order in DB.
    """
    from handlers.order import (
        start_order_checkout,
        handle_order_time,
        handle_preorder_time_input,
        handle_delivery_type,
        handle_phone_input,
        handle_note_input,
        handle_payment_method,
        handle_order_confirmation,
        OrderFSM,
    )

    user_id = 2001
    await crud.upsert_user(memory_db, telegram_id=user_id, full_name="Shaxzod")
    # Add product 1 (150 000) and product 6 (25 000)
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=1)
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=6, quantity=2)  # Total = 200 000
    state = make_fsm_context(user_id=user_id)

    # 1. Start checkout
    cb_start = MagicMock(spec=CallbackQuery, data="order_checkout", from_user=MagicMock(id=user_id))
    cb_start.message = MagicMock(spec=Message, edit_text=AsyncMock(), answer=AsyncMock())
    cb_start.answer = AsyncMock()
    await start_order_checkout(cb_start, db=memory_db, state=state, lang="uz", _t=fake_t("uz"), config=test_config)
    assert await state.get_state() == OrderFSM.waiting_for_time.state

    # 2. Choose scheduled preorder
    cb_time = MagicMock(spec=CallbackQuery, data="order_time:scheduled", from_user=MagicMock(id=user_id))
    cb_time.message = MagicMock(spec=Message, edit_text=AsyncMock())
    cb_time.answer = AsyncMock()
    await handle_order_time(cb_time, state=state, lang="uz", _t=fake_t("uz"), config=test_config)
    assert await state.get_state() == OrderFSM.waiting_for_preorder_time.state

    # 3. Enter target time
    msg_time = MagicMock(spec=Message, text="30-oktabr 14:00", from_user=MagicMock(id=user_id), answer=AsyncMock())
    await handle_preorder_time_input(msg_time, state=state, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.waiting_for_delivery_type.state

    # 4. Choose pickup (samovivoz)
    cb_del = MagicMock(spec=CallbackQuery, data="delivery_type:pickup", from_user=MagicMock(id=user_id))
    cb_del.message = MagicMock(spec=Message, answer=AsyncMock())
    cb_del.answer = AsyncMock()
    await handle_delivery_type(cb_del, state=state, lang="uz", _t=fake_t("uz"))
    # Skips location directly to phone!
    assert await state.get_state() == OrderFSM.waiting_for_phone.state

    # 5. Provide phone
    msg_phone = MagicMock(spec=Message, text="+998909876543", contact=None, from_user=MagicMock(id=user_id), answer=AsyncMock())
    await handle_phone_input(msg_phone, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.waiting_for_note.state

    # 6. Skip note
    msg_note = MagicMock(spec=Message, text=get_text("btn_skip", "uz"), from_user=MagicMock(id=user_id), answer=AsyncMock())
    await handle_note_input(msg_note, state=state, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.waiting_for_payment.state

    # 7. Select Payme
    cb_pay = MagicMock(spec=CallbackQuery, data="pay_method:payme", from_user=MagicMock(id=user_id))
    cb_pay.message = MagicMock(spec=Message, edit_text=AsyncMock(), answer=AsyncMock())
    cb_pay.answer = AsyncMock()
    await handle_payment_method(cb_pay, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.confirmation.state

    # 8. Confirm order
    cb_confirm = MagicMock(spec=CallbackQuery, data="order_confirm:yes", from_user=MagicMock(id=user_id))
    cb_confirm.message = MagicMock(spec=Message, answer=AsyncMock())
    cb_confirm.answer = AsyncMock()
    await handle_order_confirmation(cb_confirm, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))

    # Assertions
    assert await state.get_state() is None
    orders = await crud.get_user_orders(memory_db, user_id=user_id)
    assert len(orders) == 1
    order = orders[0]
    assert order["delivery_type"] == "pickup"
    assert order["delivery_cost"] == 0
    assert order["distance_km"] == 0
    assert order["address"] == "Do'kondan olib ketish"
    assert order["target_time"] == "30-oktabr 14:00"
    assert order["payment_type"] == "payme"
    assert order["total_amount"] == 200000
    assert order["custom_note"] is None


# ============================================================================
# 12. Full End-to-End Courier Flow Integration Test
# ============================================================================

@pytest.mark.asyncio
async def test_full_courier_flow(memory_db, test_config):
    """
    End-to-end integration test of courier delivery order flow:
    Checkout -> Time now -> Courier -> GPS Location -> Phone Contact -> Custom Note -> Cash -> Confirm.
    """
    from handlers.order import (
        start_order_checkout,
        handle_order_time,
        handle_delivery_type,
        handle_location_input,
        handle_phone_input,
        handle_note_input,
        handle_payment_method,
        handle_order_confirmation,
        OrderFSM,
    )

    user_id = 3001
    await crud.upsert_user(memory_db, telegram_id=user_id, full_name="Jasur")
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=2)  # 300 000
    state = make_fsm_context(user_id=user_id)

    # 1. Message checkout
    msg_start = MagicMock(spec=Message, text="✅ Buyurtma berish", from_user=MagicMock(id=user_id), answer=AsyncMock())
    await start_order_checkout(msg_start, db=memory_db, state=state, lang="uz", _t=fake_t("uz"), config=test_config)
    assert await state.get_state() == OrderFSM.waiting_for_time.state

    # 2. Now
    cb_time = MagicMock(spec=CallbackQuery, data="order_time:now", from_user=MagicMock(id=user_id))
    cb_time.message = MagicMock(spec=Message, edit_text=AsyncMock(), answer=AsyncMock())
    cb_time.answer = AsyncMock()
    await handle_order_time(cb_time, state=state, lang="uz", _t=fake_t("uz"), config=test_config)
    assert await state.get_state() == OrderFSM.waiting_for_delivery_type.state

    # 3. Courier delivery
    cb_del = MagicMock(spec=CallbackQuery, data="delivery_type:delivery", from_user=MagicMock(id=user_id))
    cb_del.message = MagicMock(spec=Message, answer=AsyncMock())
    cb_del.answer = AsyncMock()
    await handle_delivery_type(cb_del, state=state, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.waiting_for_location.state

    # 4. GPS Location
    msg_loc = MagicMock(
        spec=Message,
        location=Location(latitude=41.350000, longitude=69.290000),
        text=None,
        from_user=MagicMock(id=user_id),
        answer=AsyncMock(),
    )
    await handle_location_input(msg_loc, state=state, db=memory_db, lang="uz", _t=fake_t("uz"), config=test_config)
    assert await state.get_state() == OrderFSM.waiting_for_phone.state

    # 5. Phone contact
    msg_contact = MagicMock(
        spec=Message,
        contact=Contact(phone_number="+998901234567", first_name="Jasur"),
        text=None,
        from_user=MagicMock(id=user_id),
        answer=AsyncMock(),
    )
    await handle_phone_input(msg_contact, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.waiting_for_note.state

    # 6. Note
    msg_note = MagicMock(
        spec=Message,
        text="Onam uchun maxsus bezatib bering",
        from_user=MagicMock(id=user_id),
        answer=AsyncMock(),
    )
    await handle_note_input(msg_note, state=state, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.waiting_for_payment.state

    # 7. Cash payment
    cb_pay = MagicMock(spec=CallbackQuery, data="pay_method:cash", from_user=MagicMock(id=user_id))
    cb_pay.message = MagicMock(spec=Message, edit_text=AsyncMock(), answer=AsyncMock())
    cb_pay.answer = AsyncMock()
    await handle_payment_method(cb_pay, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.confirmation.state

    # 8. Confirm
    cb_confirm = MagicMock(spec=CallbackQuery, data="order_confirm:yes", from_user=MagicMock(id=user_id))
    cb_confirm.message = MagicMock(spec=Message, answer=AsyncMock())
    cb_confirm.answer = AsyncMock()
    await handle_order_confirmation(cb_confirm, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))

    # Assertions
    assert await state.get_state() is None
    orders = await crud.get_user_orders(memory_db, user_id=user_id)
    assert len(orders) == 1
    order = orders[0]
    assert order["delivery_type"] == "delivery"
    # Cart total was 300 000 >= 250 000 threshold -> delivery_cost is 0!
    assert order["delivery_cost"] == 0
    assert order["total_amount"] == 300000
    assert order["target_time"] == "hozir"
    assert order["phone"] == "+998901234567"
    assert order["custom_note"] == "Onam uchun maxsus bezatib bering"
    assert order["payment_type"] == "cash"
    assert order["status"] == "new"
