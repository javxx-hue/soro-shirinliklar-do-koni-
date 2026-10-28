"""
Unit tests for Reply, Inline, and Admin keyboards.
Verifies keyboard generation, localized button texts, callback data, and layouts.
"""
import pytest
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup

from keyboards import (
    admin_main_kb,
    cancel_kb,
    cart_kb,
    categories_kb,
    delivery_type_kb,
    language_kb,
    location_request_kb,
    main_menu_kb,
    order_admin_actions_kb,
    order_confirm_kb,
    order_time_kb,
    payment_methods_kb,
    phone_request_kb,
    product_card_kb,
    products_list_kb,
    skip_or_cancel_kb,
)
from middlewares.i18n import get_text


# ============================================================================
# Reply Keyboards Tests
# ============================================================================

def test_main_menu_kb_uz_defaults():
    kb = main_menu_kb(lang="uz", cart_count=0, is_admin=False)
    assert isinstance(kb, ReplyKeyboardMarkup)
    assert kb.resize_keyboard is True

    button_texts = [btn.text for row in kb.keyboard for btn in row]
    assert get_text("btn_catalog", "uz") in button_texts
    assert get_text("btn_cart", "uz") in button_texts
    assert get_text("btn_custom_cake", "uz") in button_texts
    assert get_text("btn_ai_consultant", "uz") in button_texts
    assert get_text("btn_my_orders", "uz") in button_texts
    assert get_text("btn_contact", "uz") in button_texts
    assert get_text("btn_change_lang", "uz") in button_texts
    assert get_text("admin_panel_title", "uz") not in button_texts


def test_main_menu_kb_with_cart_count_and_admin():
    kb = main_menu_kb(lang="uz", cart_count=4, is_admin=True)
    button_texts = [btn.text for row in kb.keyboard for btn in row]

    expected_cart_text = f"{get_text('btn_cart', 'uz')} (4)"
    assert expected_cart_text in button_texts
    assert get_text("admin_panel_title", "uz") in button_texts


def test_main_menu_kb_ru():
    kb = main_menu_kb(lang="ru", cart_count=2, is_admin=False)
    button_texts = [btn.text for row in kb.keyboard for btn in row]

    assert get_text("btn_catalog", "ru") in button_texts
    assert f"{get_text('btn_cart', 'ru')} (2)" in button_texts
    assert get_text("btn_custom_cake", "ru") in button_texts
    assert get_text("btn_ai_consultant", "ru") in button_texts
    assert get_text("btn_my_orders", "ru") in button_texts
    assert get_text("btn_contact", "ru") in button_texts
    assert get_text("btn_change_lang", "ru") in button_texts


def test_phone_request_kb():
    for lang in ("uz", "ru"):
        kb = phone_request_kb(lang=lang)
        assert isinstance(kb, ReplyKeyboardMarkup)
        assert kb.resize_keyboard is True

        all_buttons = [btn for row in kb.keyboard for btn in row]
        contact_buttons = [btn for btn in all_buttons if btn.request_contact]
        assert len(contact_buttons) == 1
        assert contact_buttons[0].text == get_text("btn_send_phone", lang)

        button_texts = [btn.text for btn in all_buttons]
        assert get_text("cancel_btn", lang) in button_texts


def test_location_request_kb():
    for lang in ("uz", "ru"):
        kb = location_request_kb(lang=lang)
        assert isinstance(kb, ReplyKeyboardMarkup)
        assert kb.resize_keyboard is True

        all_buttons = [btn for row in kb.keyboard for btn in row]
        location_buttons = [btn for btn in all_buttons if btn.request_location]
        assert len(location_buttons) == 1
        assert location_buttons[0].text == get_text("btn_send_location", lang)

        button_texts = [btn.text for btn in all_buttons]
        assert get_text("cancel_btn", lang) in button_texts


def test_cancel_kb():
    for lang in ("uz", "ru"):
        kb = cancel_kb(lang=lang)
        assert isinstance(kb, ReplyKeyboardMarkup)
        assert kb.resize_keyboard is True

        button_texts = [btn.text for row in kb.keyboard for btn in row]
        assert button_texts == [get_text("cancel_btn", lang)]


def test_skip_or_cancel_kb():
    for lang in ("uz", "ru"):
        kb = skip_or_cancel_kb(lang=lang)
        assert isinstance(kb, ReplyKeyboardMarkup)
        assert kb.resize_keyboard is True

        button_texts = [btn.text for row in kb.keyboard for btn in row]
        assert get_text("btn_skip", lang) in button_texts
        assert get_text("cancel_btn", lang) in button_texts


# ============================================================================
# Inline Keyboards Tests
# ============================================================================

def test_language_kb():
    kb = language_kb()
    assert isinstance(kb, InlineKeyboardMarkup)

    buttons = [btn for row in kb.inline_keyboard for btn in row]
    callbacks = {btn.callback_data: btn.text for btn in buttons}

    assert "set_lang:uz" in callbacks
    assert "set_lang:ru" in callbacks
    assert "🇺🇿" in callbacks["set_lang:uz"]
    assert "🇷🇺" in callbacks["set_lang:ru"]


