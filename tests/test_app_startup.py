"""
Tests for application startup, router aggregation, bot main entrypoint,
and common navigation handlers (handlers/common.py and bot.py).
"""
import pytest
import aiosqlite
from unittest.mock import AsyncMock, MagicMock, patch

from aiogram import Bot, Dispatcher, Router
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from database.db import init_db
from database import crud
from middlewares.i18n import get_text, I18nMiddleware
from shop_config import Config


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
async def test_common_router_definition():
    """Verify common_router is an instance of aiogram.Router with name 'common'."""
    from handlers.common import common_router
    assert isinstance(common_router, Router)
    assert common_router.name == "common"


@pytest.mark.asyncio
async def test_handlers_package_exports_common_router():
    """Verify handlers package exports common_router in __all__."""
    import handlers
    assert hasattr(handlers, "common_router")
    assert "common_router" in handlers.__all__


@pytest.mark.asyncio
async def test_build_app_registers_all_routers_and_middlewares(memory_db):
    """Verify build_app returns configured bot, dispatcher, registers all 8 routers, and sets up middlewares."""
    from bot import build_app

    test_config = Config(
        bot_token="123456789:AABBCCDDEEFFGGHHIIJJKKLLMMNNOOPPQQR",
        admin_ids=[99999],
    )
    bot, dp = build_app(config=test_config, db_connection=memory_db)

    assert isinstance(bot, Bot)
    assert isinstance(dp, Dispatcher)
    assert dp["config"] == test_config
    assert dp["db"] == memory_db

    sub_router_names = [r.name for r in dp.sub_routers]
    expected_routers = [
        "common",
        "admin",
        "catalog",
        "cart",
        "order",
        "custom_cake",
        "payments",
        "ai_consultant",
    ]
    for r_name in expected_routers:
        assert r_name in sub_router_names, f"Expected router '{r_name}' not registered in sub_routers: {sub_router_names}"

    # Check that I18nMiddleware is registered on message and callback_query
    msg_middlewares = [m.__class__ for m in dp.message.middleware]
    cb_middlewares = [m.__class__ for m in dp.callback_query.middleware]
    assert I18nMiddleware in msg_middlewares
    assert I18nMiddleware in cb_middlewares


