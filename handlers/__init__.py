"""
Handlers package for the sweet shop Telegram bot.
"""
from .catalog import catalog_router
from .cart import cart_router

__all__ = ["catalog_router", "cart_router"]
