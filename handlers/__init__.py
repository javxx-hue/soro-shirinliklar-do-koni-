"""
Handlers package for the sweet shop Telegram bot.
"""
from .catalog import catalog_router
from .cart import cart_router
from .order import order_router
from .custom_cake import custom_cake_router
from .payments import payments_router

__all__ = [
    "catalog_router",
    "cart_router",
    "order_router",
    "custom_cake_router",
    "payments_router",
]
