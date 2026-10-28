"""
Catalog and product vitrina handlers for browsing sweets, displaying details cards,
and managing product quantities into cart directly from cards.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional
import aiosqlite

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.exceptions import TelegramBadRequest

from database import crud
from database.db import get_db_connection
from keyboards.inline import categories_kb, products_list_kb, product_card_kb
from keyboards.reply import main_menu_kb
from middlewares.i18n import get_text

catalog_router = Router(name="catalog")


async def _resolve_db(db: Optional[aiosqlite.Connection]) -> aiosqlite.Connection:
    """Returns active database connection, creating one if not supplied."""
    if db is not None:
        return db
    return await get_db_connection()


# ============================================================================
# 1. Category Navigation Handlers
# ============================================================================

@catalog_router.message(Command("catalog"))
@catalog_router.message(
    F.text.in_([
        get_text("btn_catalog", "uz"),
        get_text("btn_catalog", "ru"),
    ])
    | F.text.casefold().contains("katalog")
    | F.text.casefold().contains("каталог")
)
async def open_catalog_message(
    message: Message,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Displays list of sweet categories upon message command or menu reply button click."""
    conn = await _resolve_db(db)
    categories = await crud.get_categories(conn, only_active=True)
    text = _t("select_category") if _t else get_text("select_category", lang)
    kb = categories_kb(categories=categories, lang=lang)
    await message.answer(text, reply_markup=kb)


@catalog_router.callback_query(
    F.data.in_(["open_catalog", "to_catalog", "to_categories"])
)
async def open_catalog_callback(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Displays or returns back to list of categories upon inline callback."""
    conn = await _resolve_db(db)
    categories = await crud.get_categories(conn, only_active=True)
    text = _t("select_category") if _t else get_text("select_category", lang)
    kb = categories_kb(categories=categories, lang=lang)

    await callback.answer()
    if callback.message:
        if getattr(callback.message, "photo", None):
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, reply_markup=kb)
        else:
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except Exception:
                await callback.message.answer(text, reply_markup=kb)


@catalog_router.callback_query(F.data == "to_main_menu")
async def handle_to_main_menu(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Returns user back to main menu from inline catalog view."""
    await callback.answer()
    if callback.message:
        text = _t("main_menu") if _t else get_text("main_menu", lang)
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=main_menu_kb(lang=lang))


# ============================================================================
# 2. Products List in Category
# ============================================================================

@catalog_router.callback_query(
    F.data.startswith("cat_") | F.data.startswith("category:")
)
async def show_category_products(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """Displays available sweet products inside the selected category."""
    data = callback.data or ""
    raw_id = data.split(":", 1)[1] if ":" in data else data.split("_", 1)[1]
    try:
        category_id = int(raw_id)
    except (ValueError, IndexError):
        await callback.answer()
        return

    conn = await _resolve_db(db)
    products = await crud.get_products_by_category(conn, category_id=category_id, only_available=True)

    await callback.answer()
    if not products:
        empty_text = _t("category_empty") if _t else get_text("category_empty", lang)
        back_kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=get_text("back_btn", lang), callback_data="to_categories")]]
        )
        if callback.message:
            if getattr(callback.message, "photo", None):
                try:
                    await callback.message.delete()
                except Exception:
                    pass
                await callback.message.answer(empty_text, reply_markup=back_kb)
            else:
                try:
                    await callback.message.edit_text(empty_text, reply_markup=back_kb)
                except Exception:
                    await callback.message.answer(empty_text, reply_markup=back_kb)
        return

    text = _t("select_product") if _t else get_text("select_product", lang)
    kb = products_list_kb(products=products, category_id=category_id, lang=lang)

    if callback.message:
        if getattr(callback.message, "photo", None):
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(text, reply_markup=kb)
        else:
            try:
                await callback.message.edit_text(text, reply_markup=kb)
            except Exception:
                await callback.message.answer(text, reply_markup=kb)


