# Task 9 Brief: 🎨 "O'z Tortingizga Buyurtma" (Custom Cake Flow)

## Goal
Implement the custom cake order flow in `handlers/custom_cake.py` allowing users to upload a photo of their dream cake, specify desired weight and filling, set target event date/time, and provide phone contact for confectioner review.

## Files to Create / Modify
- Modify: `handlers/__init__.py` (export `custom_cake_router`)
- Create: `handlers/custom_cake.py`
- Create: `tests/test_custom_cake.py`

## Requirements
1. In `handlers/custom_cake.py`:
   - Define `custom_cake_router = Router(name="custom_cake")`.
   - `class CustomCakeFSM(StatesGroup)`:
     - `waiting_for_photo = State()`
     - `waiting_for_details = State()`
     - `waiting_for_target_time = State()`
     - `waiting_for_phone = State()`
     - `confirmation = State()`
   - Handlers:
     * Trigger from reply button `.*O'z tortingizga.*` / `.*Заказ торта по фото.*` or command `/custom_cake`.
     * `waiting_for_photo`: accepts `message.photo` (captures `photo[-1].file_id`) or text description with `cancel_kb(lang)`.
     * `waiting_for_details`: asks for desired weight in kg and filling preferences.
     * `waiting_for_target_time`: asks for delivery/event date and time.
     * `waiting_for_phone`: accepts contact or text phone number via `phone_request_kb(lang)`.
     * `confirmation`: shows order preview summary.
     * Upon confirmation: calls `crud.create_order` with `order_type="custom_cake"`, `total_amount=0`, `payment_type="custom_quote"`, `status="new"`, saves `custom_image_id`, `custom_note`, `target_time`.
     * Sends warm confirmation message to user and returns to `main_menu_kb`.
     * Cancel at any point: resets state and returns to `main_menu_kb`.
2. In `tests/test_custom_cake.py`:
   - Unit tests covering:
     * Starting custom cake FSM.
     * Photo upload vs text description.
     * Capturing weight, filling details, target date/time, and phone.
     * Confirming order and verifying it is saved in DB with `order_type="custom_cake"`.
     * Cancellation handling.
3. TDD:
   - Write tests first and verify failure.
   - Implement `handlers/custom_cake.py` and register in `handlers/__init__.py`.
   - Run tests: `.\.venv\Scripts\pytest tests/test_custom_cake.py -v`.
   - Run full suite: `.\.venv\Scripts\pytest -v`.
   - Commit: `git add handlers/ tests/test_custom_cake.py` with message `feat: implement custom cake order by photo flow`.
