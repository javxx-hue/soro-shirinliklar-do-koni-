# Task 11 Brief: Admin Boshqaruvi va Jonli Status Xabarnomalari (Order Lifecycle)

## Goal
Implement the admin panel routers (`handlers/admin/`) and notification service (`services/notifier.py`) to alert shop owners of new orders, allow them to manage product stop-lists, view sales statistics, and advance order statuses with immediate customer live-tracking notifications.

## Files to Create / Modify
- Modify: `handlers/__init__.py` (export `admin_router`)
- Create: `services/notifier.py`
- Create: `handlers/admin/__init__.py`
- Create: `handlers/admin/panel.py`
- Create: `handlers/admin/orders.py`
- Create: `handlers/admin/products.py`
- Create: `tests/test_admin_orders.py`

## Requirements
1. In `services/notifier.py`:
   - `async def notify_admins_new_order(bot: Bot, order: dict, config: Config, order_items: list[dict] | None = None)`:
     * Loops through `config.admin_ids`.
     * Formats complete order details (Customer, phone, address, map link, distance km, items list, total sum, payment type, custom note/cake text).
     * If `order.get('custom_image_id')`: sends photo with details and `order_admin_actions_kb(order['id'], 'new')`.
     * Otherwise sends text message with `order_admin_actions_kb(order['id'], 'new')`.
   - `async def notify_customer_status_change(bot: Bot, user_id: int, order_id: int, new_status: str, lang: str = "uz", cancel_reason: str = "")`:
     * Sends localized status notification to customer:
       - 'confirmed': `_t("status_confirmed", lang)`
       - 'preparing': `_t("status_preparing", lang)`
       - 'delivering': `_t("status_delivering", lang)`
       - 'completed': `_t("status_completed", lang)`
       - 'cancelled': `_t("status_cancelled", lang, reason=cancel_reason)`
2. In `handlers/admin/`:
   - `admin_router = Router(name="admin")`
   - Access filter: restricts commands and callbacks to `user.id in config.admin_ids`.
   - `orders.py`:
     * Handles callbacks:
       - `adm_confirm_<order_id>` -> updates DB to `confirmed`, notifies customer via `notify_customer_status_change`.
       - `adm_ready_<order_id>` -> updates DB to `preparing`, notifies customer.
       - `adm_dispatch_<order_id>` -> updates DB to `delivering`, notifies customer.
       - `adm_complete_<order_id>` -> updates DB to `completed`, notifies customer.
       - `adm_cancel_<order_id>` -> updates DB to `cancelled`, notifies customer.
     * Updates admin message with next action buttons (`order_admin_actions_kb`).
   - `panel.py`:
     * Handles `/admin` command or Admin Menu button.
     * `📊 Statistika`: shows count of total orders, today's sales, and revenue.
     * `📦 Yangi buyurtmalar`: lists active/pending orders with quick action buttons.
   - `products.py`:
     * `🧁 Mahsulotlar (Stop-list)`: lists products showing `[✅ Sotuvda bor]` or `[⛔️ Tugadi (Stop-list)]`.
     * Callback `toggle_prod_<id>`: toggles product availability in DB via `crud.set_product_availability` and refreshes keyboard.
3. In `tests/test_admin_orders.py`:
   - Unit tests covering:
     * `notify_admins_new_order` sending to all admin IDs.
     * `notify_customer_status_change` sending correct localized text for each status.
     * Admin order status transitions (confirm, preparing, delivering, complete, cancel).
     * Non-admin access rejection.
     * Product stop-list toggling.
4. TDD:
   - Write tests first and verify failure.
   - Implement services and admin handlers.
   - Run tests: `.\.venv\Scripts\pytest tests/test_admin_orders.py -v`.
   - Run full suite: `.\.venv\Scripts\pytest -v`.
   - Commit: `git add services/ handlers/admin/ tests/test_admin_orders.py` with message `feat: implement admin panel and live order status notifications`.
