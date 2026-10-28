# Task 6 Brief: Katalog va Mahsulotlar Vitrinasi Handlerlari (Catalog)

## Goal
Implement the catalog router (`handlers/catalog.py`) for browsing sweet categories, viewing products, showing appetizing product cards with photos/descriptions/weights/prices, and adjusting quantity into cart directly from the card.

## Files to Create / Modify
- `handlers/__init__.py`
- `handlers/catalog.py`
- `tests/test_catalog_handlers.py`

## Requirements
1. In `handlers/catalog.py`:
   - Define `catalog_router = Router(name="catalog")`.
   - Category navigation:
     * Handle opening catalog via reply button (matches `_t("btn_catalog", "uz")` or `_t("btn_catalog", "ru")`), `/catalog` command, or inline callback `open_catalog`.
     * Show categories keyboard (`categories_kb`).
   - Products list in category:
     * Handle `F.data.startswith("cat_")`.
     * Retrieve products via `crud.get_products_by_category`.
     * Display list using `products_list_kb`.
   - Product details card:
     * Handle `F.data.startswith("prod_")`.
     * Retrieve product via `crud.get_product`.
     * Check if product is already in user's cart (quantity).
     * Format appetizing caption with name, description, weight, and price.
     * Display with `product_card_kb`.
   - Card cart actions:
     * `add_prod_<id>` and `inc_prod_<id>`: increment in cart, update message reply_markup, show toast alert `added_to_cart_alert`.
     * `dec_prod_<id>`: decrement in cart, update message reply_markup.
     * `noop`: answer callback query.
2. In `tests/test_catalog_handlers.py`:
   - Unit tests mocking or using real `aiosqlite` in-memory DB and Aiogram `Message` / `CallbackQuery` objects.
   - Verify category listing, product viewing, and inline cart button callbacks.
3. TDD:
   - Write tests in `tests/test_catalog_handlers.py` first and verify failure.
   - Implement `handlers/catalog.py`.
   - Run tests: `.\.venv\Scripts\pytest tests/test_catalog_handlers.py -v`.
   - Run full suite: `.\.venv\Scripts\pytest -v`.
   - Commit: `git add handlers/ tests/test_catalog_handlers.py` with message `feat: implement catalog and product vitrina handlers`.
