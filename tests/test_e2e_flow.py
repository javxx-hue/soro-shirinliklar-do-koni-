"""
Comprehensive End-to-End (E2E) Integration Tests for Shirinliklar Xonadoni Telegram Bot.
Covers the entire lifecycle across all subsystems:
1. Customer onboarding, catalog browsing, cart operations, delivery calculation,
   personalized cake notes, cash checkout, DB persistence, and full admin order lifecycle.
2. Custom cake request with photo upload, filling/weight details, date/phone, and DB quote state.
3. Grounded AI Sommelier ("Shirinlik Somelyesi") consultation with live database products and navigation.
4. Telegram Payments flow with PreCheckoutQuery validation, SuccessfulPayment processing, and receipt generation.
"""
from __future__ import annotations

import aiosqlite
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    Chat,
    Contact,
    Location,
    Message,
    PhotoSize,
    PreCheckoutQuery,
    SuccessfulPayment,
    User,
)

from database import crud
from database.db import init_db
from handlers.admin.orders import handle_admin_order_callback
from handlers.ai_consultant import (
    AIConsultantFSM,
    handle_ai_open_catalog,
    open_ai_consultant_message,
    process_ai_query,
)
from handlers.cart import open_cart_message
from handlers.catalog import (
    handle_card_cart_action,
    open_catalog_message,
    show_category_products,
    show_product_card,
)
from handlers.common import set_language_callback, start_handler
from handlers.custom_cake import (
    CustomCakeFSM,
    handle_custom_cake_confirmation,
    handle_custom_cake_details,
    handle_custom_cake_phone,
    handle_custom_cake_photo,
    handle_custom_cake_target_time,
    start_custom_cake,
)
from handlers.order import (
    OrderFSM,
    handle_delivery_type,
    handle_location_input,
    handle_note_input,
    handle_order_confirmation,
    handle_order_time,
    handle_payment_method,
    handle_phone_input,
    start_order_checkout,
)
from handlers.payments import handle_pre_checkout_query, handle_successful_payment
from middlewares.i18n import get_text, load_locales
from shop_config import Config


@pytest.fixture(autouse=True)
def reload_translations():
    """Ensure translations cache is fresh before tests."""
    load_locales()


@pytest.fixture
def test_config() -> Config:
    """Shop configuration with test store coordinates, thresholds, and admin IDs."""
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
        click_token="TEST_CLICK_PROVIDER_TOKEN",
        payme_token="TEST_PAYME_PROVIDER_TOKEN",
        gemini_api_key="",
    )


