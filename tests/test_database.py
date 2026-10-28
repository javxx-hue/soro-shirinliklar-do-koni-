"""
Comprehensive async tests for sweet shop SQLite database models and CRUD operations.
"""
import pytest
import aiosqlite

from database.db import init_db, get_db_connection
from database import crud


@pytest.fixture
async def test_db():
    """Fixture providing an initialized in-memory database connection."""
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA foreign_keys = ON;")
    await init_db(db)
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_init_db_creates_tables_and_seeds(test_db):
    """Verify that tables are created and default categories/products are seeded."""
    categories = await crud.get_categories(test_db, only_active=False)
    assert len(categories) >= 4

    cat_names = [c["name_uz"] for c in categories]
    assert any("Tortlar" in name for name in cat_names)
    assert any("Kapkeyk" in name for name in cat_names)

    products = await crud.get_all_available_products(test_db)
    assert len(products) >= 5

    prod_names = [p["name_uz"] for p in products]
    assert any("Medovik" in name for name in prod_names)


@pytest.mark.asyncio
async def test_init_db_idempotent(test_db):
    """Calling init_db multiple times should not duplicate seeded data."""
    initial_categories = await crud.get_categories(test_db)
    initial_products = await crud.get_all_available_products(test_db)

    # Re-run init_db
    await init_db(test_db)

    after_categories = await crud.get_categories(test_db)
    after_products = await crud.get_all_available_products(test_db)

    assert len(initial_categories) == len(after_categories)
    assert len(initial_products) == len(after_products)


@pytest.mark.asyncio
async def test_user_crud(test_db):
    """Test user upsert, retrieval, language and phone updates."""
    # 1. Upsert new user
    user = await crud.upsert_user(
        test_db,
        telegram_id=12345678,
        full_name="Dilshod Karimov",
        username="dilshodk",
        phone="+998901234567",
        language="uz",
    )
    assert user["telegram_id"] == 12345678
    assert user["full_name"] == "Dilshod Karimov"
    assert user["language"] == "uz"

    # 2. Get user
    fetched = await crud.get_user(test_db, telegram_id=12345678)
    assert fetched is not None
    assert fetched["username"] == "dilshodk"

    # 3. Update existing user (upsert)
    updated = await crud.upsert_user(
        test_db,
        telegram_id=12345678,
        full_name="Dilshodbek Karimov",
        username="dilshod_new",
    )
    assert updated["full_name"] == "Dilshodbek Karimov"
    assert updated["username"] == "dilshod_new"
    # phone should be preserved if not provided
    assert updated["phone"] == "+998901234567"

    # 4. Set language
    await crud.set_user_language(test_db, telegram_id=12345678, language="ru")
    user_ru = await crud.get_user(test_db, telegram_id=12345678)
    assert user_ru["language"] == "ru"

    # 5. Set phone
    await crud.set_user_phone(test_db, telegram_id=12345678, phone="+998998887766")
    user_phone = await crud.get_user(test_db, telegram_id=12345678)
    assert user_phone["phone"] == "+998998887766"

    # 6. Non-existent user
    non_existent = await crud.get_user(test_db, telegram_id=99999999)
    assert non_existent is None


@pytest.mark.asyncio
async def test_category_and_product_crud(test_db):
    """Test category creation, product addition, availability toggle, and search."""
    # Add new category
    cat_id = await crud.add_category(test_db, name_uz="Maxsus Takliflar", name_ru="Спецпредложения", sort_order=10)
    assert cat_id > 0

    cats = await crud.get_categories(test_db)
    assert any(c["id"] == cat_id for c in cats)

    # Add product to new category
    prod_id = await crud.add_product(
        test_db,
        category_id=cat_id,
        name_uz="Limonli Tart",
        name_ru="Лимонный тарт",
        description_uz="Nordik vanil va limonli krem bilan tayyorlangan",
        description_ru="С кремом из лимона и нотками ванили",
        price=75000,
        weight="300 g",
        photo_id="photo_tart_123",
        is_available=1,
    )
    assert prod_id > 0

    # Get product
    prod = await crud.get_product(test_db, prod_id)
    assert prod is not None
    assert prod["name_uz"] == "Limonli Tart"
    assert prod["price"] == 75000
    assert prod["is_available"] == 1

    # Get products by category
    cat_prods = await crud.get_products_by_category(test_db, cat_id)
    assert len(cat_prods) == 1
    assert cat_prods[0]["id"] == prod_id

    # Toggle availability
    await crud.set_product_availability(test_db, prod_id, is_available=0)
    avail_prods = await crud.get_products_by_category(test_db, cat_id, only_available=True)
    assert len(avail_prods) == 0

    all_cat_prods = await crud.get_products_by_category(test_db, cat_id, only_available=False)
    assert len(all_cat_prods) == 1

    # Turn back on
    await crud.set_product_availability(test_db, prod_id, is_available=1)

    # Search products
    search_res = await crud.search_products(test_db, "Limon")
    assert len(search_res) >= 1
    assert any(p["id"] == prod_id for p in search_res)

    search_ru = await crud.search_products(test_db, "лимонный")
    assert len(search_ru) >= 1
    assert any(p["id"] == prod_id for p in search_ru)


