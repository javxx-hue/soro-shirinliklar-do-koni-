"""
Admin package defining administration routers and security filters.
"""
from __future__ import annotations

from typing import Optional
from aiogram import Router
from aiogram.filters import Filter
from aiogram.types import TelegramObject

from shop_config import Config, load_config


class AdminFilter(Filter):
    """Filter ensuring incoming messages or callbacks originate from authorized admin IDs."""

    async def __call__(self, event: TelegramObject, config: Optional[Config] = None) -> bool:
        user = getattr(event, "from_user", None)
        if not user:
            return False
        cfg = config or load_config()
        return user.id in cfg.admin_ids


from .panel import panel_router
from .orders import orders_router
from .products import products_router

admin_router = Router(name="admin")
admin_router.include_router(panel_router)
admin_router.include_router(orders_router)
admin_router.include_router(products_router)

__all__ = [
    "admin_router",
    "AdminFilter",
    "panel_router",
    "orders_router",
    "products_router",
]
