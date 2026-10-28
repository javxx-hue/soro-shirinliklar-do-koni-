# Shirinlik Do'koni Telegram Boti (Sweet Shop Bot) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shirinlik do'koni uchun mijozni jalb etuvchi, 30 soniyada buyurtma oluvchi, masofa bo'yicha yetkazish narxini hisoblovchi, Click/Payme/Naqd to'lovli, oldindan buyurtma va tortga yozuv kiritish imkoniyatiga ega, hamda Gemini AI maslahatchisi bilan jihozlangan to'liq Telegram bot tizimini yaratish.

**Architecture:** `aiogram 3.13+` routerlari va FSM holatlari asosida modulli tizim. Asinxron SQLite (`aiosqlite`) ma'lumotlar bazasi, masofaga asoslangan yetkazib berish kalkulyatori, ko'p tilli i18n middleware, xavfsiz Telegram Payments API va Gemini 2.5 Flash AI maslahatchisi.

**Tech Stack:** Python 3.13, `aiogram>=3.13`, `aiosqlite>=0.20`, `python-dotenv>=1.0`, `google-genai>=1.0.0`, `pytest`, `pytest-asyncio`.

**Spec:** `docs/superpowers/specs/2026-10-28-shirinlik-dokoni-telegram-bot-design.md`

## Global Constraints
- Til yozuvi: O'zbek tili (Lotin) va Rus tili.
- Telegram Framework: aiogram 3.x (Routerlar va FSM ishlatiladi).
- Asinxronlik: Barcha DB va tashqi so'rovlar qat'iy `async/await` bo'lishi shart.
- Sinovlar: Har bir modul unit testlar orqali tekshirilishi shart (`pytest`, `pytest-asyncio`).
- Mijoz xursandchiligi (Customer Delight): Barcha matnlar iliq, ishtahani ochuvchi va xushmuomala bo'lishi kerak.

---

### Task 1: Loyiha Muhiti va Konfiguratsiyasi (Config & Requirements)

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Create: `shop_config.py`
- Test: `tests/test_shop_config.py`

**Interfaces:**
- Consumes: `.env` environment variables (`BOT_TOKEN`, `ADMIN_IDS`, `GEMINI_API_KEY`, `CLICK_TOKEN`, `PAYME_TOKEN`, `STORE_LAT`, `STORE_LON`)
- Produces: `shop_config.Config` dataclass / pydantic object containing all validated app settings.

- [ ] **Step 1: Write the failing test for configuration**

```python
# tests/test_shop_config.py
import pytest
import os
from shop_config import load_config

def test_load_config_defaults(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    monkeypatch.setenv("ADMIN_IDS", "12345678,87654321")
    monkeypatch.setenv("STORE_LAT", "41.311081")
    monkeypatch.setenv("STORE_LON", "69.240562")
    
    cfg = load_config()
    assert cfg.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert cfg.admin_ids == [12345678, 87654321]
    assert cfg.store_lat == 41.311081
    assert cfg.store_lon == 69.240562
    assert cfg.free_delivery_threshold == 250000
    assert cfg.base_delivery_price == 12000
    assert cfg.price_per_km == 2500
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_shop_config.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'shop_config'`

- [ ] **Step 3: Update requirements and implement shop_config.py**

