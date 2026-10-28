"""
SQL Schema and table definitions for sweet shop database.
"""

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    full_name TEXT NOT NULL,
    username TEXT,
    phone TEXT,
    language TEXT DEFAULT 'uz',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_CATEGORIES_TABLE = """
CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_uz TEXT NOT NULL,
    name_ru TEXT NOT NULL,
    is_active INTEGER DEFAULT 1,
    sort_order INTEGER DEFAULT 0
);
"""

CREATE_PRODUCTS_TABLE = """
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER REFERENCES categories(id),
    name_uz TEXT NOT NULL,
    name_ru TEXT NOT NULL,
    description_uz TEXT,
    description_ru TEXT,
    price INTEGER NOT NULL,
    weight TEXT,
    photo_id TEXT,
    is_available INTEGER DEFAULT 1
);
"""

CREATE_CART_TABLE = """
CREATE TABLE IF NOT EXISTS cart (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    UNIQUE(user_id, product_id)
);
"""

CREATE_ORDERS_TABLE = """
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    order_type TEXT DEFAULT 'standard',
    total_amount INTEGER NOT NULL,
    delivery_cost INTEGER DEFAULT 0,
    delivery_type TEXT NOT NULL,
    target_time TEXT NOT NULL,
    address TEXT,
    latitude REAL,
    longitude REAL,
    distance_km REAL DEFAULT 0,
    phone TEXT NOT NULL,
    custom_note TEXT,
    custom_image_id TEXT,
    payment_type TEXT NOT NULL,
    payment_status TEXT DEFAULT 'pending',
    status TEXT DEFAULT 'new',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_ORDER_ITEMS_TABLE = """
CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER REFERENCES orders(id),
    product_id INTEGER REFERENCES products(id),
    quantity INTEGER NOT NULL,
    price_at_purchase INTEGER NOT NULL
);
"""

CREATE_SETTINGS_TABLE = """
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

ALL_TABLES = [
    CREATE_USERS_TABLE,
    CREATE_CATEGORIES_TABLE,
    CREATE_PRODUCTS_TABLE,
    CREATE_CART_TABLE,
    CREATE_ORDERS_TABLE,
    CREATE_ORDER_ITEMS_TABLE,
    CREATE_SETTINGS_TABLE,
]

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);",
    "CREATE INDEX IF NOT EXISTS idx_products_category_id ON products(category_id);",
    "CREATE INDEX IF NOT EXISTS idx_cart_user_id ON cart(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);",
]
