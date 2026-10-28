"""
Inline keyboard generators for client navigation, product selection, cart management, and ordering.
"""
from __future__ import annotations

from typing import Any, Dict, List
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from middlewares.i18n import get_text


def language_kb() -> InlineKeyboardMarkup:
    """
    Language selection inline keyboard with Uzbek and Russian options.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="set_lang:uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru"),
            ]
        ]
    )


def categories_kb(categories: List[Dict[str, Any]], lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Renders shop categories as a grid (2 per row) with a back button.
    """
    rows: List[List[InlineKeyboardButton]] = []
    current_row: List[InlineKeyboardButton] = []

    for cat in categories:
        name = cat.get(f"name_{lang}") or cat.get("name_uz") or cat.get("name", "")
        btn = InlineKeyboardButton(text=str(name), callback_data=f"category:{cat['id']}")
        current_row.append(btn)
        if len(current_row) == 2:
            rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    rows.append([
        InlineKeyboardButton(text=get_text("back_btn", lang), callback_data="to_main_menu")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def products_list_kb(
    products: List[Dict[str, Any]],
    category_id: int,
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """
    Renders products in a selected category with item details and back button.
    """
    rows: List[List[InlineKeyboardButton]] = []

    for prod in products:
        name = prod.get(f"name_{lang}") or prod.get("name_uz") or prod.get("name", "")
        price = prod.get("price")
        if price:
            formatted_price = f"{price:,}".replace(",", " ")
            btn_text = f"✨ {name} — {formatted_price} so'm"
        else:
            btn_text = f"✨ {name}"

        rows.append([
            InlineKeyboardButton(text=btn_text, callback_data=f"product:{prod['id']}")
        ])

    rows.append([
        InlineKeyboardButton(text=get_text("back_btn", lang), callback_data="to_categories")
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def product_card_kb(
    product_id: int,
    quantity: int = 1,
    category_id: int = 0,
    lang: str = "uz",
) -> InlineKeyboardMarkup:
    """
    Product card interactive keyboard: quantity modifier (+/-), add to cart, and navigation.
    """
    rows = [
        [
            InlineKeyboardButton(
                text="➖",
                callback_data=f"prod_minus:{product_id}:{quantity}:{category_id}",
            ),
            InlineKeyboardButton(
                text=str(quantity),
                callback_data="noop",
            ),
            InlineKeyboardButton(
                text="➕",
                callback_data=f"prod_plus:{product_id}:{quantity}:{category_id}",
            ),
        ],
        [
            InlineKeyboardButton(
                text=get_text("btn_add_to_cart", lang),
                callback_data=f"add_cart:{product_id}:{quantity}",
            )
        ],
        [
            InlineKeyboardButton(
                text=get_text("back_btn", lang),
                callback_data=f"category:{category_id}",
            ),
            InlineKeyboardButton(
                text=get_text("btn_cart", lang),
                callback_data="to_cart",
            ),
        ],
    ]

    return InlineKeyboardMarkup(inline_keyboard=rows)


def cart_kb(cart_items: List[Dict[str, Any]], lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Generates inline keyboard for shopping cart.
    If empty, returns a button to open the catalog.
    If populated, allows quantity adjustments, clearing, and proceeding to checkout.
    """
    if not cart_items:
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_text("btn_catalog", lang),
                        callback_data="to_catalog",
                    )
                ]
            ]
        )

    rows: List[List[InlineKeyboardButton]] = []

    for item in cart_items:
        prod_id = item.get("product_id") or item.get("id")
        name = item.get(f"name_{lang}") or item.get("name_uz") or item.get("name", "")
        short_name = name[:12] if len(name) > 12 else name
        qty = item.get("quantity", 1)

        rows.append([
            InlineKeyboardButton(text="➖", callback_data=f"cart_minus:{prod_id}"),
            InlineKeyboardButton(text=f"{short_name} ({qty})", callback_data=f"cart_item:{prod_id}"),
            InlineKeyboardButton(text="➕", callback_data=f"cart_plus:{prod_id}"),
            InlineKeyboardButton(text="🗑", callback_data=f"cart_del:{prod_id}"),
        ])

    rows.append([
        InlineKeyboardButton(
            text=get_text("btn_checkout", lang),
            callback_data="order_checkout",
        )
    ])
    rows.append([
        InlineKeyboardButton(
            text=get_text("btn_clear_cart", lang),
            callback_data="cart_clear",
        )
    ])
    rows.append([
        InlineKeyboardButton(
            text=get_text("btn_catalog", lang),
            callback_data="to_catalog",
        ),
        InlineKeyboardButton(
            text=get_text("back_btn", lang),
            callback_data="to_main_menu",
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def order_time_kb(lang: str = "uz", store_open: bool = True) -> InlineKeyboardMarkup:
    """
    Presents order timing options. When store is closed, only scheduled delivery is available.
    """
    rows: List[List[InlineKeyboardButton]] = []
    if store_open:
        rows.append([
            InlineKeyboardButton(
                text=get_text("btn_time_now", lang),
                callback_data="order_time:now",
            )
        ])

    rows.append([
        InlineKeyboardButton(
            text=get_text("btn_time_scheduled", lang),
            callback_data="order_time:scheduled",
        )
    ])
    rows.append([
        InlineKeyboardButton(
            text=get_text("cancel_btn", lang),
            callback_data="order_cancel",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def delivery_type_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Presents delivery choices: Courier delivery vs Self-pickup.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_delivery", lang),
                    callback_data="delivery_type:delivery",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_pickup", lang),
                    callback_data="delivery_type:pickup",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=get_text("cancel_btn", lang),
                    callback_data="order_cancel",
                )
            ],
        ]
    )


def payment_methods_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Presents supported payment gateways: Click, Payme, and Cash/Card on delivery.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_pay_click", lang),
                    callback_data="pay_method:click",
                ),
                InlineKeyboardButton(
                    text=get_text("btn_pay_payme", lang),
                    callback_data="pay_method:payme",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=get_text("btn_pay_cash", lang),
                    callback_data="pay_method:cash",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("cancel_btn", lang),
                    callback_data="order_cancel",
                )
            ],
        ]
    )


def order_confirm_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """
    Final confirmation prompt before placing an order.
    """
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_text("btn_confirm_order", lang),
                    callback_data="order_confirm:yes",
                )
            ],
            [
                InlineKeyboardButton(
                    text=get_text("cancel_btn", lang),
                    callback_data="order_confirm:cancel",
                )
            ],
        ]
    )
