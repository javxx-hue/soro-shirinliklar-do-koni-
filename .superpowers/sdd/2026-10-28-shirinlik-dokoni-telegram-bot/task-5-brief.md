# Task 5 Brief: Klaviaturani Yaratish (Reply & Inline Keyboards)

## Goal
Implement all Reply and Inline keyboards for client and admin interfaces using `aiogram.types` (`ReplyKeyboardMarkup`, `KeyboardButton`, `InlineKeyboardMarkup`, `InlineKeyboardButton`), integrated with `middlewares/i18n.py` (`get_text`).

## Files to Create
- `keyboards/__init__.py`
- `keyboards/reply.py`
- `keyboards/inline.py`
- `keyboards/admin_kb.py`
- `tests/test_keyboards.py`

## Requirements
1. `keyboards/reply.py`:
   - `main_menu_kb(lang="uz", cart_count=0, is_admin=False) -> ReplyKeyboardMarkup`
   - `phone_request_kb(lang="uz") -> ReplyKeyboardMarkup` (with `request_contact=True`)
   - `location_request_kb(lang="uz") -> ReplyKeyboardMarkup` (with `request_location=True`)
   - `cancel_kb(lang="uz") -> ReplyKeyboardMarkup`
   - `skip_or_cancel_kb(lang="uz") -> ReplyKeyboardMarkup`
2. `keyboards/inline.py`:
   - `language_kb() -> InlineKeyboardMarkup`
   - `categories_kb(categories: list[dict], lang="uz") -> InlineKeyboardMarkup`
   - `products_list_kb(products: list[dict], category_id: int, lang="uz") -> InlineKeyboardMarkup`
   - `product_card_kb(product_id: int, quantity: int, category_id: int, lang="uz") -> InlineKeyboardMarkup`
   - `cart_kb(cart_items: list[dict], lang="uz") -> InlineKeyboardMarkup`
   - `order_time_kb(lang="uz", store_open: bool = True) -> InlineKeyboardMarkup`
   - `delivery_type_kb(lang="uz") -> InlineKeyboardMarkup`
   - `payment_methods_kb(lang="uz") -> InlineKeyboardMarkup`
   - `order_confirm_kb(lang="uz") -> InlineKeyboardMarkup`
3. `keyboards/admin_kb.py`:
   - `admin_main_kb() -> ReplyKeyboardMarkup`
   - `order_admin_actions_kb(order_id: int, current_status: str) -> InlineKeyboardMarkup`
4. `tests/test_keyboards.py`:
   - Test that all keyboard generator functions return valid Aiogram keyboard objects with expected buttons and callbacks in both 'uz' and 'ru' languages.
5. TDD:
   - Write tests first and ensure FAIL.
   - Implement the keyboards.
   - Run tests: `.\.venv\Scripts\pytest tests/test_keyboards.py -v`.
   - Run full suite: `.\.venv\Scripts\pytest -v`.
   - Commit: `git add keyboards/ tests/test_keyboards.py` with message `feat: implement reply and inline keyboards for client and admin`.
