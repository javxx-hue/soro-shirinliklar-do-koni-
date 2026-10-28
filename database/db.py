"""
Database connection management and initialization.
"""
from pathlib import Path
from typing import Union
import aiosqlite

from .models import ALL_TABLES, CREATE_INDEXES


DEFAULT_CATEGORIES = [
    {"name_uz": "🎂 Tortlar", "name_ru": "🎂 Торты", "sort_order": 1},
    {"name_uz": "🧁 Kapkeyklar va Pirojniylar", "name_ru": "🧁 Капкейки и Пирожные", "sort_order": 2},
    {"name_uz": "🥐 Shirin pishiriqlar", "name_ru": "🥐 Сладкая выпечка", "sort_order": 3},
    {"name_uz": "🍫 Shokolad va konfetlar", "name_ru": "🍫 Шоколад и конфеты", "sort_order": 4},
]

DEFAULT_PRODUCTS = [
    # Tortlar (Category 1)
    {
        "category_sort_order": 1,
        "name_uz": "Asalli Medovik (Klassik)",
        "name_ru": "Медовик классический",
        "description_uz": "Yumshoq asal qatlamlari va nozik smetana kremli an'anaviy tort.",
        "description_ru": "Нежные медовые коржи со сливочно-сметанным кремом.",
        "price": 150000,
        "weight": "1.2 kg",
        "photo_id": "",
        "is_available": 1,
    },
    {
        "category_sort_order": 1,
        "name_uz": "Qizil Baxmal (Red Velvet)",
        "name_ru": "Красный Бархат",
        "description_uz": "Yorqin qizil biskvit, nozik pishloqli krem (cream cheese) va rezavorlar ifori.",
        "description_ru": "Воздушный бисквит с нежным сливочно-сырным кремом.",
        "price": 180000,
        "weight": "1.5 kg",
        "photo_id": "",
        "is_available": 1,
    },
    {
        "category_sort_order": 1,
        "name_uz": "San-Sebastian Chizkeyk",
        "name_ru": "Чизкейк Сан-Себастьян",
        "description_uz": "Kuygan karamel ta'mli, ichi erib turuvchi nozik ispan chizkeyki.",
        "description_ru": "Испанский обожженный чизкейк с нежной тающей текстурой.",
        "price": 160000,
        "weight": "1.0 kg",
        "photo_id": "",
        "is_available": 1,
    },
    # Kapkeyklar (Category 2)
    {
        "category_sort_order": 2,
        "name_uz": "Shokoladli Kapkeyklar (6 dona)",
        "name_ru": "Шоколадные капкейки (6 шт)",
        "description_uz": "Belgiya shokoladi va nozik krem bilan bezatilgan mini shirinliklar to'plami.",
        "description_ru": "Набор шоколадных капкейков с нежным кремом из бельгийского шоколада.",
        "price": 90000,
        "weight": "450 g",
        "photo_id": "",
        "is_available": 1,
    },
    {
        "category_sort_order": 2,
        "name_uz": "Vanilli Eklerlar (4 dona)",
        "name_ru": "Ванильные эклеры (4 шт)",
        "description_uz": "Fransuzcha uslubdagi mayin xamir va qaymoqli vanil kremi.",
        "description_ru": "Французские эклеры с заварным ванильным кремом.",
        "price": 70000,
        "weight": "320 g",
        "photo_id": "",
        "is_available": 1,
    },
    # Shirin pishiriqlar (Category 3)
    {
        "category_sort_order": 3,
        "name_uz": "Shokoladli Kruassan",
        "name_ru": "Круассан с шоколадом",
        "description_uz": "Qarsildoq qatlama xamir va ichida quyuq shokolad.",
        "description_ru": "Хрустящий слоеный круассан с начинкой из темного шоколада.",
        "price": 25000,
        "weight": "120 g",
        "photo_id": "",
        "is_available": 1,
    },
    # Shokolad va konfetlar (Category 4)
    {
        "category_sort_order": 4,
        "name_uz": "Qo'lda tayyorlangan Trufellar to'plami (9 dona)",
        "name_ru": "Набор трюфелей ручной работы (9 шт)",
        "description_uz": "Haqiqiy kakao va yong'oqli premium trufel konfetlari.",
        "description_ru": "Премиальные конфеты-трюфели с орехами и натуральным какао.",
        "price": 110000,
        "weight": "250 g",
        "photo_id": "",
        "is_available": 1,
    },
]


async def get_db_connection(db_path: str = "data/shop.db") -> aiosqlite.Connection:
    """Creates and returns an active aiosqlite connection with Row row_factory."""
    if db_path != ":memory:":
        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)

    conn = await aiosqlite.connect(db_path)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys = ON;")
    return conn


async def init_db(db_or_path: Union[aiosqlite.Connection, str, Path] = "data/shop.db") -> None:
    """Initializes tables, indexes, and seeds starter sweet shop items if empty."""
    is_external_conn = isinstance(db_or_path, aiosqlite.Connection)
    conn: aiosqlite.Connection = db_or_path if is_external_conn else await get_db_connection(str(db_or_path))

    try:
        # Create all tables
        for table_sql in ALL_TABLES:
            await conn.execute(table_sql)

        # Create all indexes
        for index_sql in CREATE_INDEXES:
            await conn.execute(index_sql)

        # Seed initial categories & products if categories table is empty
        async with conn.execute("SELECT COUNT(*) AS cnt FROM categories;") as cursor:
            row = await cursor.fetchone()
            count = row["cnt"] if row else 0

        if count == 0:
            cat_id_map = {}
            for cat in DEFAULT_CATEGORIES:
                cursor = await conn.execute(
                    """
                    INSERT INTO categories (name_uz, name_ru, sort_order)
                    VALUES (?, ?, ?);
                    """,
                    (cat["name_uz"], cat["name_ru"], cat["sort_order"]),
                )
                cat_id_map[cat["sort_order"]] = cursor.lastrowid

            for prod in DEFAULT_PRODUCTS:
                cat_id = cat_id_map.get(prod["category_sort_order"])
                await conn.execute(
                    """
                    INSERT INTO products (
                        category_id, name_uz, name_ru, description_uz, description_ru,
                        price, weight, photo_id, is_available
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (
                        cat_id,
                        prod["name_uz"],
                        prod["name_ru"],
                        prod["description_uz"],
                        prod["description_ru"],
                        prod["price"],
                        prod["weight"],
                        prod["photo_id"],
                        prod["is_available"],
                    ),
                )

        await conn.commit()
    finally:
        if not is_external_conn:
            await conn.close()
