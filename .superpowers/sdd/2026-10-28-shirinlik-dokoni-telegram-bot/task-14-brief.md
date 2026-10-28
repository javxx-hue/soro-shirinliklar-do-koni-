# Task 14 Brief: To'liq Tizim Sinovi (End-to-End Verification)

## Goal
Implement comprehensive end-to-end integration tests in `tests/test_e2e_flow.py` covering the entire lifecycle across all subsystems: customer onboarding, catalog browsing, cart operations, delivery calculation, personalized cake notes, cash and online payments, custom cake photo requests, grounded AI sommelier consultations, and full admin order processing lifecycle.

## Files to Create
- Create: `tests/test_e2e_flow.py`

## Requirements
1. Implement in `tests/test_e2e_flow.py`:
   - `test_e2e_customer_order_and_admin_lifecycle`:
     * Start bot with `/start` -> select Uzbek.
     * Browse category "Tortlar" -> view product -> add 2 Medovik to cart.
     * View cart -> checkout.
     * Select time ("hozir") -> Select courier delivery.
     * Send GPS location -> verify distance and delivery threshold.
     * Send phone -> Send personalized cake note ("Tug'ilgan kuningiz bilan!").
     * Select cash payment -> Confirm order.
     * Verify DB state: order exists, order_items linked, cart is empty.
     * Admin lifecycle: new -> confirmed -> preparing -> delivering -> completed. Verify customer notification sent at each transition.
   - `test_e2e_custom_cake_request`:
     * Start custom cake flow -> upload photo file_id -> specify weight & filling -> specify target date -> specify phone -> confirm.
     * Verify DB state: order_type is "custom_cake", image_id and note saved.
   - `test_e2e_ai_sommelier_consultation`:
     * Start AI consultation -> ask for cake recommendation -> verify response contains real database products and navigation markup.
   - `test_e2e_telegram_payments`:
     * PreCheckoutQuery validation -> SuccessfulPayment DB update to "paid" -> receipt confirmation.
2. Run full test suite:
   - `.\.venv\Scripts\pytest -v`
   - All tests must pass with 100% green status.
3. Commit:
   - `git add tests/test_e2e_flow.py`
   - `git commit -m "test: implement comprehensive end-to-end integration tests"`