def test_categories_kb():
    sample_categories = [
        {"id": 1, "name_uz": "Tortlar", "name_ru": "Торты"},
        {"id": 2, "name_uz": "Kapkeyklar", "name_ru": "Капкейки"},
        {"id": 3, "name_uz": "Pishiriqlar", "name_ru": "Пирожные"},
    ]

    for lang, cat1_name in [("uz", "Tortlar"), ("ru", "Торты")]:
        kb = categories_kb(categories=sample_categories, lang=lang)
        assert isinstance(kb, InlineKeyboardMarkup)

        buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in buttons]
        texts = [btn.text for btn in buttons]

        assert "category:1" in callbacks
        assert "category:2" in callbacks
        assert "category:3" in callbacks
        assert cat1_name in texts
        assert any(btn.callback_data == "to_main_menu" for btn in buttons)


def test_products_list_kb():
    sample_products = [
        {"id": 101, "category_id": 1, "name_uz": "Medovik", "name_ru": "Медовик", "price": 120000},
        {"id": 102, "category_id": 1, "name_uz": "Napoleon", "name_ru": "Наполеон", "price": 140000},
    ]

    for lang, prod1_name in [("uz", "Medovik"), ("ru", "Медовик")]:
        kb = products_list_kb(products=sample_products, category_id=1, lang=lang)
        assert isinstance(kb, InlineKeyboardMarkup)

        buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in buttons]
        texts = [btn.text for btn in buttons]

        assert "product:101" in callbacks
        assert "product:102" in callbacks
        assert any(prod1_name in t for t in texts)
        assert any(btn.callback_data == "to_categories" for btn in buttons)


def test_product_card_kb():
    for lang in ("uz", "ru"):
        kb = product_card_kb(product_id=55, quantity=3, category_id=2, lang=lang)
        assert isinstance(kb, InlineKeyboardMarkup)

        buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in buttons]
        texts = [btn.text for btn in buttons]

        # Quantity adjustment buttons
        assert any(cb.startswith("prod_minus:55:3") for cb in callbacks)
        assert "3" in texts
        assert any(cb.startswith("prod_plus:55:3") for cb in callbacks)

        # Add to cart button
        assert any(cb == "add_cart:55:3" for cb in callbacks)
        assert any(get_text("btn_add_to_cart", lang) in t for t in texts)

        # Navigation buttons: back to category and cart button
        assert any(cb == "category:2" for cb in callbacks)
        assert any(cb == "to_cart" for cb in callbacks)


def test_cart_kb_empty():
    for lang in ("uz", "ru"):
        kb = cart_kb(cart_items=[], lang=lang)
        assert isinstance(kb, InlineKeyboardMarkup)

        buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in buttons]

        # Should prompt to browse catalog
        assert "to_catalog" in callbacks


def test_cart_kb_with_items():
    cart_items = [
        {"product_id": 10, "name_uz": "Medovik", "name_ru": "Медовик", "quantity": 2, "price": 120000, "total_price": 240000},
        {"product_id": 11, "name_uz": "Tiramisu", "name_ru": "Тирамису", "quantity": 1, "price": 45000, "total_price": 45000},
    ]

    for lang in ("uz", "ru"):
        kb = cart_kb(cart_items=cart_items, lang=lang)
        assert isinstance(kb, InlineKeyboardMarkup)

        buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in buttons]

        # Item control callbacks
        assert any("cart_minus:10" in cb or "cart_dec:10" in cb for cb in callbacks)
        assert any("cart_plus:10" in cb or "cart_inc:10" in cb for cb in callbacks)
        assert any("cart_del:10" in cb for cb in callbacks)

        # Checkout, clear, and return buttons
        assert "order_checkout" in callbacks
        assert "cart_clear" in callbacks
        assert any(cb in ("to_main_menu", "to_catalog") for cb in callbacks)


def test_order_time_kb():
    # Store open: both options available
    for lang in ("uz", "ru"):
        kb_open = order_time_kb(lang=lang, store_open=True)
        assert isinstance(kb_open, InlineKeyboardMarkup)

        buttons = [btn for row in kb_open.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in buttons]
        texts = [btn.text for btn in buttons]

        assert "order_time:now" in callbacks
        assert "order_time:scheduled" in callbacks
        assert "order_cancel" in callbacks
        assert any(get_text("btn_time_now", lang) in t for t in texts)
        assert any(get_text("btn_time_scheduled", lang) in t for t in texts)

    # Store closed: only scheduled option available
    for lang in ("uz", "ru"):
        kb_closed = order_time_kb(lang=lang, store_open=False)
        buttons = [btn for row in kb_closed.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in buttons]

        assert "order_time:now" not in callbacks
        assert "order_time:scheduled" in callbacks
        assert "order_cancel" in callbacks