@pytest.mark.asyncio
async def test_cart_operations(test_db):
    """Test cart CRUD: add, increment, update quantity, remove, get total, and clear."""
    user_id = 1001
    products = await crud.get_all_available_products(test_db)
    p1 = products[0]
    p2 = products[1]

    # 1. Add item 1
    await crud.add_to_cart(test_db, user_id=user_id, product_id=p1["id"], quantity=2)
    cart = await crud.get_cart(test_db, user_id=user_id)
    assert len(cart) == 1
    assert cart[0]["product_id"] == p1["id"]
    assert cart[0]["quantity"] == 2
    assert cart[0]["price"] == p1["price"]
    assert cart[0]["total_price"] == p1["price"] * 2

    # 2. Add same item again -> increments quantity
    await crud.add_to_cart(test_db, user_id=user_id, product_id=p1["id"], quantity=1)
    cart = await crud.get_cart(test_db, user_id=user_id)
    assert len(cart) == 1
    assert cart[0]["quantity"] == 3

    # 3. Add item 2
    await crud.add_to_cart(test_db, user_id=user_id, product_id=p2["id"], quantity=1)
    cart = await crud.get_cart(test_db, user_id=user_id)
    assert len(cart) == 2

    # 4. Total calculation
    total = await crud.get_cart_total(test_db, user_id=user_id)
    expected_total = (p1["price"] * 3) + (p2["price"] * 1)
    assert total == expected_total

    # 5. Set quantity
    await crud.set_cart_item_quantity(test_db, user_id=user_id, product_id=p1["id"], quantity=5)
    cart = await crud.get_cart(test_db, user_id=user_id)
    p1_in_cart = next(item for item in cart if item["product_id"] == p1["id"])
    assert p1_in_cart["quantity"] == 5

    # 6. Set quantity to 0 removes the item
    await crud.set_cart_item_quantity(test_db, user_id=user_id, product_id=p1["id"], quantity=0)
    cart = await crud.get_cart(test_db, user_id=user_id)
    assert len(cart) == 1
    assert cart[0]["product_id"] == p2["id"]

    # 7. Remove item
    await crud.remove_from_cart(test_db, user_id=user_id, product_id=p2["id"])
    cart = await crud.get_cart(test_db, user_id=user_id)
    assert len(cart) == 0
    assert await crud.get_cart_total(test_db, user_id=user_id) == 0

    # 8. Clear cart
    await crud.add_to_cart(test_db, user_id=user_id, product_id=p1["id"], quantity=2)
    await crud.add_to_cart(test_db, user_id=user_id, product_id=p2["id"], quantity=2)
    assert len(await crud.get_cart(test_db, user_id=user_id)) == 2

    await crud.clear_cart(test_db, user_id=user_id)
    assert len(await crud.get_cart(test_db, user_id=user_id)) == 0


@pytest.mark.asyncio
async def test_order_creation_and_management(test_db):
    """Test order creation, order items, status changes, and listing."""
    user_id = 2002
    products = await crud.get_all_available_products(test_db)
    p1 = products[0]
    p2 = products[1]

    cart_items = [
        {"product_id": p1["id"], "quantity": 2, "price_at_purchase": p1["price"]},
        {"product_id": p2["id"], "quantity": 1, "price_at_purchase": p2["price"]},
    ]
    total_amount = (p1["price"] * 2) + (p2["price"] * 1) + 15000

    order_id = await crud.create_order(
        test_db,
        user_id=user_id,
        order_type="standard",
        total_amount=total_amount,
        delivery_cost=15000,
        delivery_type="delivery",
        target_time="14:00 - 15:00 bugun",
        address="Toshkent sh., Yunusobod tumani, 4-mavze, 12-uy",
        latitude=41.3541,
        longitude=69.2891,
        distance_km=3.5,
        phone="+998901112233",
        custom_note="Iltimos, ehtiyotkorlik bilan yetkazing.",
        payment_type="click",
        custom_image_id=None,
        cart_items=cart_items,
    )
    assert order_id > 0

    # Get order
    order = await crud.get_order(test_db, order_id)
    assert order is not None
    assert order["user_id"] == user_id
    assert order["status"] == "new"
    assert order["payment_status"] == "pending"
    assert order["total_amount"] == total_amount
    assert order["delivery_cost"] == 15000
    assert order["delivery_type"] == "delivery"
    assert order["latitude"] == 41.3541
    assert order["longitude"] == 69.2891

    # Get order items
    items = await crud.get_order_items(test_db, order_id)
    assert len(items) == 2
    item1 = next(it for it in items if it["product_id"] == p1["id"])
    assert item1["quantity"] == 2
    assert item1["price_at_purchase"] == p1["price"]
    assert item1["name_uz"] == p1["name_uz"]

    # Update order status
    await crud.update_order_status(test_db, order_id, "accepted")
    updated_order = await crud.get_order(test_db, order_id)
    assert updated_order["status"] == "accepted"

    # Update payment status
    await crud.update_payment_status(test_db, order_id, "paid")
    paid_order = await crud.get_order(test_db, order_id)
    assert paid_order["payment_status"] == "paid"

    # List user orders
    user_orders = await crud.get_user_orders(test_db, user_id=user_id)
    assert len(user_orders) == 1
    assert user_orders[0]["id"] == order_id

    # List all orders
    all_orders = await crud.get_all_orders(test_db)
    assert len(all_orders) >= 1
    assert any(o["id"] == order_id for o in all_orders)


@pytest.mark.asyncio
async def test_settings_crud(test_db):
    """Test getting and setting configuration parameters."""
    assert await crud.get_setting(test_db, "shop_status") is None
    assert await crud.get_setting(test_db, "shop_status", default="open") == "open"

    await crud.set_setting(test_db, "shop_status", "closed")
    assert await crud.get_setting(test_db, "shop_status") == "closed"

    await crud.set_setting(test_db, "shop_status", "open")
    assert await crud.get_setting(test_db, "shop_status") == "open"


@pytest.mark.asyncio
async def test_file_db_initialization(tmp_path):
    """Test init_db with actual file path."""
    db_file = tmp_path / "shop_test.db"
    await init_db(db_file)

    conn = await get_db_connection(str(db_file))
    try:
        categories = await crud.get_categories(conn)
        assert len(categories) >= 4
    finally:
        await conn.close()
