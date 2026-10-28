"""
Unit and integration tests for the Custom Cake Order flow (handlers/custom_cake.py).
"""
import pytest
import aiosqlite
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import CallbackQuery, Message, Contact, PhotoSize

from database.db import init_db
from database import crud
from middlewares.i18n import get_text
from keyboards.reply import cancel_kb, phone_request_kb, main_menu_kb


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


def make_fsm_context(user_id: int = 2001, chat_id: int = 2001) -> FSMContext:
    """Creates a real FSMContext with in-memory storage."""
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=chat_id, user_id=user_id)
    return FSMContext(storage=storage, key=key)


# ============================================================================
# 1. Router & FSM Definition Tests
# ============================================================================

def test_custom_cake_router_and_fsm_definition():
    """Verify custom_cake_router is defined and CustomCakeFSM has all required states."""
    from handlers.custom_cake import custom_cake_router, CustomCakeFSM
    from handlers import custom_cake_router as exported_router

    assert isinstance(custom_cake_router, Router)
    assert custom_cake_router.name == "custom_cake"
    assert exported_router is custom_cake_router

    # Verify all 5 states exist
    assert hasattr(CustomCakeFSM, "waiting_for_photo")
    assert hasattr(CustomCakeFSM, "waiting_for_details")
    assert hasattr(CustomCakeFSM, "waiting_for_target_time")
    assert hasattr(CustomCakeFSM, "waiting_for_phone")
    assert hasattr(CustomCakeFSM, "confirmation")


# ============================================================================
# 2. Entry Handlers: Trigger via Button or Command
# ============================================================================

@pytest.mark.asyncio
async def test_start_custom_cake_via_reply_button(memory_db):
    """Clicking 'O'z tortingizga buyurtma' starts CustomCakeFSM and asks for photo."""
    from handlers.custom_cake import start_custom_cake, CustomCakeFSM

    user_id = 2002
    state = make_fsm_context(user_id=user_id)

    message = MagicMock(spec=Message)
    message.text = "🎨 O'z tortingizga buyurtma"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await start_custom_cake(
        message,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
    )

    message.answer.assert_called_once()
    assert await state.get_state() == CustomCakeFSM.waiting_for_photo.state

    text = message.answer.call_args[0][0]
    assert get_text("custom_cake_intro", "uz") in text or get_text("custom_cake_send_photo", "uz") in text

    # Verify reply markup contains cancel button
    reply_markup = message.answer.call_args[1].get("reply_markup")
    assert reply_markup is not None


@pytest.mark.asyncio
async def test_start_custom_cake_via_command_ru(memory_db):
    """Command /custom_cake in Russian starts CustomCakeFSM and prompts for photo."""
    from handlers.custom_cake import start_custom_cake, CustomCakeFSM

    user_id = 2003
    state = make_fsm_context(user_id=user_id)

    message = MagicMock(spec=Message)
    message.text = "/custom_cake"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await start_custom_cake(
        message,
        state=state,
        lang="ru",
        _t=fake_t("ru"),
    )

    message.answer.assert_called_once()
    assert await state.get_state() == CustomCakeFSM.waiting_for_photo.state
    text = message.answer.call_args[0][0]
    assert get_text("custom_cake_intro", "ru") in text or get_text("custom_cake_send_photo", "ru") in text


# ============================================================================
# 3. Step 1: Photo / Description Input Tests
# ============================================================================