@pytest.mark.asyncio
async def test_start_handler_new_user_prompts_language_selection(memory_db):
    """When a new user triggers /start, they are saved in DB and prompted for language."""
    from handlers.common import start_handler

    user_id = 11001
    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = user_id
    message.from_user.full_name = "Yangi Foydalanuvchi"
    message.from_user.username = "new_user"
    message.answer = AsyncMock()

    test_config = Config(bot_token="123456:dummy", admin_ids=[99999])

    await start_handler(
        message=message,
        command=None,
        db=memory_db,
        config=test_config,
        lang="uz",
        _t=fake_t("uz"),
    )

    # Check user was created in DB
    user_in_db = await crud.get_user(memory_db, user_id)
    assert user_in_db is not None
    assert user_in_db["full_name"] == "Yangi Foydalanuvchi"

    # User should be prompted to choose language
    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    sent_text = args[0]
    assert get_text("choose_language", "uz") in sent_text
    reply_markup = kwargs.get("reply_markup")
    assert isinstance(reply_markup, InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_start_handler_existing_user_shows_welcome_and_main_menu(memory_db):
    """When an existing user with language set triggers /start, they receive welcome message and main menu."""
    from handlers.common import start_handler

    user_id = 12002
    await crud.upsert_user(
        memory_db,
        telegram_id=user_id,
        full_name="Eski Foydalanuvchi",
        language="uz",
    )

    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = user_id
    message.from_user.full_name = "Eski Foydalanuvchi"
    message.from_user.username = "old_user"
    message.answer = AsyncMock()

    test_config = Config(bot_token="123456:dummy", admin_ids=[user_id])

    await start_handler(
        message=message,
        command=None,
        db=memory_db,
        config=test_config,
        lang="uz",
        _t=fake_t("uz"),
    )

    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    sent_text = args[0]
    assert get_text("welcome_msg", "uz") in sent_text
    reply_markup = kwargs.get("reply_markup")
    assert isinstance(reply_markup, ReplyKeyboardMarkup)
    # Check that admin panel button is included since user_id is in admin_ids
    kb_texts = [btn.text for row in reply_markup.keyboard for btn in row]
    assert get_text("admin_panel_title", "uz") in kb_texts


@pytest.mark.asyncio
async def test_start_handler_deep_link_language_selection(memory_db):
    """When /start is called with 'lang' or 'language' argument, prompts language_kb even for existing user."""
    from handlers.common import start_handler

    user_id = 13003
    await crud.upsert_user(
        memory_db,
        telegram_id=user_id,
        full_name="Mijoz",
        language="uz",
    )

    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = user_id
    message.from_user.full_name = "Mijoz"
    message.from_user.username = "client"
    message.answer = AsyncMock()

    command = MagicMock()
    command.args = "lang"

    await start_handler(
        message=message,
        command=command,
        db=memory_db,
        config=Config(bot_token="123:dummy"),
        lang="uz",
        _t=fake_t("uz"),
    )

    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    assert get_text("choose_language", "uz") in args[0]
    assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_set_language_callback_uz_and_ru(memory_db):
    """Selecting language callback sets DB language, sends confirmation, and displays main menu."""
    from handlers.common import set_language_callback

    user_id = 14004
    await crud.upsert_user(memory_db, telegram_id=user_id, full_name="Vali", language="uz")

    # 1. Switch to Russian
    callback = MagicMock()
    callback.data = "set_lang:ru"
    callback.from_user = MagicMock()
    callback.from_user.id = user_id
    callback.answer = AsyncMock()
    callback.message = MagicMock()
    callback.message.answer = AsyncMock()

    test_config = Config(bot_token="123:dummy", admin_ids=[])

    await set_language_callback(
        callback=callback,
        db=memory_db,
        config=test_config,
    )

    # DB updated to ru
    updated_user = await crud.get_user(memory_db, user_id)
    assert updated_user["language"] == "ru"
    callback.answer.assert_called_once()
    callback.message.answer.assert_called_once()
    sent_text = callback.message.answer.call_args[0][0]
    assert get_text("lang_selected_ru", "ru") in sent_text
    reply_markup = callback.message.answer.call_args[1].get("reply_markup")
    assert isinstance(reply_markup, ReplyKeyboardMarkup)

    # 2. Switch back to Uzbek via lang_uz callback format
    callback.data = "lang_uz"
    callback.answer.reset_mock()
    callback.message.answer.reset_mock()

    await set_language_callback(
        callback=callback,
        db=memory_db,
        config=test_config,
    )

    updated_user = await crud.get_user(memory_db, user_id)
    assert updated_user["language"] == "uz"
    sent_text = callback.message.answer.call_args[0][0]
    assert get_text("lang_selected_uz", "uz") in sent_text


@pytest.mark.asyncio
async def test_change_language_handler():
    """Testing /language command or change language reply button."""
    from handlers.common import change_language_handler

    message = MagicMock()
    message.answer = AsyncMock()

    await change_language_handler(message=message, lang="uz", _t=fake_t("uz"))
    message.answer.assert_called_once()
    args, kwargs = message.answer.call_args
    assert get_text("choose_language", "uz") in args[0]
    assert isinstance(kwargs.get("reply_markup"), InlineKeyboardMarkup)


@pytest.mark.asyncio
async def test_about_and_contact_handler():
    """Testing /about or contact button returns shop details, address, hours, and phone."""
    from handlers.common import about_handler

    message = MagicMock()
    message.answer = AsyncMock()

    # Uzbek
    await about_handler(message=message, lang="uz", _t=fake_t("uz"))
    message.answer.assert_called_once()
    assert get_text("contact_info", "uz") in message.answer.call_args[0][0]

    # Russian
    message.answer.reset_mock()
    await about_handler(message=message, lang="ru", _t=fake_t("ru"))
    message.answer.assert_called_once()
    assert get_text("contact_info", "ru") in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_my_orders_empty(memory_db):
    """When user has no orders, /my_orders shows empty orders notice."""
    from handlers.common import my_orders_handler

    user_id = 15005
    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = user_id
    message.answer = AsyncMock()

    await my_orders_handler(message=message, db=memory_db, lang="uz", _t=fake_t("uz"))

    message.answer.assert_called_once()
    assert get_text("my_orders_empty", "uz") in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_my_orders_with_orders(memory_db):
    """When user has orders, /my_orders lists recent orders with status and sum."""
    from handlers.common import my_orders_handler

    user_id = 16006
    order_id = await crud.create_order(
        db=memory_db,
        user_id=user_id,
        order_type="standard",
        total_amount=150000,
        delivery_cost=12000,
        delivery_type="delivery",
        target_time="Hozir",
        address="Toshkent, Yunusobod",
        latitude=41.31,
        longitude=69.24,
        distance_km=2.5,
        phone="+998901234567",
        custom_note="Tabrik yozuvi",
        payment_type="cash",
    )

    message = MagicMock()
    message.from_user = MagicMock()
    message.from_user.id = user_id
    message.answer = AsyncMock()

    await my_orders_handler(message=message, db=memory_db, lang="uz", _t=fake_t("uz"))

    message.answer.assert_called_once()
    sent_text = message.answer.call_args[0][0]
    assert f"#{order_id}" in sent_text
    assert "150 000" in sent_text or "150000" in sent_text


@pytest.mark.asyncio
async def test_help_handler():
    """Testing /help displays help guide."""
    from handlers.common import help_handler

    message = MagicMock()
    message.answer = AsyncMock()

    await help_handler(message=message, lang="uz", _t=fake_t("uz"))
    message.answer.assert_called_once()
    assert get_text("help_msg", "uz") in message.answer.call_args[0][0]


@pytest.mark.asyncio
async def test_setup_bot_commands():
    """Verify setup_bot_commands registers required commands on bot."""
    from bot import setup_bot_commands

    bot = MagicMock()
    bot.set_my_commands = AsyncMock()

    await setup_bot_commands(bot)

    bot.set_my_commands.assert_called_once()
    commands = bot.set_my_commands.call_args[0][0]
    command_names = {c.command for c in commands}
    required = {
        "start",
        "catalog",
        "cart",
        "custom_cake",
        "my_orders",
        "ai",
        "language",
        "about",
        "help",
    }
    for req in required:
        assert req in command_names, f"Command '{req}' missing from set_my_commands!"