```python
# shop_config.py
import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    bot_token: str
    admin_ids: List[int] = field(default_factory=list)
    gemini_api_key: str = ""
    click_token: str = ""
    payme_token: str = ""
    store_lat: float = 41.311081  # Default Toshkent markazi
    store_lon: float = 69.240562
    base_delivery_price: int = 12000
    price_per_km: int = 2500
    free_delivery_threshold: int = 250000
    work_start: str = "09:00"
    work_end: str = "22:00"

def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN", "")
    admin_ids_raw = os.getenv("ADMIN_IDS", "")
    admin_ids = [int(i.strip()) for i in admin_ids_raw.split(",") if i.strip().isdigit()]
    
    return Config(
        bot_token=bot_token,
        admin_ids=admin_ids,
        gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
        click_token=os.getenv("CLICK_TOKEN", ""),
        payme_token=os.getenv("PAYME_TOKEN", ""),
        store_lat=float(os.getenv("STORE_LAT", "41.311081")),
        store_lon=float(os.getenv("STORE_LON", "69.240562")),
        base_delivery_price=int(os.getenv("BASE_DELIVERY_PRICE", "12000")),
        price_per_km=int(os.getenv("PRICE_PER_KM", "2500")),
        free_delivery_threshold=int(os.getenv("FREE_DELIVERY_THRESHOLD", "250000")),
        work_start=os.getenv("WORK_START", "09:00"),
        work_end=os.getenv("WORK_END", "22:00"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_shop_config.py -v`  
Expected: PASS

---

### Task 2: Ma'lumotlar Bazasi va CRUD Funksiyalari (Database & CRUD)

**Files:**
- Create: `database/db.py`
- Create: `database/models.py`
- Create: `database/crud.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Consumes: `aiosqlite`, SQLite filepath
- Produces: `init_db(db_path)`, `upsert_user(...)`, `get_categories()`, `get_products_by_category(...)`, `add_to_cart(...)`, `get_cart(...)`, `clear_cart(...)`, `create_order(...)`, `update_order_status(...)`.

- [ ] **Step 1: Write the failing tests for Database and CRUD**

```python
# tests/test_database.py
import pytest
import pytest_asyncio
import aiosqlite
from database.db import init_db
from database.crud import (
    upsert_user, get_user,
    add_category, get_categories,
    add_product, get_products_by_category,
    add_to_cart, get_cart, clear_cart,
    create_order, get_order
)

@pytest_asyncio.fixture
async def test_db():
    db_path = ":memory:"
    async with aiosqlite.connect(db_path) as db:
        await init_db(db)
        yield db

@pytest.mark.asyncio
async def test_user_and_cart_flow(test_db):
    user = await upsert_user(test_db, telegram_id=123, full_name="Ali", username="ali", language="uz")
    assert user["telegram_id"] == 123
    assert user["language"] == "uz"

    cat_id = await add_category(test_db, name_uz="Tortlar", name_ru="Торты")
    prod_id = await add_product(
        test_db, category_id=cat_id, name_uz="Medovik", name_ru="Медовик",
        description_uz="Asalli mayin tort", description_ru="Нежный медовый торт",
        price=120000, weight="1.2 kg", photo_id="test_photo"
    )

    await add_to_cart(test_db, user_id=123, product_id=prod_id, quantity=2)
    cart_items = await get_cart(test_db, user_id=123)
    assert len(cart_items) == 1
    assert cart_items[0]["quantity"] == 2
    assert cart_items[0]["total_price"] == 240000

    order_id = await create_order(
        test_db, user_id=123, order_type="standard", total_amount=240000,
        delivery_cost=15000, delivery_type="delivery", target_time="hozir",
        address="Amir Temur ko'chasi 1", latitude=41.31, longitude=69.24,
        distance_km=3.2, phone="+998901234567", custom_note="Tabrik bilan",
        payment_type="cash"
    )
    order = await get_order(test_db, order_id=order_id)
    assert order["total_amount"] == 240000
    assert order["status"] == "new"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_database.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement database/db.py, models.py, and crud.py**

Create schema with tables: `users`, `categories`, `products`, `cart`, `orders`, `order_items`, `settings`.  
Add starter seed categories (Tortlar, Kapkeyklar, Milliy shirinliklar, Shokoladlar) and popular products if empty.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_database.py -v`  
Expected: PASS

---

### Task 3: Lokalizatsiya (O'zbek va Rus tillari i18n)

**Files:**
- Create: `locales/uz.json`
- Create: `locales/ru.json`
- Create: `middlewares/i18n.py`
- Test: `tests/test_i18n.py`

**Interfaces:**
- Consumes: `user.language` from DB or Telegram user object
- Produces: `_t(key, lang, **kwargs)` helper and `I18nMiddleware` for aiogram.

- [ ] **Step 1: Write test for localization parity and translation keys**

```python
# tests/test_i18n.py
import json
import pytest
from middlewares.i18n import get_text