@pytest.mark.asyncio
async def test_photo_upload_advances_to_waiting_for_details(memory_db):
    """Uploading photo stores file_id and advances to waiting_for_details."""
    from handlers.custom_cake import handle_custom_cake_photo, CustomCakeFSM

    user_id = 2004
    state = make_fsm_context(user_id=user_id)
    await state.set_state(CustomCakeFSM.waiting_for_photo)

    message = MagicMock(spec=Message)
    message.photo = [
        PhotoSize(file_id="small_thumb", file_unique_id="u1", width=50, height=50),
        PhotoSize(file_id="large_photo_id_123", file_unique_id="u2", width=800, height=800),
    ]
    message.caption = "Shu dizaynda tort pishirib bera olasizmi?"
    message.text = None
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_custom_cake_photo(
        message,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
    )

    message.answer.assert_called_once()
    assert await state.get_state() == CustomCakeFSM.waiting_for_details.state

    data = await state.get_data()
    assert data["custom_image_id"] == "large_photo_id_123"
    assert data["photo_desc"] == "Shu dizaynda tort pishirib bera olasizmi?"

    # Check prompt asks for weight/filling
    text = message.answer.call_args[0][0]
    assert get_text("custom_cake_send_weight", "uz") in text or get_text("custom_cake_send_desc", "uz") in text


@pytest.mark.asyncio
async def test_text_description_advances_to_waiting_for_details(memory_db):
    """Sending text description instead of photo stores description and advances."""
    from handlers.custom_cake import handle_custom_cake_photo, CustomCakeFSM

    user_id = 2005
    state = make_fsm_context(user_id=user_id)
    await state.set_state(CustomCakeFSM.waiting_for_photo)

    message = MagicMock(spec=Message)
    message.photo = None
    message.caption = None
    message.text = "Oq va pushti rangli 2 qavatli to'y torti, tabiiy atirgullar bilan."
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_custom_cake_photo(
        message,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
    )

    message.answer.assert_called_once()
    assert await state.get_state() == CustomCakeFSM.waiting_for_details.state

    data = await state.get_data()
    assert data["custom_image_id"] is None
    assert "Oq va pushti" in data["photo_desc"]


# ============================================================================
# 4. Step 2: Weight and Filling Details Tests
# ============================================================================

@pytest.mark.asyncio
async def test_details_input_advances_to_waiting_for_target_time(memory_db):
    """Entering weight and filling details advances to waiting_for_target_time."""
    from handlers.custom_cake import handle_custom_cake_details, CustomCakeFSM

    user_id = 2006
    state = make_fsm_context(user_id=user_id)
    await state.set_state(CustomCakeFSM.waiting_for_details)
    await state.update_data(custom_image_id="img_123", photo_desc="")

    message = MagicMock(spec=Message)
    message.text = "3 kg, shokoladli biskvit va qulupnayli krem, yong'oqsiz"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_custom_cake_details(
        message,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
    )

    message.answer.assert_called_once()
    assert await state.get_state() == CustomCakeFSM.waiting_for_target_time.state

    data = await state.get_data()
    assert "3 kg" in data["details"]

    # Verify prompt asks for delivery/event date and time
    text = message.answer.call_args[0][0]
    assert get_text("custom_cake_send_date", "uz") in text


# ============================================================================
# 5. Step 3: Target Date and Time Tests
# ============================================================================

@pytest.mark.asyncio
async def test_target_time_input_advances_to_waiting_for_phone(memory_db):
    """Entering target date/time advances to waiting_for_phone and asks for contact."""
    from handlers.custom_cake import handle_custom_cake_target_time, CustomCakeFSM

    user_id = 2007
    state = make_fsm_context(user_id=user_id)
    await state.set_state(CustomCakeFSM.waiting_for_target_time)
    await state.update_data(
        custom_image_id="img_123",
        photo_desc="Dizayn",
        details="2 kg, bananli",
    )

    message = MagicMock(spec=Message)
    message.text = "1-noyabr soat 16:00 ga"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_custom_cake_target_time(
        message,
        state=state,
        lang="uz",
        _t=fake_t("uz"),
    )

    message.answer.assert_called_once()
    assert await state.get_state() == CustomCakeFSM.waiting_for_phone.state

    data = await state.get_data()
    assert data["target_time"] == "1-noyabr soat 16:00 ga"

    # Verify prompt asks for phone
    text = message.answer.call_args[0][0]
    assert get_text("order_phone_prompt", "uz") in text


