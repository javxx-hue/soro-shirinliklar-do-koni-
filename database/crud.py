"""
Asynchronous CRUD operations for users, categories, products, cart, orders, and settings.
"""
from typing import Any, Dict, List, Optional
import aiosqlite


# ==========================================
# USERS
# ==========================================

async def upsert_user(
    db: aiosqlite.Connection,
    telegram_id: int,
    full_name: str,
    username: Optional[str] = None,
    phone: Optional[str] = None,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Inserts a new user or updates existing user details, preserving existing phone/language if None."""
    existing = await get_user(db, telegram_id)
    if existing:
        await db.execute(
            """
            UPDATE users
            SET full_name = ?,
                username = COALESCE(?, username),
                phone = COALESCE(?, phone),
                language = COALESCE(?, language)
            WHERE telegram_id = ?;
            """,
            (full_name, username, phone, language, telegram_id),
        )
    else:
        lang = language if language else "uz"
        await db.execute(
            """
            INSERT INTO users (telegram_id, full_name, username, phone, language)
            VALUES (?, ?, ?, ?, ?);
            """,
            (telegram_id, full_name, username, phone, lang),
        )
    await db.commit()
    user = await get_user(db, telegram_id)
    return user or {}


async def get_user(db: aiosqlite.Connection, telegram_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a user by telegram_id as a dictionary."""
    async with db.execute("SELECT * FROM users WHERE telegram_id = ?;", (telegram_id,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def set_user_language(db: aiosqlite.Connection, telegram_id: int, language: str) -> None:
    """Updates user's preferred language."""
    await db.execute("UPDATE users SET language = ? WHERE telegram_id = ?;", (language, telegram_id))
    await db.commit()


async def set_user_phone(db: aiosqlite.Connection, telegram_id: int, phone: str) -> None:
    """Updates user's phone number."""
    await db.execute("UPDATE users SET phone = ? WHERE telegram_id = ?;", (phone, telegram_id))
    await db.commit()


# ==========================================
# CATEGORIES & PRODUCTS
# ==========================================

async def get_categories(db: aiosqlite.Connection, only_active: bool = True) -> List[Dict[str, Any]]:
    """Returns sweet shop categories sorted by sort_order and id."""
    query = "SELECT * FROM categories"
    if only_active:
        query += " WHERE is_active = 1"
    query += " ORDER BY sort_order ASC, id ASC;"

    async with db.execute(query) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def add_category(
    db: aiosqlite.Connection,
    name_uz: str,
    name_ru: str,
    sort_order: int = 0,
    is_active: int = 1,
) -> int:
    """Adds a new product category and returns its ID."""
    cursor = await db.execute(
        """
        INSERT INTO categories (name_uz, name_ru, sort_order, is_active)
        VALUES (?, ?, ?, ?);
        """,
        (name_uz, name_ru, sort_order, is_active),
    )
    await db.commit()
    return cursor.lastrowid or 0


async def get_products_by_category(
    db: aiosqlite.Connection,
    category_id: int,
    only_available: bool = True,
) -> List[Dict[str, Any]]:
    """Retrieves all products belonging to a given category."""
    query = "SELECT * FROM products WHERE category_id = ?"
    params: list = [category_id]
    if only_available:
        query += " AND is_available = 1"
    query += " ORDER BY id ASC;"

    async with db.execute(query, params) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_product(db: aiosqlite.Connection, product_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single product by its primary key ID."""
    async with db.execute("SELECT * FROM products WHERE id = ?;", (product_id,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def add_product(
    db: aiosqlite.Connection,
    category_id: int,
    name_uz: str,
    name_ru: str,
    description_uz: str,
    description_ru: str,
    price: int,
    weight: str,
    photo_id: str = "",
    is_available: int = 1,
) -> int:
    """Adds a new sweet product and returns its ID."""
    cursor = await db.execute(
        """
        INSERT INTO products (
            category_id, name_uz, name_ru, description_uz, description_ru,
            price, weight, photo_id, is_available
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            category_id,
            name_uz,
            name_ru,
            description_uz,
            description_ru,
            price,
            weight,
            photo_id,
            is_available,
        ),
    )
    await db.commit()
    return cursor.lastrowid or 0


async def set_product_availability(db: aiosqlite.Connection, product_id: int, is_available: int) -> None:
    """Toggles or sets the availability of a product (1 = available, 0 = out of stock)."""
    await db.execute("UPDATE products SET is_available = ? WHERE id = ?;", (is_available, product_id))
    await db.commit()


async def search_products(db: aiosqlite.Connection, query: str) -> List[Dict[str, Any]]:
    """Searches available products by Uzbek/Russian name and description with full Unicode case-insensitivity."""
    q = query.strip().lower()
    if not q:
        return []

    async with db.execute(
        "SELECT * FROM products WHERE is_available = 1 ORDER BY id ASC;"
    ) as cursor:
        rows = await cursor.fetchall()
        results = []
        for r in rows:
            name_uz = (r["name_uz"] or "").lower()
            name_ru = (r["name_ru"] or "").lower()
            desc_uz = (r["description_uz"] or "").lower()
            desc_ru = (r["description_ru"] or "").lower()
            if q in name_uz or q in name_ru or q in desc_uz or q in desc_ru:
                results.append(dict(r))
        return results


async def get_all_available_products(db: aiosqlite.Connection) -> List[Dict[str, Any]]:
    """Returns all available products."""
    async with db.execute(
        "SELECT * FROM products WHERE is_available = 1 ORDER BY category_id ASC, id ASC;"
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_all_products(db: aiosqlite.Connection) -> List[Dict[str, Any]]:
    """Returns all products regardless of availability."""
    async with db.execute(
        "SELECT * FROM products ORDER BY category_id ASC, id ASC;"
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


# ==========================================
# CART
# ==========================================

async def add_to_cart(db: aiosqlite.Connection, user_id: int, product_id: int, quantity: int = 1) -> None:
    """Adds a product to user's cart or increments quantity if already present."""
    await db.execute(
        """
        INSERT INTO cart (user_id, product_id, quantity)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, product_id) DO UPDATE SET
            quantity = cart.quantity + excluded.quantity;
        """,
        (user_id, product_id, quantity),
    )
    await db.commit()


async def set_cart_item_quantity(db: aiosqlite.Connection, user_id: int, product_id: int, quantity: int) -> None:
    """Sets exact cart quantity. If quantity <= 0, deletes the item from cart."""
    if quantity <= 0:
        await db.execute(
            "DELETE FROM cart WHERE user_id = ? AND product_id = ?;",
            (user_id, product_id),
        )
    else:
        await db.execute(
            "UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?;",
            (quantity, user_id, product_id),
        )
    await db.commit()


async def get_cart(db: aiosqlite.Connection, user_id: int) -> List[Dict[str, Any]]:
    """Returns user's cart joined with product details (names, price, weight, photo, calculated total_price)."""
    async with db.execute(
        """
        SELECT
            c.id,
            c.user_id,
            c.product_id,
            c.quantity,
            p.name_uz,
            p.name_ru,
            p.price,
            p.weight,
            p.photo_id,
            (p.price * c.quantity) AS total_price
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
        ORDER BY c.id ASC;
        """,
        (user_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_cart_total(db: aiosqlite.Connection, user_id: int) -> int:
    """Calculates the total monetary sum of items in user's cart."""
    async with db.execute(
        """
        SELECT COALESCE(SUM(p.price * c.quantity), 0) AS total
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?;
        """,
        (user_id,),
    ) as cursor:
        row = await cursor.fetchone()
        return int(row["total"]) if row else 0


async def remove_from_cart(db: aiosqlite.Connection, user_id: int, product_id: int) -> None:
    """Removes a specific product from user's cart."""
    await db.execute(
        "DELETE FROM cart WHERE user_id = ? AND product_id = ?;",
        (user_id, product_id),
    )
    await db.commit()


async def clear_cart(db: aiosqlite.Connection, user_id: int) -> None:
    """Empties user's cart completely."""
    await db.execute("DELETE FROM cart WHERE user_id = ?;", (user_id,))
    await db.commit()


# ==========================================
# ORDERS
# ==========================================

async def create_order(
    db: aiosqlite.Connection,
    user_id: int,
    order_type: str,
    total_amount: int,
    delivery_cost: int,
    delivery_type: str,
    target_time: str,
    address: Optional[str],
    latitude: Optional[float],
    longitude: Optional[float],
    distance_km: float,
    phone: str,
    custom_note: Optional[str],
    payment_type: str,
    custom_image_id: Optional[str] = None,
    cart_items: Optional[List[Dict[str, Any]]] = None,
) -> int:
    """Creates a new order with optional line items and returns the new order_id."""
    cursor = await db.execute(
        """
        INSERT INTO orders (
            user_id, order_type, total_amount, delivery_cost, delivery_type,
            target_time, address, latitude, longitude, distance_km,
            phone, custom_note, custom_image_id, payment_type, payment_status, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 'new');
        """,
        (
            user_id,
            order_type,
            total_amount,
            delivery_cost,
            delivery_type,
            target_time,
            address,
            latitude,
            longitude,
            distance_km,
            phone,
            custom_note,
            custom_image_id,
            payment_type,
        ),
    )
    order_id = cursor.lastrowid or 0

    if cart_items:
        for item in cart_items:
            price = item.get("price_at_purchase", item.get("price", 0))
            await db.execute(
                """
                INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase)
                VALUES (?, ?, ?, ?);
                """,
                (order_id, item["product_id"], item["quantity"], price),
            )

    await db.commit()
    return order_id


async def get_order(db: aiosqlite.Connection, order_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves an order by its ID."""
    async with db.execute("SELECT * FROM orders WHERE id = ?;", (order_id,)) as cursor:
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_order_items(db: aiosqlite.Connection, order_id: int) -> List[Dict[str, Any]]:
    """Retrieves all line items for an order, joined with current product details."""
    async with db.execute(
        """
        SELECT
            oi.id,
            oi.order_id,
            oi.product_id,
            oi.quantity,
            oi.price_at_purchase,
            p.name_uz,
            p.name_ru,
            p.weight,
            p.photo_id
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
        ORDER BY oi.id ASC;
        """,
        (order_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def update_order_status(db: aiosqlite.Connection, order_id: int, status: str) -> None:
    """Updates order progression status (e.g. 'new', 'accepted', 'preparing', 'delivering', 'completed', 'cancelled')."""
    await db.execute("UPDATE orders SET status = ? WHERE id = ?;", (status, order_id))
    await db.commit()


async def update_payment_status(db: aiosqlite.Connection, order_id: int, payment_status: str) -> None:
    """Updates payment status (e.g. 'pending', 'paid', 'failed')."""
    await db.execute("UPDATE orders SET payment_status = ? WHERE id = ?;", (payment_status, order_id))
    await db.commit()


async def get_user_orders(db: aiosqlite.Connection, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves recent orders created by a specific user."""
    async with db.execute(
        """
        SELECT * FROM orders
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT ?;
        """,
        (user_id, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_all_orders(db: aiosqlite.Connection, limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves all recent orders (useful for admin/staff dashboard)."""
    async with db.execute(
        """
        SELECT * FROM orders
        ORDER BY created_at DESC, id DESC
        LIMIT ?;
        """,
        (limit,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_order_statistics(db: aiosqlite.Connection) -> Dict[str, Any]:
    """Calculates order and revenue statistics for admin dashboard."""
    async with db.execute(
        "SELECT COUNT(*) AS total_orders, COALESCE(SUM(total_amount), 0) AS total_revenue FROM orders;"
    ) as cur:
        row = await cur.fetchone()
        total_orders = row["total_orders"] if row else 0
        total_revenue = row["total_revenue"] if row else 0

    async with db.execute(
        "SELECT COUNT(*) AS today_orders, COALESCE(SUM(total_amount), 0) AS today_revenue FROM orders WHERE date(created_at) = date('now');"
    ) as cur:
        row2 = await cur.fetchone()
        today_orders = row2["today_orders"] if row2 else 0
        today_revenue = row2["today_revenue"] if row2 else 0

    async with db.execute("SELECT COUNT(*) AS total_users FROM users;") as cur:
        row3 = await cur.fetchone()
        total_users = row3["total_users"] if row3 else 0

    return {
        "total_orders": total_orders,
        "total_revenue": total_revenue,
        "today_orders": today_orders,
        "today_revenue": today_revenue,
        "total_users": total_users,
    }


# ==========================================
# SETTINGS
# ==========================================

async def get_setting(db: aiosqlite.Connection, key: str, default: Optional[str] = None) -> Optional[str]:
    """Fetches a configuration setting value by key."""
    async with db.execute("SELECT value FROM settings WHERE key = ?;", (key,)) as cursor:
        row = await cursor.fetchone()
        return row["value"] if row else default


async def set_setting(db: aiosqlite.Connection, key: str, value: str) -> None:
    """Sets or updates a configuration setting value."""
    await db.execute(
        """
        INSERT INTO settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = excluded.value;
        """,
        (key, value),
    )
    await db.commit()