def test_locales_keys_match():
    with open("locales/uz.json", "r", encoding="utf-8") as f:
        uz = json.load(f)
    with open("locales/ru.json", "r", encoding="utf-8") as f:
        ru = json.load(f)
    
    assert set(uz.keys()) == set(ru.keys()), f"Mismatched keys: {set(uz.keys()) ^ set(ru.keys())}"

def test_translation_formatting():
    msg = get_text("order_confirmed_msg", lang="uz", order_id=45)
    assert "45" in msg
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_i18n.py -v`  
Expected: FAIL

- [ ] **Step 3: Create locales/uz.json, locales/ru.json and middlewares/i18n.py**

Include friendly, warm phrases:
- Greetings and menu texts
- Delivery & pre-order choice texts
- Custom cake note prompts
- Order tracking notifications: "👩‍🍳 Qandolatchilar tayyorlashni boshladi", "🎁 Chiroyli qadoqlandi", "🚗 Kuryer yo'lga chiqdi".

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_i18n.py -v`  
Expected: PASS

---

### Task 4: Masofa va Yetkazib Berish Narxini Hisoblash Dvigateli (Delivery Engine)

**Files:**
- Create: `services/delivery.py`
- Test: `tests/test_delivery.py`

**Interfaces:**
- Consumes: `user_lat`, `user_lon`, `store_lat`, `store_lon`, `cart_total`, `config`
- Produces: `calculate_delivery(user_lat, user_lon, cart_total, config) -> (distance_km, delivery_price, is_free)`

- [ ] **Step 1: Write tests for distance and delivery calculations**

```python
# tests/test_delivery.py
import pytest
from services.delivery import calculate_distance_km, calculate_delivery_cost
from shop_config import Config

def test_calculate_distance():
    # Toshkent markazidan Chilonzorgacha ~6.5 km
    dist = calculate_distance_km(41.311081, 69.240562, 41.2858, 69.2036)
    assert 4.0 <= dist <= 8.0

def test_delivery_cost_normal():
    cfg = Config(bot_token="", base_delivery_price=12000, price_per_km=2500, free_delivery_threshold=250000)
    # 5 km masofa: 12000 (dastlabki 3 km) + 2 * 2500 = 17000 so'm
    cost, is_free = calculate_delivery_cost(distance_km=5.0, cart_total=150000, config=cfg)
    assert cost == 17000
    assert is_free is False

def test_delivery_cost_free_threshold():
    cfg = Config(bot_token="", base_delivery_price=12000, price_per_km=2500, free_delivery_threshold=250000)
    cost, is_free = calculate_delivery_cost(distance_km=8.0, cart_total=300000, config=cfg)
    assert cost == 0
    assert is_free is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\pytest tests/test_delivery.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement services/delivery.py with Haversine formula**

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\pytest tests/test_delivery.py -v`  
Expected: PASS

---

### Task 5: Klaviaturani Yaratish (Reply & Inline Keyboards)

**Files:**
- Create: `keyboards/reply.py`
- Create: `keyboards/inline.py`
- Create: `keyboards/admin_kb.py`
- Test: `tests/test_keyboards.py`

**Interfaces:**
- Produces: `main_menu_kb(lang, is_admin)`, `phone_request_kb(lang)`, `location_request_kb(lang)`, `categories_kb(categories, lang)`, `product_card_kb(product_id, quantity, lang)`, `cart_kb(cart_items, lang)`, `delivery_time_kb(lang)`, `payment_methods_kb(lang)`, `order_admin_actions_kb(order_id)`.

- [ ] **Step 1: Write test for keyboard layouts**

