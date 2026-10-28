"""
Tests for catalog and product vitrina handlers (handlers/catalog.py).
"""
import pytest
import aiosqlite
from unittest.mock import AsyncMock, MagicMock

from database.db import init_db
from database import crud
from middlewares.i18n import get_text
from handlers.catalog import catalog_router
from keyboards.inline import categories_kb, products_list_kb, product_card_kb


@pytest.fixture
async def memory_db():
    """In-memory SQLite database initialized with categories and products."""
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
async def test_catalog_router_definition():
    """Verify catalog_router is an instance of aiogram.Router with name 'catalog'."""
    from aiogram import Router
    assert isinstance(catalog_router, Router)
    assert catalog_router.name == "catalog"


@pytest.mark.asyncio
async def test_open_catalog_message_uz(memory_db):
    """Test opening catalog via Uzbek reply button text."""
    message = MagicMock()
    message.text = get_text("btn_catalog", "uz")
    message.from_user = MagicMock()
    message.from_user.id = 1001
    message.from_user.language_code = "uz"
    message.answer = AsyncMock()

    # Find handler registered on message
    from handlers.catalog import open_catalog_message
    await open_catalog_message(message, db=memory_db, lang="uz", _t=fake_t("uz"))

    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    assert get_text("select_category", "uz") in args[0]
    assert "reply_markup" in kwargs
    # Verify markup has categories
    kb = kwargs["reply_markup"]
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert any("category:1" in btn.callback_data for btn in buttons)


@pytest.mark.asyncio
async def test_open_catalog_message_ru(memory_db):
    """Test opening catalog via Russian reply button text."""
    message = MagicMock()
    message.text = get_text("btn_catalog", "ru")
    message.from_user = MagicMock()
    message.from_user.id = 1002
    message.from_user.language_code = "ru"
    message.answer = AsyncMock()

    from handlers.catalog import open_catalog_message
    await open_catalog_message(message, db=memory_db, lang="ru", _t=fake_t("ru"))

    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    assert get_text("select_category", "ru") in args[0]
    kb = kwargs["reply_markup"]
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    assert any("category:1" in btn.callback_data for btn in buttons)


