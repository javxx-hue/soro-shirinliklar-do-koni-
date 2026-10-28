# Task 2 Brief: Ma'lumotlar Bazasi va CRUD Funksiyalari (Database & CRUD)

## Goal
Implement asynchronous SQLite database initialization and full CRUD operations for the sweet shop:
- Tables: `users`, `categories`, `products`, `cart`, `orders`, `order_items`, `settings`
- Pre-populate default sweet shop categories and sample delicious cakes/pastries if database is empty.
- CRUD operations for users, categories, products (with availability toggle), cart items (add, get, update quantity, remove, clear), orders (create, get, list by user, update status, list pending).

## Files to Create
- `database/__init__.py`
- `database/db.py`
- `database/models.py`
- `database/crud.py`
- `tests/test_database.py`

## Requirements & Specifications
1. Use `aiosqlite` with `row_factory = aiosqlite.Row` (or dictionary converter) so results can be accessed as dicts.
2. In `database/models.py`:
   - Define SQL `CREATE TABLE IF NOT EXISTS` statements:
     * `users`: `id INTEGER PRIMARY KEY AUTOINCREMENT, telegram_id INTEGER UNIQUE NOT NULL, full_name TEXT NOT NULL, username TEXT, phone TEXT, language TEXT DEFAULT 'uz', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
     * `categories`: `id INTEGER PRIMARY KEY AUTOINCREMENT, name_uz TEXT NOT NULL, name_ru TEXT NOT NULL, is_active INTEGER DEFAULT 1, sort_order INTEGER DEFAULT 0`
     * `products`: `id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER REFERENCES categories(id), name_uz TEXT NOT NULL, name_ru TEXT NOT NULL, description_uz TEXT, description_ru TEXT, price INTEGER NOT NULL, weight TEXT, photo_id TEXT, is_available INTEGER DEFAULT 1`
     * `cart`: `id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, product_id INTEGER NOT NULL, quantity INTEGER NOT NULL DEFAULT 1, UNIQUE(user_id, product_id)`
     * `orders`: `id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, order_type TEXT DEFAULT 'standard', total_amount INTEGER NOT NULL, delivery_cost INTEGER DEFAULT 0, delivery_type TEXT NOT NULL, target_time TEXT NOT NULL, address TEXT, latitude REAL, longitude REAL, distance_km REAL DEFAULT 0, phone TEXT NOT NULL, custom_note TEXT, custom_image_id TEXT, payment_type TEXT NOT NULL, payment_status TEXT DEFAULT 'pending', status TEXT DEFAULT 'new', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP`
     * `order_items`: `id INTEGER PRIMARY KEY AUTOINCREMENT, order_id INTEGER REFERENCES orders(id), product_id INTEGER REFERENCES products(id), quantity INTEGER NOT NULL, price_at_purchase INTEGER NOT NULL`
     * `settings`: `key TEXT PRIMARY KEY, value TEXT NOT NULL`
3. In `database/db.py`:
   - `async def init_db(db_or_path)` - creates all tables and, if `categories` is empty, seeds starter categories:
     - "🎂 Tortlar" / "🎂 Торты"
     - "🧁 Kapkeyklar va Pirojniylar" / "🧁 Капкейки и Пирожные"
     - "🥐 Shirin pishiriqlar" / "🥐 Сладкая выпечка"
     - "🍫 Shokolad va konfetlar" / "🍫 Шоколад и конфеты"
     and seeds sample starter products (e.g. Medovik, Krasniy Barxat, San-Sebastian, Shokoladli Kapkeyk) with mouthwatering descriptions, realistic prices (e.g. 150000, 180000, 160000) and weights.
   - `async def get_db_connection(db_path: str = "data/shop.db") -> aiosqlite.Connection`
4. In `database/crud.py`:
   - Users:
     * `async def upsert_user(db, telegram_id, full_name, username=None, phone=None, language='uz') -> dict`
     * `async def get_user(db, telegram_id) -> dict | None`
     * `async def set_user_language(db, telegram_id, language: str) -> None`
     * `async def set_user_phone(db, telegram_id, phone: str) -> None`
   - Categories & Products:
     * `async def get_categories(db, only_active=True) -> list[dict]`
     * `async def add_category(db, name_uz, name_ru, sort_order=0) -> int`
     * `async def get_products_by_category(db, category_id, only_available=True) -> list[dict]`
     * `async def get_product(db, product_id) -> dict | None`
     * `async def add_product(db, category_id, name_uz, name_ru, description_uz, description_ru, price, weight, photo_id="", is_available=1) -> int`
     * `async def set_product_availability(db, product_id, is_available: int) -> None`
     * `async def search_products(db, query: str) -> list[dict]`
     * `async def get_all_available_products(db) -> list[dict]`
   - Cart:
     * `async def add_to_cart(db, user_id, product_id, quantity=1) -> None` (upserts: if exists, increment quantity)
     * `async def set_cart_item_quantity(db, user_id, product_id, quantity) -> None` (if <=0, removes)
     * `async def get_cart(db, user_id) -> list[dict]` (joins products to include name_uz, name_ru, price, photo_id, total_price = price * quantity)
     * `async def get_cart_total(db, user_id) -> int`
     * `async def remove_from_cart(db, user_id, product_id) -> None`
     * `async def clear_cart(db, user_id) -> None`
   - Orders:
     * `async def create_order(db, user_id, order_type, total_amount, delivery_cost, delivery_type, target_time, address, latitude, longitude, distance_km, phone, custom_note, payment_type, custom_image_id=None, cart_items=None) -> int`
     * `async def get_order(db, order_id) -> dict | None`
     * `async def get_order_items(db, order_id) -> list[dict]`
     * `async def update_order_status(db, order_id, status: str) -> None`
     * `async def update_payment_status(db, order_id, payment_status: str) -> None`
     * `async def get_user_orders(db, user_id, limit=10) -> list[dict]`
     * `async def get_all_orders(db, limit=50) -> list[dict]`
5. In `tests/test_database.py`:
   - Comprehensive test suite testing all the above CRUD methods on an in-memory SQLite database (`:memory:`).
6. TDD:
   - First write `tests/test_database.py` and run it to verify failure.
   - Implement `database/models.py`, `database/db.py`, `database/crud.py`.
   - Run tests: `.\.venv\Scripts\pytest tests/test_database.py -v`.
   - Commit: `git add database/ tests/test_database.py` and commit with message `feat: implement database models and async CRUD operations`.
