"""
Reply keyboard generators for client interface.
Supports Uzbek and Russian localizations, contact/location requests, and main navigation.
"""
from __future__ import annotations

from typing import Optional
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from middlewares.i18n import get_text


def main_menu_kb(
    lang: str = "uz",
    cart_count: int = 0,
    is_admin: bool = False,
) -> ReplyKeyboardMarkup:
    """
    Generates the main navigation reply keyboard.
    If cart_count > 0, appends count in parentheses to the cart button label.
    If is_admin is True, includes a button to access the admin panel.
    """
    cart_label = get_text("btn_cart", lang)
    if cart_count > 0:
        cart_label = f"{cart_label} ({cart_count})"

    keyboard = [
        [
            KeyboardButton(text=get_text("btn_catalog", lang)),
            KeyboardButton(text=cart_label),
        ],
        [
            KeyboardButton(text=get_text("btn_custom_cake", lang)),
            KeyboardButton(text=get_text("btn_ai_consultant", lang)),
        ],
        [
            KeyboardButton(text=get_text("btn_my_orders", lang)),
            KeyboardButton(text=get_text("btn_contact", lang)),
        ],
        [
            KeyboardButton(text=get_text("btn_change_lang", lang)),
        ],
    ]

    if is_admin:
        keyboard.append([KeyboardButton(text=get_text("admin_panel_title", lang))])

    return ReplyKeyboardMarkup(
        keyboard=keyboard,
        resize_keyboard=True,
    )


def phone_request_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """
    Generates a keyboard requesting the user's phone contact.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text("btn_send_phone", lang), request_contact=True)],
            [KeyboardButton(text=get_text("cancel_btn", lang))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def location_request_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """
    Generates a keyboard requesting the user's live or GPS location.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text("btn_send_location", lang), request_location=True)],
            [KeyboardButton(text=get_text("cancel_btn", lang))],
        ],
        resize_keyboard=True,
    )


def cancel_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """
    Generates a keyboard with only a cancel button.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text("cancel_btn", lang))],
        ],
        resize_keyboard=True,
    )


def skip_or_cancel_kb(lang: str = "uz") -> ReplyKeyboardMarkup:
    """
    Generates a keyboard with skip and cancel buttons.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=get_text("btn_skip", lang))],
            [KeyboardButton(text=get_text("cancel_btn", lang))],
        ],
        resize_keyboard=True,
    )
