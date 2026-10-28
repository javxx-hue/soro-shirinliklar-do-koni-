"""
Tests for shopping cart handlers (handlers/cart.py).
"""
import pytest
import aiosqlite
from unittest.mock import AsyncMock, MagicMock

from database.db import init_db
from database import crud
from middlewares.i18n import get_text
from keyboards.inline import cart_kb, delivery_type_kb


@pytest.fixture
async def memory_db():
    """In-memory SQLite database initialized with categories, products, and tables."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    await init_db(db)
    yield db
    await db.close()


def fake_t(lang="uz"):
    """Helper to mock i18n _t callable."""
    return lambda key, **kwargs: get_text(key, lang=kwargs.pop("lang", lang), **kwargs)


@pytest.mark.asyncio
async def test_cart_router_definition():
    """Verify cart_router is an instance of aiogram.Router with name 'cart' and exported from handlers."""
    from aiogram import Router
    from handlers import cart_router

    assert isinstance(cart_router, Router)
    assert cart_router.name == "cart"


@pytest.mark.asyncio
async def test_open_cart_message_empty(memory_db):
    """Test opening empty cart via Uzbek reply button text and /cart command."""
    from handlers.cart import open_cart_message

    message = MagicMock()
    message.text = "🛒 Savatcha"
    message.from_user = MagicMock()
    message.from_user.id = 1001
    message.answer = AsyncMock()

    await open_cart_message(message, db=memory_db, lang="uz", _t=fake_t("uz"))

    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    assert get_text("cart_empty", "uz") in args[0]
    assert "reply_markup" in kwargs
    kb = kwargs["reply_markup"]
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert any(btn.callback_data in ("to_catalog", "open_catalog") for btn in buttons)


@pytest.mark.asyncio
async def test_open_cart_message_ru_empty(memory_db):
    """Test opening empty cart via Russian reply button text."""
    from handlers.cart import open_cart_message

    message = MagicMock()
    message.text = "🛒 Корзина"
    message.from_user = MagicMock()
    message.from_user.id = 1002
    message.answer = AsyncMock()

    await open_cart_message(message, db=memory_db, lang="ru", _t=fake_t("ru"))

    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    assert get_text("cart_empty", "ru") in args[0]


@pytest.mark.asyncio
async def test_open_cart_message_populated(memory_db):
    """Test opening cart with items displays receipt text and cart_kb."""
    from handlers.cart import open_cart_message

    user_id = 2001
    # Add product 1 (Medovik: 150 000) x 2 and product 6 (Kruassan: 25 000) x 1
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=2)
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=6, quantity=1)

    message = MagicMock()
    message.text = "/cart"
    message.from_user = MagicMock()
    message.from_user.id = user_id
    message.answer = AsyncMock()

    await open_cart_message(message, db=memory_db, lang="uz", _t=fake_t("uz"))

    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    text = args[0]

    # Verify receipt details
    assert get_text("cart_title", "uz") in text
    assert "Medovik" in text
    assert "Kruassan" in text
    # 2 * 150000 + 1 * 25000 = 325 000 so'm
    assert "325 000" in text

    # Verify markup has checkout and clear buttons
    kb = kwargs["reply_markup"]
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    callbacks = [btn.callback_data for btn in buttons]
    assert any("checkout" in cb for cb in callbacks)
    assert any("clear" in cb for cb in callbacks)


@pytest.mark.asyncio
async def test_open_cart_callback_empty_and_populated(memory_db):
    """Test opening cart via callback queries ('view_cart' and 'to_cart')."""
    from handlers.cart import open_cart_callback

    user_id = 3001
    callback = MagicMock()
    callback.data = "view_cart"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock()
    callback.message.photo = None
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.message.delete = AsyncMock()
    callback.answer = AsyncMock()

    # Empty cart
    await open_cart_callback(callback, db=memory_db, lang="uz", _t=fake_t("uz"))
    callback.answer.assert_called_once()
    callback.message.edit_text.assert_called_once()
    assert get_text("cart_empty", "uz") in callback.message.edit_text.call_args[0][0]

    # Add item and test 'to_cart'
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=1)
    callback.data = "to_cart"
    callback.message.edit_text.reset_mock()
    callback.answer.reset_mock()

    await open_cart_callback(callback, db=memory_db, lang="uz", _t=fake_t("uz"))
    callback.answer.assert_called_once()
    callback.message.edit_text.assert_called_once()
    assert "Medovik" in callback.message.edit_text.call_args[0][0]

    # Test opening cart from photo message (e.g. from product card)
    callback.message.photo = [MagicMock()]
    callback.message.answer.reset_mock()
    callback.message.delete.reset_mock()

    await open_cart_callback(callback, db=memory_db, lang="uz", _t=fake_t("uz"))
    callback.message.delete.assert_called_once()
    callback.message.answer.assert_called_once()
    assert "Medovik" in callback.message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cart_increment_callback(memory_db):
    """Test incrementing cart item quantity via 'inc_cart_<id>' and 'cart_plus:<id>'."""
    from handlers.cart import handle_cart_increment

    user_id = 4001
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=1)

    callback = MagicMock()
    callback.data = "inc_cart_1"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await handle_cart_increment(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    # DB should have quantity 2
    cart = await crud.get_cart(memory_db, user_id=user_id)
    assert len(cart) == 1
    assert cart[0]["quantity"] == 2

    callback.answer.assert_called_once()
    callback.message.edit_text.assert_called_once()
    text = callback.message.edit_text.call_args[0][0]
    # 2 * 150000 = 300 000
    assert "300 000" in text

    # Also test cart_plus:1 syntax
    callback.data = "cart_plus:1"
    callback.message.edit_text.reset_mock()
    callback.answer.reset_mock()

    await handle_cart_increment(callback, db=memory_db, lang="uz", _t=fake_t("uz"))
    cart = await crud.get_cart(memory_db, user_id=user_id)
    assert cart[0]["quantity"] == 3


@pytest.mark.asyncio
async def test_cart_decrement_callback(memory_db):
    """Test decrementing cart item quantity via 'dec_cart_<id>' and 'cart_minus:<id>'."""
    from handlers.cart import handle_cart_decrement

    user_id = 5001
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=2)

    callback = MagicMock()
    callback.data = "dec_cart_1"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    # 2 -> 1
    await handle_cart_decrement(callback, db=memory_db, lang="uz", _t=fake_t("uz"))
    cart = await crud.get_cart(memory_db, user_id=user_id)
    assert cart[0]["quantity"] == 1
    assert "150 000" in callback.message.edit_text.call_args[0][0]

    # 1 -> 0 (removes item, cart empty view)
    callback.data = "cart_minus:1"
    callback.message.edit_text.reset_mock()
    callback.answer.reset_mock()

    await handle_cart_decrement(callback, db=memory_db, lang="uz", _t=fake_t("uz"))
    cart = await crud.get_cart(memory_db, user_id=user_id)
    assert len(cart) == 0

    callback.message.edit_text.assert_called_once()
    assert get_text("cart_empty", "uz") in callback.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_cart_delete_callback(memory_db):
    """Test removing product entirely from cart via 'del_cart_<id>' and 'cart_del:<id>'."""
    from handlers.cart import handle_cart_delete

    user_id = 6001
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=5)
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=6, quantity=2)

    callback = MagicMock()
    callback.data = "del_cart_1"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await handle_cart_delete(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    cart = await crud.get_cart(memory_db, user_id=user_id)
    assert len(cart) == 1
    assert cart[0]["product_id"] == 6

    # Now delete remaining product with cart_del:6
    callback.data = "cart_del:6"
    callback.message.edit_text.reset_mock()
    callback.answer.reset_mock()

    await handle_cart_delete(callback, db=memory_db, lang="uz", _t=fake_t("uz"))
    cart = await crud.get_cart(memory_db, user_id=user_id)
    assert len(cart) == 0
    assert get_text("cart_empty", "uz") in callback.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_clear_cart_callback(memory_db):
    """Test clearing all items from cart via 'clear_cart' and 'cart_clear'."""
    from handlers.cart import handle_clear_cart

    user_id = 7001
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=2)
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=2, quantity=1)

    callback = MagicMock()
    callback.data = "clear_cart"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await handle_clear_cart(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    cart = await crud.get_cart(memory_db, user_id=user_id)
    assert len(cart) == 0

    # Answer should show alert
    callback.answer.assert_called_once()
    assert get_text("cart_cleared", "uz") in callback.answer.call_args[0][0]
    assert callback.answer.call_args[1].get("show_alert") is True

    # Message should show empty cart
    assert get_text("cart_empty", "uz") in callback.message.edit_text.call_args[0][0]


@pytest.mark.asyncio
async def test_checkout_callback_empty(memory_db):
    """Test checkout callback with empty cart alerts user."""
    from handlers.cart import handle_cart_checkout

    user_id = 8001
    callback = MagicMock()
    callback.data = "checkout"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock()
    callback.answer = AsyncMock()

    await handle_cart_checkout(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    callback.answer.assert_called_once()
    assert get_text("cart_empty", "uz") in callback.answer.call_args[0][0]
    assert callback.answer.call_args[1].get("show_alert") is True


@pytest.mark.asyncio
async def test_checkout_callback_populated(memory_db):
    """Test checkout callback with populated cart initiates order flow."""
    from handlers.cart import handle_cart_checkout

    user_id = 8002
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=1)

    callback = MagicMock()
    callback.data = "order_checkout"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    await handle_cart_checkout(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    callback.answer.assert_called_once()
    callback.message.edit_text.assert_called_once()
    args, kwargs = callback.message.edit_text.call_args
    assert get_text("order_delivery_type_prompt", "uz") in args[0]
    assert "reply_markup" in kwargs


@pytest.mark.asyncio
async def test_cart_item_click_noop(memory_db):
    """Test clicking on the cart item label answers query safely."""
    from handlers.cart import handle_cart_item_click

    callback = MagicMock()
    callback.data = "cart_item:1"
    callback.answer = AsyncMock()

    await handle_cart_item_click(callback)
    callback.answer.assert_called_once()