```python
# tests/test_keyboards.py
from keyboards.reply import main_menu_kb, phone_request_kb
from keyboards.inline import product_card_kb

def test_main_menu_buttons_count():
    kb = main_menu_kb(lang="uz", is_admin=False)
    # Tekshiramiz: Katalog, Savatcha, Maslahatchi, O'z tortingiz, Buyurtmalarim, Aloqa
    button_texts = [btn.text for row in kb.keyboard for btn in row]
    assert any("Katalog" in t for t in button_texts)
    assert any("Savatcha" in t for t in button_texts)
    assert any("Maslahatchi" in t for t in button_texts)
```

- [ ] **Step 2: Run test and verify it fails**

Run: `.venv\Scripts\pytest tests/test_keyboards.py -v`  
Expected: FAIL

- [ ] **Step 3: Implement keyboards**

- [ ] **Step 4: Run test and verify it passes**

Run: `.venv\Scripts\pytest tests/test_keyboards.py -v`  
Expected: PASS

---

### Task 6: Katalog va Mahsulotlar Vitrinasi Handlerlari (Catalog)

**Files:**
- Create: `handlers/catalog.py`
- Test: `tests/test_catalog_handlers.py`

**Interfaces:**
- Router handling: `katalog` button, category selection callback, product card callback with photo, description, weight, price, and +/- cart actions.

- [ ] **Step 1: Write test for catalog navigation callbacks**
- [ ] **Step 2: Run test and verify it fails**
- [ ] **Step 3: Implement handlers/catalog.py**
- [ ] **Step 4: Run test and verify it passes**

---

### Task 7: Savatcha Boshqaruvi Handlerlari (Cart System)

**Files:**
- Create: `handlers/cart.py`
- Test: `tests/test_cart_handlers.py`

**Interfaces:**
- Router handling: `🛒 Savatcha`, changing item quantity (+/-), deleting an item, clearing cart, and proceeding to `✅ Buyurtma berish`.

- [ ] **Step 1: Write test for cart item updates and calculations**
- [ ] **Step 2: Run test and verify it fails**
- [ ] **Step 3: Implement handlers/cart.py**
- [ ] **Step 4: Run test and verify it passes**

---

### Task 8: Buyurtma Rasmiylashtirish FSM Oqimi (Order Placement Flow)

**Files:**
- Create: `handlers/order.py`
- Test: `tests/test_order_fsm.py`

