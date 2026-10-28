# Task 10 Brief: To'lovlar Tizimi (Click va Payme Telegram Payments)

## Goal
Implement the Telegram Payments router (`handlers/payments.py`) to support Click and Payme provider invoices, pre-checkout query validation, and successful payment processing.

## Files to Create / Modify
- Modify: `handlers/__init__.py` (export `payments_router`)
- Create: `handlers/payments.py`
- Create: `tests/test_payments.py`

## Requirements
1. In `handlers/payments.py`:
   - Define `payments_router = Router(name="payments")`.
   - `async def send_order_invoice(bot, chat_id, order, provider, config, lang="uz")`:
     * provider: "click" or "payme"
     * selects `provider_token = config.click_token if provider == "click" else config.payme_token`
     * if token missing, sends a graceful message explaining that online payments are in test/demo mode and payment can be completed on delivery or via card.
     * if token present, calls `bot.send_invoice(...)` with:
       - `title`: localized title ("Buyurtma #{order_id}")
       - `description`: localized description
       - `payload`: f"order_{order['id']}"
       - `currency`: "UZS"
       - `prices`: `[LabeledPrice(label="Shirinliklar", amount=order['total_amount'] * 100)]` (UZS is formatted in tiyin, 1 UZS = 100 tiyin)
   - `PreCheckoutQuery` handler:
     * Parses `query.invoice_payload` (e.g. `order_123`)
     * Validates order exists in DB and is not cancelled/already paid.
     * If valid: `await query.answer(ok=True)`
     * If invalid: `await query.answer(ok=False, error_message=...)`
   - `SuccessfulPayment` message handler:
     * Triggered on `F.successful_payment`.
     * Parses order_id from `message.successful_payment.invoice_payload`.
     * Updates payment status via `crud.update_payment_status(db, order_id, "paid")`.
     * Sends localized receipt message to customer confirming payment and order progress.
     * Restores `main_menu_kb`.
2. In `tests/test_payments.py`:
   - Unit tests covering:
     * Invoice generation with valid token and fallback when token is empty.
     * Successful `PreCheckoutQuery` handling for valid order.
     * Failed `PreCheckoutQuery` handling for non-existent order.
     * `SuccessfulPayment` handler updating DB payment status to "paid" and confirming to user.
3. TDD:
   - Write tests first and verify failure.
   - Implement `handlers/payments.py` and register in `handlers/__init__.py`.
   - Run tests: `.\.venv\Scripts\pytest tests/test_payments.py -v`.
   - Run full suite: `.\.venv\Scripts\pytest -v`.
   - Commit: `git add handlers/ tests/test_payments.py` with message `feat: implement Telegram payments for Click and Payme`.