# ============================================================================
# 6. Step 4: Phone Input Tests
# ============================================================================

@pytest.mark.asyncio
async def test_phone_input_contact_advances_to_confirmation(memory_db):
    """Submitting phone contact updates DB and advances to confirmation with summary."""
    from handlers.custom_cake import handle_custom_cake_phone, CustomCakeFSM

    user_id = 2008
    await crud.upsert_user(memory_db, telegram_id=user_id, full_name="Nilufar")
    state = make_fsm_context(user_id=user_id)
    await state.set_state(CustomCakeFSM.waiting_for_phone)
    await state.update_data(
        custom_image_id="photo_xyz",
        photo_desc="Qulupnayli bezak",
        details="2.5 kg, mevali",
        target_time="25-dekabr 18:00",
    )

    message = MagicMock(spec=Message)
    message.contact = Contact(phone_number="+998901234567", first_name="Nilufar")
    message.text = None
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_custom_cake_phone(
        message,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    message.answer.assert_called_once()
    assert await state.get_state() == CustomCakeFSM.confirmation.state

    data = await state.get_data()
    assert data["phone"] == "+998901234567"

    # Check user in DB was updated
    user = await crud.get_user(memory_db, user_id)
    assert user["phone"] == "+998901234567"

    # Verify summary message contains order details
    summary = message.answer.call_args[0][0]
    assert "+998901234567" in summary
    assert "2.5 kg, mevali" in summary
    assert "25-dekabr 18:00" in summary


@pytest.mark.asyncio
async def test_phone_input_text_advances_to_confirmation(memory_db):
    """Submitting phone as text advances to confirmation."""
    from handlers.custom_cake import handle_custom_cake_phone, CustomCakeFSM

    user_id = 2009
    state = make_fsm_context(user_id=user_id)
    await state.set_state(CustomCakeFSM.waiting_for_phone)
    await state.update_data(
        custom_image_id=None,
        photo_desc="Tort tavsifi",
        details="1.5 kg, shokoladli",
        target_time="Ertaga 12:00",
    )

    message = MagicMock(spec=Message)
    message.contact = None
    message.text = "+998935557799"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_custom_cake_phone(
        message,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    message.answer.assert_called_once()
    assert await state.get_state() == CustomCakeFSM.confirmation.state
    data = await state.get_data()
    assert data["phone"] == "+998935557799"


# ============================================================================
# 7. Step 5: Order Confirmation & DB Persistence
# ============================================================================

@pytest.mark.asyncio
async def test_custom_cake_confirmation_persists_to_db_and_resets(memory_db):
    """Confirming custom cake order creates record in DB with order_type='custom_cake' and clears FSM."""
    from handlers.custom_cake import handle_custom_cake_confirmation, CustomCakeFSM

    user_id = 2010
    await crud.upsert_user(memory_db, telegram_id=user_id, full_name="Zilola")
    state = make_fsm_context(user_id=user_id)
    await state.set_state(CustomCakeFSM.confirmation)
    await state.update_data(
        custom_image_id="file_photo_1001",
        photo_desc="Shokoladli smes",
        details="2 kg, o'rmon mevalari",
        target_time="2-noyabr 15:00",
        phone="+998912223344",
    )

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "order_confirm:yes"
    callback.from_user = MagicMock(id=user_id)
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()

    await handle_custom_cake_confirmation(
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

    # 2. Check DB order created
    orders = await crud.get_user_orders(memory_db, user_id=user_id)
    assert len(orders) == 1
    cake_order = orders[0]
    assert cake_order["order_type"] == "custom_cake"
    assert cake_order["total_amount"] == 0
    assert cake_order["payment_type"] == "custom_quote"
    assert cake_order["status"] == "new"
    assert cake_order["custom_image_id"] == "file_photo_1001"
    assert "2 kg" in cake_order["custom_note"]
    assert cake_order["target_time"] == "2-noyabr 15:00"
    assert cake_order["phone"] == "+998912223344"

    # 3. Confirmation message sent
    sent_text = callback.message.answer.call_args[0][0]
    assert f"#{cake_order['id']}" in sent_text


@pytest.mark.asyncio
async def test_custom_cake_confirmation_via_message(memory_db):
    """User can also confirm custom cake order via text message."""
    from handlers.custom_cake import handle_custom_cake_confirmation, CustomCakeFSM

    user_id = 2011
    await crud.upsert_user(memory_db, telegram_id=user_id, full_name="Jasur")
    state = make_fsm_context(user_id=user_id)
    await state.set_state(CustomCakeFSM.confirmation)
    await state.update_data(
        custom_image_id=None,
        photo_desc="Rasm yo'q",
        details="1 kg bento tort",
        target_time="Bugun 20:00",
        phone="+998909876543",
    )

    message = MagicMock(spec=Message)
    message.text = "🎉 Buyurtmani tasdiqlash"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_custom_cake_confirmation(
        message,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    message.answer.assert_called_once()
    assert await state.get_state() is None

    orders = await crud.get_user_orders(memory_db, user_id=user_id)
    assert len(orders) == 1
    assert orders[0]["order_type"] == "custom_cake"


# ============================================================================
# 8. Cancellation Tests at Various Steps
# ============================================================================

@pytest.mark.asyncio
async def test_cancel_at_photo_state(memory_db):
    """User cancels at waiting_for_photo state resets FSM and shows main menu."""
    from handlers.custom_cake import handle_custom_cake_cancel, CustomCakeFSM

    user_id = 2012
    state = make_fsm_context(user_id=user_id)
    await state.set_state(CustomCakeFSM.waiting_for_photo)

    message = MagicMock(spec=Message)
    message.text = "❌ Bekor qilish"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_custom_cake_cancel(
        message,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    message.answer.assert_called_once()
    assert await state.get_state() is None
    sent_text = message.answer.call_args[0][0]
    assert get_text("action_cancelled", "uz") in sent_text


@pytest.mark.asyncio
async def test_cancel_at_details_state(memory_db):
    """User cancels at waiting_for_details state resets FSM."""
    from handlers.custom_cake import handle_custom_cake_cancel, CustomCakeFSM

    user_id = 2013
    state = make_fsm_context(user_id=user_id)
    await state.set_state(CustomCakeFSM.waiting_for_details)

    message = MagicMock(spec=Message)
    message.text = "/cancel"
    message.from_user = MagicMock(id=user_id)
    message.answer = AsyncMock()

    await handle_custom_cake_cancel(
        message,
        state=state,
        db=memory_db,
        lang="ru",
        _t=fake_t("ru"),
    )

    message.answer.assert_called_once()
    assert await state.get_state() is None
    sent_text = message.answer.call_args[0][0]
    assert get_text("action_cancelled", "ru") in sent_text


@pytest.mark.asyncio
async def test_cancel_at_confirmation_callback(memory_db):
    """User cancels at confirmation via callback query resets FSM."""
    from handlers.custom_cake import handle_custom_cake_cancel, CustomCakeFSM

    user_id = 2014
    state = make_fsm_context(user_id=user_id)
    await state.set_state(CustomCakeFSM.confirmation)

    callback = MagicMock(spec=CallbackQuery)
    callback.data = "order_confirm:cancel"
    callback.from_user = MagicMock(id=user_id)
    callback.message = MagicMock(spec=Message)
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()

    await handle_custom_cake_cancel(
        callback,
        state=state,
        db=memory_db,
        lang="uz",
        _t=fake_t("uz"),
    )

    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    assert await state.get_state() is None
    sent_text = callback.message.answer.call_args[0][0]
    assert get_text("action_cancelled", "uz") in sent_text
