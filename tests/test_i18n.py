"""
Tests for localization (i18n), translation key parity, safe formatting, and I18nMiddleware.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
import pytest
import pytest_asyncio
import aiosqlite

from database.db import init_db
from database.crud import upsert_user
from middlewares.i18n import get_text, I18nMiddleware, load_locales


def test_locales_keys_match():
    """Verify that uz.json and ru.json have 100% key parity and non-empty values."""
    locales_dir = Path(__file__).resolve().parent.parent / "locales"
    uz_path = locales_dir / "uz.json"
    ru_path = locales_dir / "ru.json"

    assert uz_path.exists(), f"locales/uz.json not found at {uz_path}"
    assert ru_path.exists(), f"locales/ru.json not found at {ru_path}"

    with open(uz_path, "r", encoding="utf-8") as f:
        uz_data = json.load(f)
    with open(ru_path, "r", encoding="utf-8") as f:
        ru_data = json.load(f)

    uz_keys = set(uz_data.keys())
    ru_keys = set(ru_data.keys())

    diff = uz_keys ^ ru_keys
    assert not diff, f"Mismatched keys between uz.json and ru.json: {diff}"
    assert len(uz_keys) >= 30, f"Expected at least 30 keys, got {len(uz_keys)}"

    # Check for empty values
    for k, v in uz_data.items():
        assert isinstance(v, str) and v.strip(), f"Key '{k}' in uz.json is empty"
    for k, v in ru_data.items():
        assert isinstance(v, str) and v.strip(), f"Key '{k}' in ru.json is empty"


def test_get_text_basic():
    """Verify basic key retrieval for both Uzbek and Russian."""
    uz_text = get_text("btn_cart", lang="uz")
    ru_text = get_text("btn_cart", lang="ru")

    assert "Savatcha" in uz_text or "Savat" in uz_text
    assert "Корзина" in ru_text


def test_get_text_formatting():
    """Verify placeholder replacement in formatted messages."""
    uz_msg = get_text("order_confirmed_msg", lang="uz", order_id=45)
    ru_msg = get_text("order_confirmed_msg", lang="ru", order_id=45)

    assert "45" in uz_msg
    assert "45" in ru_msg


def test_get_text_safe_formatting_missing_placeholders():
    """Verify that missing placeholders do not crash with KeyError."""
    # Calling order_confirmed_msg without order_id should not crash
    msg = get_text("order_confirmed_msg", lang="uz")
    assert isinstance(msg, str)
    assert len(msg) > 0


def test_get_text_safe_formatting_extra_placeholders():
    """Verify that unused extra keyword arguments are safely ignored."""
    msg = get_text("welcome_msg", lang="uz", non_existent_arg="hello", number=123)
    assert isinstance(msg, str)
    assert len(msg) > 0


def test_get_text_fallback_behavior():
    """Verify fallback when key or language is invalid or missing."""
    # Non-existent key should return the key name itself
    missing_key = "some_random_missing_key_9999"
    assert get_text(missing_key, lang="uz") == missing_key
    assert get_text(missing_key, lang="ru") == missing_key

    # Invalid language should fallback to uz
    uz_cart = get_text("btn_cart", lang="uz")
    fallback_cart = get_text("btn_cart", lang="fr")
    assert fallback_cart == uz_cart

    # None as lang should default to uz
    assert get_text("btn_cart", lang=None) == uz_cart


@pytest_asyncio.fixture
async def memory_db():
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    await init_db(db)
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_i18n_middleware_with_db_user(memory_db):
    """Verify middleware detects user language stored in database."""
    # User 1001 prefers Russian
    await upsert_user(memory_db, telegram_id=1001, full_name="Ivan", language="ru")

    middleware = I18nMiddleware(db=memory_db)

    # Fake telegram event
    event = MagicMock()
    event.from_user.id = 1001
    event.from_user.language_code = "uz"  # Telegram says uz, but DB says ru

    data = {}
    handler_called = False

    async def fake_handler(ev, d):
        nonlocal handler_called
        handler_called = True
        assert d["lang"] == "ru"
        assert callable(d["_t"])
        # Check injected _t helper
        assert "Корзина" in d["_t"]("btn_cart")
        # Check override
        assert "Savat" in d["_t"]("btn_cart", lang="uz")
        return "ok"

    result = await middleware(fake_handler, event, data)
    assert result == "ok"
    assert handler_called is True
    assert data["lang"] == "ru"


@pytest.mark.asyncio
async def test_i18n_middleware_fallback_to_telegram_language_code(memory_db):
    """Verify middleware falls back to Telegram language_code if user not in DB."""
    middleware = I18nMiddleware(db=memory_db)

    # User 2002 not in DB, telegram language is ru
    event = MagicMock()
    event.from_user.id = 2002
    event.from_user.language_code = "ru-RU"

    data = {}

    async def fake_handler(ev, d):
        assert d["lang"] == "ru"
        return "ok"

    await middleware(fake_handler, event, data)


@pytest.mark.asyncio
async def test_i18n_middleware_fallback_to_default_uz(memory_db):
    """Verify middleware falls back to 'uz' when user not in DB and language_code is English/unknown."""
    middleware = I18nMiddleware(db=memory_db)

    event = MagicMock()
    event.from_user.id = 3003
    event.from_user.language_code = "en"

    data = {}

    async def fake_handler(ev, d):
        assert d["lang"] == "uz"
        return "ok"

    await middleware(fake_handler, event, data)


@pytest.mark.asyncio
async def test_i18n_middleware_db_in_data(memory_db):
    """Verify middleware reads db from data['db'] if not passed in constructor."""
    middleware = I18nMiddleware()  # No db in constructor

    await upsert_user(memory_db, telegram_id=4004, full_name="Aziz", language="ru")

    event = MagicMock()
    event.from_user.id = 4004
    event.from_user.language_code = "en"

    data = {"db": memory_db}

    async def fake_handler(ev, d):
        assert d["lang"] == "ru"
        return "ok"

    await middleware(fake_handler, event, data)


@pytest.mark.asyncio
async def test_i18n_middleware_no_from_user():
    """Verify middleware handles events without from_user gracefully."""
    middleware = I18nMiddleware()

    event = MagicMock()
    event.from_user = None

    data = {}

    async def fake_handler(ev, d):
        assert d["lang"] == "uz"
        return "ok"

    await middleware(fake_handler, event, data)