**FSM States:**
- `OrderFSM.waiting_for_time` (Hozir yoki sana/soat)
- `OrderFSM.waiting_for_delivery_type` (Yetkazish yoki Olib ketish)
- `OrderFSM.waiting_for_location` (GPS koordinata yoki manzil matni)
- `OrderFSM.waiting_for_phone` (Kontakt yoki raqam kiritish)
- `OrderFSM.waiting_for_note` (Tortga yozuv / tabriknoma yoki o'tkazib yuborish)
- `OrderFSM.waiting_for_payment` (Click, Payme, Yetkazilganda naqd/karta)
- `OrderFSM.confirmation` (Tasdiqlash)

- [ ] **Step 1: Write test for FSM state transitions**
- [ ] **Step 2: Run test and verify it fails**
- [ ] **Step 3: Implement handlers/order.py**
- [ ] **Step 4: Run test and verify it passes**

---

### Task 9: 🎨 "O'z Tortingizga Buyurtma" (Custom Cake Flow)

**Files:**
- Create: `handlers/custom_cake.py`
- Test: `tests/test_custom_cake.py`

**Interfaces:**
- Allows users to upload a photo of a cake they want, specify weight (kg), description/filling preferences, phone, and target event date. Forwards directly to admins as a special custom order request.

- [ ] **Step 1: Write test for custom cake intake flow**
- [ ] **Step 2: Run test and verify it fails**
- [ ] **Step 3: Implement handlers/custom_cake.py**
- [ ] **Step 4: Run test and verify it passes**

---

### Task 10: To'lovlar Tizimi (Click va Payme Telegram Payments)

**Files:**
- Create: `handlers/payments.py`
- Test: `tests/test_payments.py`

**Interfaces:**
- PreCheckoutQuery handler (validates order status, total price in tiyin/sum)
- SuccessfulPayment handler (marks order `paid`, notifies admins, sends official digital receipt to user).

- [ ] **Step 1: Write test for PreCheckout and Payment receipt handling**
- [ ] **Step 2: Run test and verify it fails**
- [ ] **Step 3: Implement handlers/payments.py**
- [ ] **Step 4: Run test and verify it passes**

---

### Task 11: Admin Boshqaruvi va Jonli Status Xabarnomalari (Order Lifecycle)

**Files:**
- Create: `handlers/admin/panel.py`
- Create: `handlers/admin/orders.py`
- Create: `handlers/admin/products.py`
- Create: `services/notifier.py`
- Test: `tests/test_admin_orders.py`

**Interfaces:**
- Adminga ovozli/chiroyli xabar yuborish (barcha tafsilotlar, Google Maps havolasi, mijoz raqami).
- Inline action buttons: `[ ✅ Qabul qilish ]`, `[ 🎁 Tayyorlandi ]`, `[ 🚗 Kuryerga berildi ]`, `[ 🎉 Yetkazildi ]`, `[ ❌ Bekor qilish ]`.
- Har bir bosishda mijozga real vaqtda samimiy xabarnoma boradi.

- [ ] **Step 1: Write test for status transition notifications**
- [ ] **Step 2: Run test and verify it fails**
- [ ] **Step 3: Implement admin handlers and notifier service**
- [ ] **Step 4: Run test and verify it passes**

---

### Task 12: Gemini AI "Shirinlik Somelyesi" (AI Consultant)

**Files:**
- Create: `services/gemini.py`
- Create: `handlers/ai_consultant.py`
- Test: `tests/test_ai_consultant.py`

**Interfaces:**
- System prompt grounding: faqat ma'lumotlar bazasidagi mahsulotlar va ularning haqiqiy tarkibi, porsiyasi va narxlariga tayanib maslahat beradi.
- Xushmuomala, iliq va ishtahani ochuvchi tilda muloqot qiladi, mijozga to'g'ri tanlov qilishda ko'maklashadi.

- [ ] **Step 1: Write mock test for Gemini consultation logic**
- [ ] **Step 2: Run test and verify it fails**
- [ ] **Step 3: Implement services/gemini.py and handlers/ai_consultant.py**
- [ ] **Step 4: Run test and verify it passes**

---

### Task 13: Bosh Bot Fayli va Routerlarni Birlashtirish (Main Entrypoint)

**Files:**
- Modify: `bot.py`
- Modify: `handlers/common.py`
- Test: `tests/test_app_startup.py`

**Interfaces:**
- Dispatcher initialization, registering all routers (`common`, `catalog`, `cart`, `order`, `custom_cake`, `payments`, `ai_consultant`, `admin`), setting up bot commands, database startup and shutdown lifecycle.

- [ ] **Step 1: Write startup integration test**
- [ ] **Step 2: Run test and verify it fails**
- [ ] **Step 3: Implement bot.py and common handlers**
- [ ] **Step 4: Run test and verify it passes**

---

### Task 14: To'liq Tizim Sinovi (End-to-End Verification)

**Files:**
- Test: `tests/test_e2e_flow.py`

- [ ] **Step 1: Write end-to-end integration test covering:**
  1. User start & language selection (UZ)
  2. Browsing category & adding cake to cart
  3. Delivery calculation with GPS coordinates
  4. Adding personalized note on the cake
  5. Checkout with Cash / Click
  6. Admin receiving notification and advancing status to "Yetkazildi".
- [ ] **Step 2: Run all tests in repository**

Run: `.venv\Scripts\pytest -v`  
Expected: All tests pass (100% green).
