"""
Handlers package for the sweet shop Telegram bot.
"""
from .common import common_router
from .catalog import catalog_router
from .cart import cart_router
from .order import order_router
from .custom_cake import custom_cake_router
from .payments import payments_router
from .admin import admin_router
from .ai_consultant import ai_consultant_router

__all__ = [
    "common_router",
    "catalog_router",
    "cart_router",
    "order_router",
    "custom_cake_router",
    "payments_router",
    "admin_router",
    "ai_consultant_router",
]
