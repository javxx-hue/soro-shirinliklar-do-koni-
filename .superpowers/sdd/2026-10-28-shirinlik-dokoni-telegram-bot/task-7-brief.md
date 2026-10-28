# Task 7 Brief: Savatcha Boshqaruvi Handlerlari (Cart System)

## Goal
Implement the cart router (`handlers/cart.py`) for viewing the shopping cart, increasing/decreasing quantities, removing individual items, clearing the cart, and advancing to checkout.

## Files to Create / Modify
- Modify: `handlers/__init__.py` (export `cart_router`)
- Create: `handlers/cart.py`
- Create: `tests/test_cart_handlers.py`

## Requirements
1. In `handlers/cart.py`:
   - Define `cart_router = Router(name="cart")`.
   - Opening cart:
     * Reply button matching `.*Savatcha.*` / `.*Корзина.*` or `/cart` command or callback query `view_cart`.
     * Retrieve cart from `crud.get_cart(db, user_id)`.
     * If empty: send message `_t("cart_empty", lang)` with button to open catalog (`open_catalog`).
     * If not empty: format appetizing receipt text detailing each item, quantity, unit price, total price, and overall sum.
     * Attach `cart_kb(cart_items, lang)`.
   - Interactive callbacks:
     * `inc_cart_<product_id>`: increment product quantity in cart, recalculate and edit message text & markup.
     * `dec_cart_<product_id>`: decrement quantity (if reaches 0, removes item), update message. If cart becomes empty, show empty cart message.
     * `del_cart_<product_id>`: remove product entirely from cart, update message.
     * `clear_cart`: calls `crud.clear_cart(db, user_id)`, updates message to empty cart view with an alert `_t("cart_cleared", lang)`.
     * `checkout`: if cart is empty, show alert; if not empty, start order flow or emit signal for Order FSM.
2. In `tests/test_cart_handlers.py`:
   - Unit tests covering:
     * Empty cart display.
     * Non-empty cart display with item totals and sum.
     * Increment, decrement, delete, and clear cart callbacks.
     * Handling empty cart attempt on checkout.
3. TDD:
   - Write tests first and verify failure.
   - Implement `handlers/cart.py` and wire into `handlers/__init__.py`.
   - Run tests: `.\.venv\Scripts\pytest tests/test_cart_handlers.py -v`.
   - Run full suite: `.\.venv\Scripts\pytest -v`.
   - Commit: `git add handlers/ tests/test_cart_handlers.py` with message `feat: implement interactive cart management handlers`.