@pytest.fixture
async def memory_db():
    """In-memory SQLite database initialized with schemas, categories, and seeded products."""
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
    """Creates an isolated in-memory FSMContext for deterministic state tracking."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


# ============================================================================
# 1. End-to-End Customer Order and Full Admin Lifecycle
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_customer_order_and_admin_lifecycle(memory_db, test_config):
    """
    End-to-End Journey 1: Customer Onboarding -> Catalog Browsing -> Cart -> Checkout ->
    Delivery calculation -> Note -> Cash payment -> Order Confirmation -> Admin Order Progression.
    """
    customer_id = 5001
    admin_id = test_config.admin_ids[0]

    # ------------------------------------------------------------------------
    # Step 1: Start Bot with /start -> Select Uzbek language
    # ------------------------------------------------------------------------
    start_msg = MagicMock(spec=Message)
    start_msg.from_user = User(id=customer_id, is_bot=False, first_name="Ali", username="alivali")
    start_msg.text = "/start"
    start_msg.answer = AsyncMock()

    await start_handler(
        start_msg,
        db=memory_db,
        config=test_config,
        lang="uz",
        _t=fake_t("uz"),
    )

    # First-time user is prompted for language selection
    start_msg.answer.assert_called_once()
    assert get_text("choose_language", "uz") in start_msg.answer.call_args[0][0]
    assert start_msg.answer.call_args[1].get("reply_markup") is not None

    # Customer chooses Uzbek
    cb_lang = MagicMock(spec=CallbackQuery)
    cb_lang.data = "set_lang:uz"
    cb_lang.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    cb_lang.message = MagicMock(spec=Message, answer=AsyncMock())
    cb_lang.answer = AsyncMock()

    await set_language_callback(cb_lang, db=memory_db, config=test_config, _t=fake_t("uz"))

    # Verify user profile in DB
    user_db = await crud.get_user(memory_db, customer_id)
    assert user_db is not None
    assert user_db["language"] == "uz"
    cb_lang.answer.assert_called_once()
    cb_lang.message.answer.assert_called_once()
    assert get_text("welcome_msg", "uz") in cb_lang.message.answer.call_args[0][0]

    # ------------------------------------------------------------------------
    # Step 2: Browse Category "Tortlar" -> View Medovik -> Add 2 to Cart
    # ------------------------------------------------------------------------
    # Customer opens catalog
    msg_cat = MagicMock(spec=Message)
    msg_cat.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    msg_cat.text = get_text("btn_catalog", "uz")
    msg_cat.answer = AsyncMock()

    await open_catalog_message(msg_cat, db=memory_db, lang="uz", _t=fake_t("uz"))
    msg_cat.answer.assert_called_once()
    categories_kb_markup = msg_cat.answer.call_args[1]["reply_markup"]
    cat_buttons = [b for row in categories_kb_markup.inline_keyboard for b in row]
    assert any("category:1" in b.callback_data or "cat_1" in b.callback_data for b in cat_buttons)

    # Customer selects Category 1 ("Tortlar")
    cb_cat = MagicMock(spec=CallbackQuery)
    cb_cat.data = "cat_1"
    cb_cat.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    cb_cat.message = MagicMock(spec=Message, edit_text=AsyncMock(), answer=AsyncMock(), photo=None)
    cb_cat.answer = AsyncMock()

    await show_category_products(cb_cat, db=memory_db, lang="uz", _t=fake_t("uz"))
    cb_cat.message.edit_text.assert_called_once()
    products_kb = cb_cat.message.edit_text.call_args[1]["reply_markup"]
    prod_buttons = [b for row in products_kb.inline_keyboard for b in row]
    assert any("prod_1" in b.callback_data or "product:1" in b.callback_data for b in prod_buttons)

    # Customer views product 1 (Medovik: price 150 000 UZS)
    cb_prod = MagicMock(spec=CallbackQuery)
    cb_prod.data = "prod_1"
    cb_prod.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    cb_prod.message = MagicMock(spec=Message, edit_text=AsyncMock(), answer=AsyncMock(), photo=None)
    cb_prod.answer = AsyncMock()

    await show_product_card(cb_prod, db=memory_db, lang="uz", _t=fake_t("uz"))
    cb_prod.answer.assert_called_once()

    # Customer clicks to add 1 Medovik
    cb_add1 = MagicMock(spec=CallbackQuery)
    cb_add1.data = "add_prod_1"
    cb_add1.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    cb_add1.message = MagicMock(spec=Message, edit_reply_markup=AsyncMock())
    cb_add1.answer = AsyncMock()
    await handle_card_cart_action(cb_add1, db=memory_db, lang="uz", _t=fake_t("uz"))

    # Customer increments to add 2nd Medovik
    cb_add2 = MagicMock(spec=CallbackQuery)
    cb_add2.data = "inc_prod_1"
    cb_add2.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    cb_add2.message = MagicMock(spec=Message, edit_reply_markup=AsyncMock())
    cb_add2.answer = AsyncMock()
    await handle_card_cart_action(cb_add2, db=memory_db, lang="uz", _t=fake_t("uz"))

    # Verify Cart state in DB: 2 items of product 1 = 300 000 UZS
    cart_items = await crud.get_cart(memory_db, user_id=customer_id)
    assert len(cart_items) == 1
    assert cart_items[0]["product_id"] == 1
    assert cart_items[0]["quantity"] == 2
    assert cart_items[0]["price"] == 150000

    # ------------------------------------------------------------------------
    # Step 3: View Cart -> Checkout
    # ------------------------------------------------------------------------
    msg_cart = MagicMock(spec=Message)
    msg_cart.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    msg_cart.text = get_text("btn_cart", "uz")
    msg_cart.answer = AsyncMock()

    await open_cart_message(msg_cart, db=memory_db, lang="uz", _t=fake_t("uz"))
    msg_cart.answer.assert_called_once()
    cart_text = msg_cart.answer.call_args[0][0]
    assert "Medovik" in cart_text
    assert "300 000" in cart_text or "300000" in cart_text

    # Customer clicks "Buyurtma berish"
    state = make_fsm_context(user_id=customer_id)
    cb_checkout = MagicMock(spec=CallbackQuery)
    cb_checkout.data = "order_checkout"
    cb_checkout.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    cb_checkout.message = MagicMock(spec=Message, answer=AsyncMock(), edit_text=AsyncMock())
    cb_checkout.answer = AsyncMock()

    await start_order_checkout(
        cb_checkout,
        db=memory_db,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
        config=test_config,
    )
    assert await state.get_state() == OrderFSM.waiting_for_time.state

    # ------------------------------------------------------------------------
    # Step 4: Select Time ("hozir") -> Select Courier Delivery
    # ------------------------------------------------------------------------
    cb_time = MagicMock(spec=CallbackQuery)
    cb_time.data = "order_time:now"
    cb_time.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    cb_time.message = MagicMock(spec=Message, answer=AsyncMock(), edit_text=AsyncMock())
    cb_time.answer = AsyncMock()

    await handle_order_time(cb_time, state=state, lang="uz", _t=fake_t("uz"), config=test_config)
    assert await state.get_state() == OrderFSM.waiting_for_delivery_type.state

    cb_del = MagicMock(spec=CallbackQuery)
    cb_del.data = "delivery_type:delivery"
    cb_del.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    cb_del.message = MagicMock(spec=Message, answer=AsyncMock())
    cb_del.answer = AsyncMock()

    await handle_delivery_type(cb_del, state=state, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.waiting_for_location.state

    # ------------------------------------------------------------------------
    # Step 5: Send GPS Location -> Verify Distance & Free Delivery Threshold
    # ------------------------------------------------------------------------
    # Customer sends location ~5.9 km away from store
    msg_loc = MagicMock(
        spec=Message,
        location=Location(latitude=41.350000, longitude=69.290000),
        text=None,
        from_user=User(id=customer_id, is_bot=False, first_name="Ali"),
        answer=AsyncMock(),
    )
    await handle_location_input(
        msg_loc,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
        config=test_config,
    )

    fsm_data = await state.get_data()
    assert fsm_data["distance_km"] > 0
    # Cart total (300 000 UZS) >= free_delivery_threshold (250 000 UZS) -> delivery is free (0 UZS)
    assert fsm_data["delivery_cost"] == 0
    assert await state.get_state() == OrderFSM.waiting_for_phone.state

    # ------------------------------------------------------------------------
    # Step 6: Send Phone -> Send Personalized Cake Note ("Tug'ilgan kuningiz bilan!")
    # ------------------------------------------------------------------------
    msg_phone = MagicMock(
        spec=Message,
        contact=Contact(phone_number="+998901234567", first_name="Ali"),
        text=None,
        from_user=User(id=customer_id, is_bot=False, first_name="Ali"),
        answer=AsyncMock(),
    )
    await handle_phone_input(msg_phone, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.waiting_for_note.state

    # Verify user phone updated in DB
    user_updated = await crud.get_user(memory_db, customer_id)
    assert user_updated["phone"] == "+998901234567"

    # Send personalized cake note
    msg_note = MagicMock(
        spec=Message,
        text="Tug'ilgan kuningiz bilan!",
        from_user=User(id=customer_id, is_bot=False, first_name="Ali"),
        answer=AsyncMock(),
    )
    await handle_note_input(msg_note, state=state, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.waiting_for_payment.state
    fsm_data = await state.get_data()
    assert fsm_data["custom_note"] == "Tug'ilgan kuningiz bilan!"

    # ------------------------------------------------------------------------
    # Step 7: Select Cash Payment -> Confirm Order
    # ------------------------------------------------------------------------
    cb_pay = MagicMock(spec=CallbackQuery)
    cb_pay.data = "pay_method:cash"
    cb_pay.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    cb_pay.message = MagicMock(spec=Message, edit_text=AsyncMock(), answer=AsyncMock())
    cb_pay.answer = AsyncMock()

    await handle_payment_method(cb_pay, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == OrderFSM.confirmation.state

    # Confirm order
    cb_confirm = MagicMock(spec=CallbackQuery)
    cb_confirm.data = "order_confirm:yes"
    cb_confirm.from_user = User(id=customer_id, is_bot=False, first_name="Ali")
    cb_confirm.message = MagicMock(spec=Message, answer=AsyncMock())
    cb_confirm.answer = AsyncMock()

    await handle_order_confirmation(
        cb_confirm,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )
    assert await state.get_state() is None

    # ------------------------------------------------------------------------
    # Step 8: Verify DB State (order, order_items, empty cart)
    # ------------------------------------------------------------------------
    orders = await crud.get_user_orders(memory_db, user_id=customer_id)
    assert len(orders) == 1
    order = orders[0]
    order_id = order["id"]

    assert order["delivery_type"] == "delivery"
    assert order["delivery_cost"] == 0
    assert order["total_amount"] == 300000
    assert order["target_time"] == "hozir"
    assert order["phone"] == "+998901234567"
    assert order["custom_note"] == "Tug'ilgan kuningiz bilan!"
    assert order["payment_type"] == "cash"
    assert order["status"] == "new"

    # Verify order_items linked
    order_items = await crud.get_order_items(memory_db, order_id=order_id)
    assert len(order_items) == 1
    assert order_items[0]["product_id"] == 1
    assert order_items[0]["quantity"] == 2
    assert order_items[0]["price_at_purchase"] == 150000

    # Verify cart is empty
    cart_after = await crud.get_cart(memory_db, user_id=customer_id)
    assert len(cart_after) == 0

    # ------------------------------------------------------------------------
    # Step 9: Admin Order Lifecycle (new -> confirmed -> preparing -> delivering -> completed)
    # ------------------------------------------------------------------------
    mock_bot = MagicMock(spec=Bot)
    mock_bot.send_message = AsyncMock()

    def make_admin_callback(action: str) -> CallbackQuery:
        cb = MagicMock(spec=CallbackQuery)
        cb.data = f"{action}_{order_id}"
        cb.bot = mock_bot
        cb.from_user = User(id=admin_id, is_bot=False, first_name="Admin")
        cb.message = MagicMock(spec=Message, edit_reply_markup=AsyncMock(), edit_text=AsyncMock())
        cb.answer = AsyncMock()
        return cb

    # 1. new -> confirmed
    cb_adm1 = make_admin_callback("adm_confirm")
    await handle_admin_order_callback(cb_adm1, db=memory_db, config=test_config)
    order_state1 = await crud.get_order(memory_db, order_id)
    assert order_state1["status"] == "confirmed"
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args.kwargs["chat_id"] == customer_id
    text1 = mock_bot.send_message.call_args.kwargs["text"]
    assert f"#{order_id}" in text1
    assert any(w in text1.lower() for w in ("tasdiqlandi", "qabul qilindi"))

    # 2. confirmed -> preparing
    mock_bot.send_message.reset_mock()
    cb_adm2 = make_admin_callback("adm_ready")
    await handle_admin_order_callback(cb_adm2, db=memory_db, config=test_config)
    order_state2 = await crud.get_order(memory_db, order_id)
    assert order_state2["status"] == "preparing"
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args.kwargs["chat_id"] == customer_id
    text2 = mock_bot.send_message.call_args.kwargs["text"]
    assert f"#{order_id}" in text2
    assert "tayyorlash" in text2.lower()

    # 3. preparing -> delivering
    mock_bot.send_message.reset_mock()
    cb_adm3 = make_admin_callback("adm_dispatch")
    await handle_admin_order_callback(cb_adm3, db=memory_db, config=test_config)
    order_state3 = await crud.get_order(memory_db, order_id)
    assert order_state3["status"] == "delivering"
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args.kwargs["chat_id"] == customer_id
    text3 = mock_bot.send_message.call_args.kwargs["text"]
    assert f"#{order_id}" in text3
    assert any(w in text3.lower() for w in ("kuryer", "yo'lga chiqdi"))

    # 4. delivering -> completed
    mock_bot.send_message.reset_mock()
    cb_adm4 = make_admin_callback("adm_complete")
    await handle_admin_order_callback(cb_adm4, db=memory_db, config=test_config)
    order_state4 = await crud.get_order(memory_db, order_id)
    assert order_state4["status"] == "completed"
    mock_bot.send_message.assert_called_once()
    assert mock_bot.send_message.call_args.kwargs["chat_id"] == customer_id
    text4 = mock_bot.send_message.call_args.kwargs["text"]
    assert f"#{order_id}" in text4
    assert any(w in text4.lower() for w in ("yetkazildi", "yakunlandi", "ishtaha"))


# ============================================================================
# 2. End-to-End Custom Cake Photo Request Flow
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_custom_cake_request(memory_db):
    """
    End-to-End Journey 2: Custom Cake Request Flow:
    Trigger -> Upload Photo -> Weight & Filling Details -> Target Delivery Date -> Phone -> Confirm ->
    Verify DB state (order_type='custom_cake', image_id, custom_note, target_time, phone).
    """
    customer_id = 6001
    await crud.upsert_user(memory_db, telegram_id=customer_id, full_name="Nilufar", language="uz")
    state = make_fsm_context(user_id=customer_id)

    # 1. Start custom cake flow via reply button
    msg_start = MagicMock(
        spec=Message,
        text=get_text("btn_custom_cake", "uz"),
        from_user=User(id=customer_id, is_bot=False, first_name="Nilufar"),
        answer=AsyncMock(),
    )
    await start_custom_cake(msg_start, state=state, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == CustomCakeFSM.waiting_for_photo.state

    # 2. Upload photo with caption
    photo_file_id = "AgACAgIAAxkBAAIBYWRzc_custom_cake_photo_file_id_789"
    msg_photo = MagicMock(
        spec=Message,
        photo=[
            PhotoSize(file_id="small_photo", file_unique_id="s1", width=100, height=100),
            PhotoSize(file_id=photo_file_id, file_unique_id="s2", width=800, height=800),
        ],
        caption="3 qavatli to'y torti dizayni",
        text=None,
        from_user=User(id=customer_id, is_bot=False, first_name="Nilufar"),
        answer=AsyncMock(),
    )
    await handle_custom_cake_photo(msg_photo, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == CustomCakeFSM.waiting_for_details.state

    # 3. Specify weight & filling
    msg_details = MagicMock(
        spec=Message,
        text="3.5 kg, vanilli biskvit, qaymoqli krem va qulupnayli mevali nachinka",
        from_user=User(id=customer_id, is_bot=False, first_name="Nilufar"),
        answer=AsyncMock(),
    )
    await handle_custom_cake_details(msg_details, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == CustomCakeFSM.waiting_for_target_time.state

    # 4. Specify target date
    msg_date = MagicMock(
        spec=Message,
        text="15-noyabr 17:00",
        from_user=User(id=customer_id, is_bot=False, first_name="Nilufar"),
        answer=AsyncMock(),
    )
    await handle_custom_cake_target_time(msg_date, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == CustomCakeFSM.waiting_for_phone.state

    # 5. Specify phone contact
    msg_phone = MagicMock(
        spec=Message,
        contact=Contact(phone_number="+998911112233", first_name="Nilufar"),
        text=None,
        from_user=User(id=customer_id, is_bot=False, first_name="Nilufar"),
        answer=AsyncMock(),
    )
    await handle_custom_cake_phone(msg_phone, state=state, db=memory_db, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == CustomCakeFSM.confirmation.state

    # 6. Confirm custom cake order
    cb_confirm = MagicMock(spec=CallbackQuery)
    cb_confirm.data = "order_confirm:yes"
    cb_confirm.from_user = User(id=customer_id, is_bot=False, first_name="Nilufar")
    cb_confirm.message = MagicMock(spec=Message, answer=AsyncMock())
    cb_confirm.answer = AsyncMock()

    await handle_custom_cake_confirmation(
        cb_confirm,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )
    assert await state.get_state() is None

    # 7. Verify DB state: order exists, order_type='custom_cake', image_id, and note saved
    orders = await crud.get_user_orders(memory_db, user_id=customer_id)
    assert len(orders) == 1
    custom_order = orders[0]

    assert custom_order["order_type"] == "custom_cake"
    assert custom_order["custom_image_id"] == photo_file_id
    assert "3 qavatli to'y torti dizayni" in custom_order["custom_note"]
    assert "3.5 kg" in custom_order["custom_note"]
    assert "qulupnayli" in custom_order["custom_note"]
    assert custom_order["target_time"] == "15-noyabr 17:00"
    assert custom_order["phone"] == "+998911112233"
    assert custom_order["payment_type"] == "custom_quote"
    assert custom_order["total_amount"] == 0
    assert custom_order["status"] == "new"


# ============================================================================
# 3. End-to-End AI Sommelier Consultation Flow
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_ai_sommelier_consultation(memory_db, test_config):
    """
    End-to-End Journey 3: Grounded AI Sommelier Consultation:
    Open Sommelier -> Ask for recommendation -> Verify response contains real DB products
    and navigation markup -> Tap navigation button -> Navigate to catalog vitrina.
    """
    customer_id = 7001
    await crud.upsert_user(memory_db, telegram_id=customer_id, full_name="Sardor", language="uz")
    state = make_fsm_context(user_id=customer_id)

    # 1. Open AI Sommelier via menu button
    msg_start = MagicMock(
        spec=Message,
        text=get_text("btn_ai_consultant", "uz"),
        from_user=User(id=customer_id, is_bot=False, first_name="Sardor"),
        answer=AsyncMock(),
    )
    await open_ai_consultant_message(msg_start, state=state, lang="uz", _t=fake_t("uz"))
    assert await state.get_state() == AIConsultantFSM.waiting_for_query.state
    msg_start.answer.assert_called_once()
    assert get_text("ai_consultant_intro", "uz") in msg_start.answer.call_args[0][0]

    # 2. Ask recommendation for honey or chocolate cake
    msg_query = MagicMock(
        spec=Message,
        text="Assalomu alaykum! Mehmonlar uchun qanday asal yoki shokoladli tortni maslahat berasiz?",
        from_user=User(id=customer_id, is_bot=False, first_name="Sardor"),
        chat=Chat(id=customer_id, type="private"),
        bot=MagicMock(send_chat_action=AsyncMock()),
        answer=AsyncMock(),
    )

    with patch("handlers.ai_consultant.load_config", return_value=test_config):
        await process_ai_query(
            msg_query,
            state=state,
            db=memory_db,
            lang="uz",
            _t=fake_t("uz"),
        )

    # 3. Verify grounded recommendation and navigation markup
    msg_query.answer.assert_called_once()
    call_args, call_kwargs = msg_query.answer.call_args
    recommendation_text = call_args[0]
    result_markup = call_kwargs.get("reply_markup")

    # Verify recommendation contains actual database product names and prices
    assert any(
        product_name in recommendation_text
        for product_name in ["Medovik", "Asalli Medovik", "Shokoladli", "Qizil Baxmal"]
    )
    assert any(
        price_tag in recommendation_text
        for price_tag in ["150 000", "150000", "90 000", "25 000"]
    )

    # Verify navigation markup provides quick buttons to catalog and main menu
    assert result_markup is not None
    nav_buttons = [b for row in result_markup.inline_keyboard for b in row]
    assert any(b.callback_data in ("open_catalog", "to_catalog") for b in nav_buttons)
    assert any(b.callback_data == "to_main_menu" for b in nav_buttons)

    # 4. User clicks "Vitrinani ko'rish" (open_catalog)
    cb_catalog = MagicMock(spec=CallbackQuery)
    cb_catalog.data = "open_catalog"
    cb_catalog.from_user = User(id=customer_id, is_bot=False, first_name="Sardor")
    cb_catalog.message = MagicMock(spec=Message, answer=AsyncMock())
    cb_catalog.answer = AsyncMock()

    await handle_ai_open_catalog(
        cb_catalog,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )
    assert await state.get_state() is None
    cb_catalog.answer.assert_called_once()
    cb_catalog.message.answer.assert_called_once()
    assert get_text("select_category", "uz") in cb_catalog.message.answer.call_args[0][0]


# ============================================================================
# 4. End-to-End Telegram Payments Flow
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_telegram_payments(memory_db):
    """
    End-to-End Journey 4: Telegram Online Payments:
    Existing Order awaiting payment -> PreCheckoutQuery validation -> SuccessfulPayment
    DB update to 'paid' -> Confirmation receipt and main menu.
    """
    customer_id = 8001
    await crud.upsert_user(memory_db, telegram_id=customer_id, full_name="Dildora", language="uz")

    # Create an order with pending online payment (e.g. Click)
    order_id = await crud.create_order(
        db=memory_db,
        user_id=customer_id,
        order_type="standard",
        total_amount=150000,
        delivery_cost=12000,
        delivery_type="delivery",
        target_time="hozir",
        address="Toshkent, Yunusobod 4-mavze",
        latitude=41.36,
        longitude=69.28,
        distance_km=3.2,
        phone="+998931234567",
        custom_note="Iltimos, ehtiyotkorlik bilan yetkazing",
        payment_type="click",
    )

    initial_order = await crud.get_order(memory_db, order_id)
    assert initial_order["payment_status"] == "pending"
    assert initial_order["status"] == "new"

    # 1. PreCheckoutQuery validation from Telegram Payments
    pre_checkout = MagicMock(spec=PreCheckoutQuery)
    pre_checkout.id = "pcq_e2e_click_001"
    pre_checkout.invoice_payload = f"order_{order_id}"
    pre_checkout.from_user = User(id=customer_id, is_bot=False, first_name="Dildora")
    pre_checkout.currency = "UZS"
    pre_checkout.total_amount = 16200000  # in tiyin (162 000 UZS)
    pre_checkout.answer = AsyncMock()

    await handle_pre_checkout_query(
        query=pre_checkout,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )
    pre_checkout.answer.assert_awaited_once_with(ok=True)

    # 2. SuccessfulPayment event delivered upon completed payment
    sp = MagicMock(spec=SuccessfulPayment)
    sp.currency = "UZS"
    sp.total_amount = 16200000
    sp.invoice_payload = f"order_{order_id}"
    sp.provider_payment_charge_id = "click_provider_txn_98765"
    sp.telegram_payment_charge_id = "tg_pay_charge_54321"

    payment_msg = MagicMock(spec=Message)
    payment_msg.from_user = User(id=customer_id, is_bot=False, first_name="Dildora")
    payment_msg.chat = Chat(id=customer_id, type="private")
    payment_msg.successful_payment = sp
    payment_msg.answer = AsyncMock()

    await handle_successful_payment(
        message=payment_msg,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    # 3. Verify DB state: payment_status updated to 'paid'
    paid_order = await crud.get_order(memory_db, order_id)
    assert paid_order["payment_status"] == "paid"

    # 4. Verify receipt confirmation and main navigation menu displayed
    payment_msg.answer.assert_awaited_once()
    msg_args, msg_kwargs = payment_msg.answer.call_args
    receipt_text = msg_args[0] if msg_args else msg_kwargs.get("text", "")

    assert str(order_id) in receipt_text
    assert any(
        term in receipt_text.lower()
        for term in ("to'lov", "muvaffaqiyatli", "qabul", "to'landi")
    )
    assert msg_kwargs.get("reply_markup") is not None