@pytest.mark.asyncio
async def test_open_catalog_command(memory_db):
    """Test opening catalog via /catalog command."""
    message = MagicMock()
    message.text = "/catalog"
    message.from_user = MagicMock()
    message.from_user.id = 1003
    message.answer = AsyncMock()

    from handlers.catalog import open_catalog_message
    await open_catalog_message(message, db=memory_db, lang="uz", _t=fake_t("uz"))

    message.answer.assert_called_once()
    assert get_text("select_category", "uz") in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_open_catalog_callback(memory_db):
    """Test opening catalog via inline callback (open_catalog / to_catalog / to_categories)."""
    callback = MagicMock()
    callback.data = "open_catalog"
    callback.from_user = MagicMock()
    callback.from_user.id = 1004
    callback.message = MagicMock()
    callback.message.photo = None
    callback.message.text = "Previous text"
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()

    from handlers.catalog import open_catalog_callback
    await open_catalog_callback(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    callback.answer.assert_called_once()
    callback.message.edit_text.assert_called_once()
    args, kwargs = callback.message.edit_text.call_args
    assert get_text("select_category", "uz") in args[0]
    assert "reply_markup" in kwargs


@pytest.mark.asyncio
async def test_category_products_list(memory_db):
    """Test viewing products list in a category."""
    # Seeded category 1 is Tortlar
    callback = MagicMock()
    callback.data = "cat_1"
    callback.from_user = MagicMock()
    callback.from_user.id = 1005
    callback.message = MagicMock()
    callback.message.photo = None
    callback.message.text = "Categories"
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()

    from handlers.catalog import show_category_products
    await show_category_products(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    callback.answer.assert_called_once()
    callback.message.edit_text.assert_called_once()
    args, kwargs = callback.message.edit_text.call_args
    assert get_text("select_product", "uz") in args[0]
    kb = kwargs["reply_markup"]
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    # Check that Medovik product is in the buttons
    assert any("product:1" in btn.callback_data or "prod_1" in btn.callback_data for btn in buttons)


@pytest.mark.asyncio
async def test_category_empty_products(memory_db):
    """Test viewing an empty category shows category_empty notice."""
    # Create empty category
    cat_id = await crud.add_category(memory_db, name_uz="Bo'sh toifa", name_ru="Пустая категория")

    callback = MagicMock()
    callback.data = f"category:{cat_id}"
    callback.from_user = MagicMock()
    callback.from_user.id = 1006
    callback.message = MagicMock()
    callback.message.photo = None
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.answer = AsyncMock()

    from handlers.catalog import show_category_products
    await show_category_products(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    callback.answer.assert_called_once()
    callback.message.edit_text.assert_called_once()
    args, kwargs = callback.message.edit_text.call_args
    assert get_text("category_empty", "uz") in args[0]


@pytest.mark.asyncio
async def test_product_card_details(memory_db):
    """Test product details card displays photo/caption with weight, description, price, and card kb."""
    callback = MagicMock()
    callback.data = "prod_1"
    callback.from_user = MagicMock()
    callback.from_user.id = 1007
    callback.message = MagicMock()
    callback.message.photo = None
    callback.message.text = "List of products"
    callback.message.edit_text = AsyncMock()
    callback.message.answer = AsyncMock()
    callback.message.delete = AsyncMock()
    callback.answer = AsyncMock()

    from handlers.catalog import show_product_card
    await show_product_card(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    callback.answer.assert_called_once()
    # Edit text was called (or answer)
    assert callback.message.edit_text.called or callback.message.answer.called
    call_args = callback.message.edit_text.call_args if callback.message.edit_text.called else callback.message.answer.call_args
    caption = call_args[0][0]

    # Verify appetizing card details
    assert "Medovik" in caption
    assert "Vazni:" in caption or "1.2 kg" in caption
    assert "150 000" in caption or "150000" in caption
    assert "reply_markup" in call_args[1]


@pytest.mark.asyncio
async def test_product_card_quantity_reflects_cart(memory_db):
    """Test product details card reflects quantity if already in user's cart."""
    user_id = 1008
    # Product 1 added to cart with quantity 4
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=4)

    callback = MagicMock()
    callback.data = "product:1"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock()
    callback.message.photo = None
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()

    from handlers.catalog import show_product_card
    await show_product_card(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    kb = callback.message.edit_text.call_args[1]["reply_markup"]
    buttons = [btn for row in kb.inline_keyboard for btn in row]
    # Center noop button should display quantity 4
    assert any(btn.text == "4" for btn in buttons)


@pytest.mark.asyncio
async def test_product_not_available(memory_db):
    """Test requesting unavailable or non-existent product notifies user."""
    callback = MagicMock()
    callback.data = "prod_99999"
    callback.from_user = MagicMock()
    callback.from_user.id = 1009
    callback.answer = AsyncMock()

    from handlers.catalog import show_product_card
    await show_product_card(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    callback.answer.assert_called_once()
    assert callback.answer.call_args[1].get("show_alert") is True or get_text("product_not_available", "uz") in callback.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_cart_inc_and_add_prod(memory_db):
    """Test add_prod_<id> and inc_prod_<id> increment cart, show toast alert, and update markup."""
    user_id = 1010
    callback = MagicMock()
    callback.data = "add_prod_1"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.answer = AsyncMock()

    from handlers.catalog import handle_card_cart_action
    await handle_card_cart_action(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    # Verify cart has product 1 with quantity 1
    cart = await crud.get_cart(memory_db, user_id)
    assert len(cart) == 1
    assert cart[0]["product_id"] == 1
    assert cart[0]["quantity"] == 1

    # Verify toast alert shown
    callback.answer.assert_called_once()
    alert_text = callback.answer.call_args[0][0] if callback.answer.call_args[0] else callback.answer.call_args[1].get("text")
    assert get_text("added_to_cart_alert", "uz") in alert_text or "savatchaga" in alert_text.lower() or "savat" in alert_text.lower()
    callback.message.edit_reply_markup.assert_called_once()

    # Now call inc_prod_1
    callback.data = "inc_prod_1"
    callback.answer.reset_mock()
    callback.message.edit_reply_markup.reset_mock()
    await handle_card_cart_action(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    cart = await crud.get_cart(memory_db, user_id)
    assert cart[0]["quantity"] == 2
    callback.answer.assert_called_once()
    callback.message.edit_reply_markup.assert_called_once()


@pytest.mark.asyncio
async def test_cart_dec_prod(memory_db):
    """Test dec_prod_<id> decrements cart and updates markup."""
    user_id = 1011
    # User starts with 2 of product 1
    await crud.add_to_cart(memory_db, user_id=user_id, product_id=1, quantity=2)

    callback = MagicMock()
    callback.data = "dec_prod_1"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.answer = AsyncMock()

    from handlers.catalog import handle_card_cart_action
    await handle_card_cart_action(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    cart = await crud.get_cart(memory_db, user_id)
    assert cart[0]["quantity"] == 1
    callback.message.edit_reply_markup.assert_called_once()
    callback.answer.assert_called_once()

    # Decrement again down to 0
    callback.answer.reset_mock()
    callback.message.edit_reply_markup.reset_mock()
    await handle_card_cart_action(callback, db=memory_db, lang="uz", _t=fake_t("uz"))

    cart = await crud.get_cart(memory_db, user_id)
    assert len(cart) == 0
    callback.message.edit_reply_markup.assert_called_once()
    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_noop_callback():
    """Test clicking noop counter button answers callback without modification."""
    callback = MagicMock()
    callback.data = "noop"
    callback.answer = AsyncMock()

    from handlers.catalog import handle_noop
    await handle_noop(callback)

    callback.answer.assert_called_once()


@pytest.mark.asyncio
async def test_prod_plus_minus_and_add_cart(memory_db):
    """Test keyboard interactive callbacks prod_plus, prod_minus, and add_cart."""
    user_id = 1012
    callback = MagicMock()
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.message = MagicMock()
    callback.message.edit_reply_markup = AsyncMock()
    callback.answer = AsyncMock()

    from handlers.catalog import handle_card_cart_action

    # 1. Plus
    callback.data = "prod_plus:1:2:1"
    await handle_card_cart_action(callback, db=memory_db, lang="uz", _t=fake_t("uz"))
    callback.message.edit_reply_markup.assert_called_once()
    new_kb = callback.message.edit_reply_markup.call_args[1]["reply_markup"]
    assert any(btn.text == "3" for row in new_kb.inline_keyboard for btn in row)

    # 2. Minus
    callback.message.edit_reply_markup.reset_mock()
    callback.data = "prod_minus:1:3:1"
    await handle_card_cart_action(callback, db=memory_db, lang="uz", _t=fake_t("uz"))
    new_kb = callback.message.edit_reply_markup.call_args[1]["reply_markup"]
    assert any(btn.text == "2" for row in new_kb.inline_keyboard for btn in row)

    # 3. Add to cart
    callback.answer.reset_mock()
    callback.data = "add_cart:1:3"
    await handle_card_cart_action(callback, db=memory_db, lang="uz", _t=fake_t("uz"))
    cart = await crud.get_cart(memory_db, user_id)
    assert len(cart) == 1
    assert cart[0]["quantity"] == 3
    callback.answer.assert_called_once()