def test_delivery_type_kb():
    for lang in ("uz", "ru"):
        kb = delivery_type_kb(lang=lang)
        assert isinstance(kb, InlineKeyboardMarkup)

        buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in buttons]
        texts = [btn.text for btn in buttons]

        assert "delivery_type:delivery" in callbacks
        assert "delivery_type:pickup" in callbacks
        assert "order_cancel" in callbacks
        assert any(get_text("btn_delivery", lang) in t for t in texts)
        assert any(get_text("btn_pickup", lang) in t for t in texts)


def test_payment_methods_kb():
    for lang in ("uz", "ru"):
        kb = payment_methods_kb(lang=lang)
        assert isinstance(kb, InlineKeyboardMarkup)

        buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in buttons]
        texts = [btn.text for btn in buttons]

        assert "pay_method:click" in callbacks
        assert "pay_method:payme" in callbacks
        assert "pay_method:cash" in callbacks
        assert "order_cancel" in callbacks
        assert any(get_text("btn_pay_click", lang) in t for t in texts)
        assert any(get_text("btn_pay_payme", lang) in t for t in texts)
        assert any(get_text("btn_pay_cash", lang) in t for t in texts)


def test_order_confirm_kb():
    for lang in ("uz", "ru"):
        kb = order_confirm_kb(lang=lang)
        assert isinstance(kb, InlineKeyboardMarkup)

        buttons = [btn for row in kb.inline_keyboard for btn in row]
        callbacks = [btn.callback_data for btn in buttons]
        texts = [btn.text for btn in buttons]

        assert "order_confirm:yes" in callbacks
        assert "order_confirm:cancel" in callbacks
        assert any(get_text("btn_confirm_order", lang) in t for t in texts)
        assert any(get_text("cancel_btn", lang) in t for t in texts)


# ============================================================================
# Admin Keyboards Tests
# ============================================================================

def test_admin_main_kb():
    kb = admin_main_kb()
    assert isinstance(kb, ReplyKeyboardMarkup)
    assert kb.resize_keyboard is True

    button_texts = [btn.text for row in kb.keyboard for btn in row]
    assert any("Statistika" in t or "📊" in t for t in button_texts)
    assert any("Buyurtmalar" in t or "📦" in t for t in button_texts)
    assert any("Mahsulotlar" in t or "🍰" in t for t in button_texts)
    assert any("Bosh menyu" in t or "Asosiy" in t or "⬅️" in t for t in button_texts)


def test_order_admin_actions_kb():
    # Test new status -> action to accept (prepare)
    kb_new = order_admin_actions_kb(order_id=42, current_status="new")
    buttons_new = [btn for row in kb_new.inline_keyboard for btn in row]
    cbs_new = [btn.callback_data for btn in buttons_new]
    assert any("admin_order:preparing:42" in cb for cb in cbs_new)
    assert any("admin_order:cancel:42" in cb for cb in cbs_new)

    # Test preparing status -> action to mark ready
    kb_prep = order_admin_actions_kb(order_id=42, current_status="preparing")
    buttons_prep = [btn for row in kb_prep.inline_keyboard for btn in row]
    cbs_prep = [btn.callback_data for btn in buttons_prep]
    assert any("admin_order:ready:42" in cb for cb in cbs_prep)
    assert any("admin_order:cancel:42" in cb for cb in cbs_prep)

    # Test ready status -> action to deliver
    kb_ready = order_admin_actions_kb(order_id=42, current_status="ready")
    buttons_ready = [btn for row in kb_ready.inline_keyboard for btn in row]
    cbs_ready = [btn.callback_data for btn in buttons_ready]
    assert any("admin_order:delivering:42" in cb for cb in cbs_ready)
    assert any("admin_order:cancel:42" in cb for cb in cbs_ready)

    # Test delivering status -> action to complete
    kb_deliv = order_admin_actions_kb(order_id=42, current_status="delivering")
    buttons_deliv = [btn for row in kb_deliv.inline_keyboard for btn in row]
    cbs_deliv = [btn.callback_data for btn in buttons_deliv]
    assert any("admin_order:delivered:42" in cb for cb in cbs_deliv)
    assert any("admin_order:cancel:42" in cb for cb in cbs_deliv)

    # Test all / empty status -> should contain all action buttons
    kb_all = order_admin_actions_kb(order_id=42, current_status="all")
    buttons_all = [btn for row in kb_all.inline_keyboard for btn in row]
    cbs_all = [btn.callback_data for btn in buttons_all]
    assert any("admin_order:preparing:42" in cb for cb in cbs_all)
    assert any("admin_order:ready:42" in cb for cb in cbs_all)
    assert any("admin_order:delivering:42" in cb for cb in cbs_all)
    assert any("admin_order:delivered:42" in cb for cb in cbs_all)
    assert any("admin_order:cancel:42" in cb for cb in cbs_all)
