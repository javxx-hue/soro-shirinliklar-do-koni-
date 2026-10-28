# Task 8 Brief: Buyurtma Rasmiylashtirish FSM Oqimi (Order Placement Flow)

## Goal
Implement the end-to-end Order Placement FSM in `handlers/order.py` connecting cart checkout to a confirmed order in the database, with step-by-step guidance, pre-order time selection, distance & delivery cost calculation, contact sharing, custom cake note/postcard input, payment method selection, and final order confirmation.

## Files to Create / Modify
- Modify: `handlers/__init__.py` (export `order_router`)
- Create: `handlers/order.py`
- Create: `tests/test_order_fsm.py`

## Requirements
1. In `handlers/order.py`:
   - Define `order_router = Router(name="order")`.
   - `class OrderFSM(StatesGroup)`:
     - `waiting_for_time = State()`
     - `waiting_for_preorder_time = State()`
     - `waiting_for_delivery_type = State()`
     - `waiting_for_location = State()`
     - `waiting_for_phone = State()`
     - `waiting_for_note = State()`
     - `waiting_for_payment = State()`
     - `confirmation = State()`
   - Flow triggers:
     - Initiated from `checkout` callback or `_t("btn_checkout")`.
     - Check cart: if empty, alert user and do not start FSM.
   - Step 1 (Time):
     - Displays `order_time_kb(lang, store_open=is_store_open(config))`.
     - `time_now`: sets `target_time = "hozir"` -> asks delivery type.
     - `time_preorder`: prompts user for target date/time string -> sets `target_time = text` -> asks delivery type.
   - Step 2 (Delivery Type):
     - `delivery_courier`: prompts for location with `location_request_kb(lang)`.
     - `delivery_pickup`: sets `delivery_cost = 0`, `distance_km = 0`, `address = "Do'kondan olib ketish"` -> skips location, prompts for phone with `phone_request_kb(lang)`.
   - Step 3 (Location):
     - If `message.location`: calculates distance to `config.store_lat, config.store_lon` using `services.delivery.calculate_distance_km`.
     - Calculates `delivery_cost` using `calculate_delivery_cost`.
     - Formats address with maps link.
     - If `message.text`: sets address text, default delivery cost.
     - Informs user about distance and delivery fee (or congratulates if free delivery threshold reached).
     - Advances to `waiting_for_phone`.
   - Step 4 (Phone):
     - Accepts `message.contact.phone_number` or text phone.
     - Saves phone in DB via `crud.set_user_phone`.
     - Prompts for cake note/postcard text with `skip_or_cancel_kb(lang)`.
     - Advances to `waiting_for_note`.
   - Step 5 (Cake Note / Tabriknoma):
     - Accepts text note or skip button (`btn_skip`).
     - Shows payment methods with `payment_methods_kb(lang)`.
     - Advances to `waiting_for_payment`.
   - Step 6 (Payment & Summary Chek):
     - Accepts `pay_cash`, `pay_card`, `pay_click`, `pay_payme`.
     - Compiles full order summary with all details, items, delivery fee, grand total.
     - Shows `order_confirm_kb(lang)`.
     - Advances to `confirmation`.
   - Step 7 (Confirmation):
     - `confirm_order`:
       * Saves order in DB via `crud.create_order`.
       * Clears user's cart via `crud.clear_cart`.
       * Clears FSM state.
       * Sends success message with order number and tracking status.
       * Restores main menu (`main_menu_kb`).
     - `cancel_order` or `btn_cancel`:
       * Clears FSM state.
       * Sends cancellation message and restores main menu.
2. In `tests/test_order_fsm.py`:
   - Comprehensive async test suite covering:
     * Full delivery flow: Time -> Courier -> Location -> Phone -> Note -> Cash -> Confirm -> Order saved in DB.
     * Pickup flow: Time -> Pickup (skips location) -> Phone -> Skip note -> Confirm.
     * Cancellation at any step.
3. TDD:
   - Write tests first and verify failure.
   - Implement `handlers/order.py` and register in `handlers/__init__.py`.
   - Run tests: `.\.venv\Scripts\pytest tests/test_order_fsm.py -v`.
   - Run full suite: `.\.venv\Scripts\pytest -v`.
   - Commit: `git add handlers/ tests/test_order_fsm.py` with message `feat: implement full order placement FSM flow`.