# ============================================================================
# 3. Product Details Card
# ============================================================================

@catalog_router.callback_query(
    F.data.regexp(r"^(prod_|product:)(\d+)$")
)
async def show_product_card(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Renders appetizing product card with photo, name, description, weight,
    formatted price, and interactive +/- cart adjustment buttons.
    """
    data = callback.data or ""
    product_id_str = data.split(":" if ":" in data else "_")[-1]
    try:
        product_id = int(product_id_str)
    except ValueError:
        await callback.answer()
        return

    conn = await _resolve_db(db)
    product = await crud.get_product(conn, product_id=product_id)

    if not product or product.get("is_available") == 0:
        not_avail = _t("product_not_available") if _t else get_text("product_not_available", lang)
        await callback.answer(not_avail, show_alert=True)
        return

    user_id = callback.from_user.id if callback.from_user else 0
    cart_items = await crud.get_cart(conn, user_id=user_id)
    cart_item = next((item for item in cart_items if item["product_id"] == product_id), None)
    current_qty = cart_item["quantity"] if cart_item else 1

    name = product.get(f"name_{lang}") or product.get("name_uz") or ""
    desc = product.get(f"description_{lang}") or product.get("description_uz") or ""
    weight = product.get("weight") or ""
    price = product.get("price", 0)
    formatted_price = f"{price:,}".replace(",", " ")

    caption = _t(
        "product_card_template",
        name=name,
        description=desc,
        weight=weight,
        price=formatted_price,
    ) if _t else get_text(
        "product_card_template",
        lang=lang,
        name=name,
        description=desc,
        weight=weight,
        price=formatted_price,
    )

    category_id = product.get("category_id", 0)
    kb = product_card_kb(
        product_id=product_id,
        quantity=current_qty,
        category_id=category_id,
        lang=lang,
    )

    await callback.answer()
    photo_id = product.get("photo_id")
    if photo_id and photo_id.strip():
        if callback.message:
            try:
                await callback.message.delete()
            except Exception:
                pass
            try:
                await callback.message.answer_photo(
                    photo=photo_id,
                    caption=caption,
                    reply_markup=kb,
                )
                return
            except Exception:
                pass

    if callback.message:
        if getattr(callback.message, "photo", None):
            try:
                await callback.message.delete()
            except Exception:
                pass
            await callback.message.answer(caption, reply_markup=kb)
        else:
            try:
                await callback.message.edit_text(caption, reply_markup=kb)
            except Exception:
                await callback.message.answer(caption, reply_markup=kb)


# ============================================================================
# 4. Card Cart Actions (+ / - / Add to Cart / Noop)
# ============================================================================

@catalog_router.callback_query(
    F.data.startswith("add_prod_")
    | F.data.startswith("inc_prod_")
    | F.data.startswith("dec_prod_")
    | F.data.startswith("prod_plus:")
    | F.data.startswith("prod_minus:")
    | F.data.startswith("add_cart:")
)
async def handle_card_cart_action(
    callback: CallbackQuery,
    db: Optional[aiosqlite.Connection] = None,
    lang: str = "uz",
    _t: Optional[Callable[..., str]] = None,
) -> None:
    """
    Handles inline cart modifications directly on product card:
    - add_prod_<id> / inc_prod_<id>: increments in cart, shows toast alert, updates reply_markup
    - dec_prod_<id>: decrements in cart, updates reply_markup
    - prod_plus / prod_minus: interactive quantity adjustments
    - add_cart: adds specified quantity to cart
    """
    data = callback.data or ""
    conn = await _resolve_db(db)
    user_id = callback.from_user.id if callback.from_user else 0

    # 1. add_prod_<id> or inc_prod_<id>
    if data.startswith("add_prod_") or data.startswith("inc_prod_"):
        product_id = int(data.split("_")[-1])
        await crud.add_to_cart(conn, user_id=user_id, product_id=product_id, quantity=1)

        product = await crud.get_product(conn, product_id=product_id)
        cart = await crud.get_cart(conn, user_id=user_id)
        item = next((i for i in cart if i["product_id"] == product_id), None)
        new_qty = item["quantity"] if item else 1
        category_id = product.get("category_id", 0) if product else 0

        new_kb = product_card_kb(
            product_id=product_id,
            quantity=new_qty,
            category_id=category_id,
            lang=lang,
        )
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=new_kb)
            except TelegramBadRequest:
                pass

        alert_msg = _t("added_to_cart_alert") if _t else get_text("added_to_cart_alert", lang)
        if alert_msg == "added_to_cart_alert":
            prod_name = product.get(f"name_{lang}") or product.get("name_uz", "") if product else ""
            alert_msg = _t("product_added_to_cart", product_name=prod_name, quantity=new_qty) if _t else get_text(
                "product_added_to_cart", lang=lang, product_name=prod_name, quantity=new_qty
            )
        await callback.answer(alert_msg)
        return

    # 2. dec_prod_<id>
    if data.startswith("dec_prod_"):
        product_id = int(data.split("_")[-1])
        cart = await crud.get_cart(conn, user_id=user_id)
        item = next((i for i in cart if i["product_id"] == product_id), None)
        current_qty = item["quantity"] if item else 0
        new_qty = max(0, current_qty - 1)

        await crud.set_cart_item_quantity(conn, user_id=user_id, product_id=product_id, quantity=new_qty)

        product = await crud.get_product(conn, product_id=product_id)
        category_id = product.get("category_id", 0) if product else 0
        display_qty = max(1, new_qty)

        new_kb = product_card_kb(
            product_id=product_id,
            quantity=display_qty,
            category_id=category_id,
            lang=lang,
        )
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=new_kb)
            except TelegramBadRequest:
                pass

        await callback.answer()
        return

    # 3. prod_plus:<product_id>:<quantity>:<category_id>
    if data.startswith("prod_plus:"):
        parts = data.split(":")
        product_id, qty, category_id = int(parts[1]), int(parts[2]), int(parts[3])
        new_qty = qty + 1
        new_kb = product_card_kb(
            product_id=product_id,
            quantity=new_qty,
            category_id=category_id,
            lang=lang,
        )
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=new_kb)
            except TelegramBadRequest:
                pass
        await callback.answer()
        return

    # 4. prod_minus:<product_id>:<quantity>:<category_id>
    if data.startswith("prod_minus:"):
        parts = data.split(":")
        product_id, qty, category_id = int(parts[1]), int(parts[2]), int(parts[3])
        new_qty = max(1, qty - 1)
        new_kb = product_card_kb(
            product_id=product_id,
            quantity=new_qty,
            category_id=category_id,
            lang=lang,
        )
        if callback.message:
            try:
                await callback.message.edit_reply_markup(reply_markup=new_kb)
            except TelegramBadRequest:
                pass
        await callback.answer()
        return

    # 5. add_cart:<product_id>:<quantity>
    if data.startswith("add_cart:"):
        parts = data.split(":")
        product_id, qty = int(parts[1]), int(parts[2])
        await crud.add_to_cart(conn, user_id=user_id, product_id=product_id, quantity=qty)

        product = await crud.get_product(conn, product_id=product_id)
        alert_msg = _t("added_to_cart_alert") if _t else get_text("added_to_cart_alert", lang)
        if alert_msg == "added_to_cart_alert":
            prod_name = product.get(f"name_{lang}") or product.get("name_uz", "") if product else ""
            alert_msg = _t("product_added_to_cart", product_name=prod_name, quantity=qty) if _t else get_text(
                "product_added_to_cart", lang=lang, product_name=prod_name, quantity=qty
            )
        await callback.answer(alert_msg)
        return


@catalog_router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    """Answers noop callback query without making changes."""
    await callback.answer()
