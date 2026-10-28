# Texnik Loyiha Hujjati: Shirinlik Do'koni Telegram Boti (Sweet Shop Bot)

**Sana:** 2026-10-28  
**Loyiha:** Shirinlik do'koni uchun to'liq funksional, xaridorni jalb etuvchi Telegram savdo boti va AI maslahatchisi.  
**Holat:** Tasdiqlangan / Amalga oshirishga tayyor.

---

## 1. Loyihaning Maqsadi va Asosiy Qiymati

Shirinlik do'koni uchun mijozlarni 1-soniyadanoq o'ziga jalb qiluvchi, buyurtma berish jarayoni o'ta oson va yoqimli bo'lgan, xaridorlarning birorta ham e'tiroziga o'rin qoldirmaydigan zamonaviy Telegram bot yaratish.

### Asosiy tamoyillar (Customer Delight & Business Logic):
1. **Ishtahani ochuvchi taqdimot:** Mahsulot fotosurati, aniq vazni/porsiyasi va hissiy, ishtahani qitiqlovchi tavsiflar.
2. **Tezkor va aniq yetkazib berish narxi (Delivery Pricing Engine):** Lokatsiya asosida masofani (km) va yetkazib berish narxini shaffof hisoblash. 250,000 so'mdan oshgan xaridlarga **bepul yetkazib berish** bonusi (o'rtacha xarid chekini oshiradi).
3. **Oldindan buyurtma va Vaqt tanlovi (Pre-orders):** "⚡️ Hozir / Bugun (60-90 daqiqada)" yoki "📅 Aniq sana va vaqtga (Masalan: Ertaga 18:00 ga)" tanlash imkoniyati.
4. **🎨 "O'z tortingizga buyurtma" (Custom Order / Rasm yuborish):** Mijoz o'zi internetdan topgan tort rasmini va talablarini yuborishi, admin bilan kelishishi mumkin.
5. **Mehr va e'tibor (Personalization):** Shirinlik ko'pincha sovg'a va bayramlar uchun olinishini hisobga olib, "Tort ustiga yozuv yoki bepul tabriknoma" qoldirish imkoniyati.
6. **Ish vaqti va Tungi rejim:** Ish vaqtidan tashqarida buyurtma berilganda mijozni sarosimaga solmasdan, ertangi kunga qabul qilish.
7. **Shubha va xavotirni yo'qotish (Live Tracking):** Buyurtma har bir bosqichida mijozga status xabari boradi (*Qabul qilindi 👩‍🍳 -> Tayyorlandi va qadoqlandi 🎁 -> Kuryer yo'lga chiqdi 🚗 -> Yetkazildi 🎉*).
8. **AI Somelye (Chegaralangan Gemini 2.5 Flash):** Faqat do'kon bazasidagi shirinliklar, mevalar, allergenlar va porsiyalar asosida aniq tavsiya beruvchi aqlli yordamchi.
9. **Ko'p tillilik va moslashuvchan to'lov:** O'zbek va Rus tillari, ham onlayn (Click / Payme), ham joyida naqd/karta to'lovi.

---

## 2. Tizim Arxitekturasi va Texnologiyalar

- **Dasturlash tili:** Python 3.13+
- **Asosiy freymvork:** `aiogram 3.13+` (Asinxron routerlar, FSM holatlari, Inline/Reply klaviaturalar)
- **Ma'lumotlar bazasi:** `aiosqlite` (Asinxron SQLite — tezkor, mustaqil fayl bazasi)
- **AI Integratsiya:** `google-genai` (Gemini 2.5 Flash — shirinliklar konteksti asosida aqlli maslahatchi)
- **To'lov tizimi:** Telegram Payments API (Click va Payme provider tokenlari bilan)
- **Lokalizatsiya:** JSON lug'atlar asosidagi i18n middleware (`locales/uz.json`, `locales/ru.json`)
- **Konfiguratsiya:** `pydantic-settings` yoki `python-dotenv` orqali `.env` muhit o'zgaruvchilari

---

## 3. Loyiha Katalog Strukturasi

```text
telegram yordamchi/
├── bot.py                  # Botni ishga tushirish (Dispatcher, Routers, Polling lifecycle)
├── config.py               # Sozlamalar (.env: BOT_TOKEN, ADMIN_IDS, GEMINI_API_KEY, CLICK_TOKEN, PAYME_TOKEN)
├── database/
│   ├── db.py               # Asinxron DB engine, ulanish, jadvallarni yaratish va boshlang'ich ma'lumotlar
│   ├── models.py           # Ma'lumotlar sxemasi (Users, Categories, Products, Cart, Orders, OrderItems)
│   └── crud.py             # DB operatsiyalari (Foydalanuvchi, Mahsulotlar, Savat, Buyurtmalar)
├── handlers/
│   ├── __init__.py         # Routerlarni birlashtiruvchi markaz
│   ├── common.py           # /start, /help, tilni tanlash (UZ/RU), asosiy menyu navigatsiyasi
│   ├── catalog.py          # Kategoriyalar, mahsulotlar ro'yxati, mahsulot kartasi (+/- savatga qo'shish)
│   ├── cart.py             # Savatni boshqarish (sonini o'zgartirish, tozalash, mahsulotni o'chirish)
│   ├── order.py            # Buyurtma FSM zanjiri (Yetkazish turi, Lokatsiya, Telefon, Tabriknoma, To'lov)
│   ├── payments.py         # Click va Payme to'lovlari (PreCheckoutQuery, SuccessfulPayment)
│   ├── ai_consultant.py    # "🍰 Shirinlik maslahatchisi" Gemini bilan suhbat bo'limi
│   └── admin/
│       ├── __init__.py
│       ├── panel.py        # Admin bosh menyusi, statistika, xabarnomalar
│       ├── products.py     # Mahsulotlarni qo'shish, tahrirlash, stop-list (bor/yo'q)
│       └── orders.py       # Buyurtma statuslarini boshqarish (Tasdiqlash, Tayyor, Yo'lda, Yakunlandi)
├── keyboards/
│   ├── inline.py           # Mahsulot kartasi, toifalar, savat va buyurtma inline tugmalari
│   ├── reply.py            # Bosh menyu, kontakt yuborish, lokatsiya yuborish reply tugmalari
│   └── admin_kb.py         # Admin boshqaruv paneli tugmalari
├── middlewares/
│   └── i18n.py             # Foydalanuvchi tilini aniqlash va tarjima lug'atini contextga yuklash
├── services/
│   ├── gemini.py           # Gemini prompt muhandisligi (shirinliklar menyusi va xushmuomala maslahat)
│   └── notifier.py         # Buyurtma holati o'zgarganda adminga va mijozga bildirishnoma yuborish
├── locales/
│   ├── uz.json             # O'zbekcha interfeys matnlari
│   └── ru.json             # Ruscha interfeys matnlari
└── tests/
    ├── test_database.py    # DB operatsiyalari testlari
    ├── test_cart.py        # Savatcha hisob-kitob testlari
    └── test_i18n.py        # Lug'atlar to'liqligi testlari
```

---

## 4. Ma'lumotlar Bazasi Modeli (Database Schema)

### 1. `users` (Foydalanuvchilar)
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `telegram_id` INTEGER UNIQUE NOT NULL
- `full_name` TEXT NOT NULL
- `username` TEXT
- `phone` TEXT
- `language` TEXT DEFAULT 'uz' ('uz' yoki 'ru')
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### 2. `categories` (Kategoriyalar: Masalan: Tortlar, Mini shirinliklar, Milliy shirinliklar, Ichimliklar)
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `name_uz` TEXT NOT NULL
- `name_ru` TEXT NOT NULL
- `is_active` INTEGER DEFAULT 1
- `sort_order` INTEGER DEFAULT 0

### 3. `products` (Mahsulotlar)
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `category_id` INTEGER REFERENCES categories(id)
- `name_uz` TEXT NOT NULL
- `name_ru` TEXT NOT NULL
- `description_uz` TEXT
- `description_ru` TEXT
- `price` INTEGER NOT NULL (so'mda)
- `weight` TEXT (masalan: "1.2 kg" yoki "6 dona")
- `photo_id` TEXT (Telegram file_id yoki rasm havolasi)
- `is_available` INTEGER DEFAULT 1 (1 - sotuvda bor, 0 - stop-list)

### 4. `cart` (Savatcha)
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id` INTEGER REFERENCES users(telegram_id)
- `product_id` INTEGER REFERENCES products(id)
- `quantity` INTEGER NOT NULL DEFAULT 1

### 5. `orders` (Buyurtmalar)
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `user_id` INTEGER REFERENCES users(telegram_id)
- `order_type` TEXT DEFAULT 'standard' ('standard' yoki 'custom_cake')
- `total_amount` INTEGER NOT NULL
- `delivery_cost` INTEGER DEFAULT 0 (masofa bo'yicha hisoblangan yetkazib berish narxi)
- `delivery_type` TEXT NOT NULL ('delivery' yoki 'pickup')
- `target_time` TEXT NOT NULL (Masalan: 'hozir' yoki '2026-10-29 18:00')
- `address` TEXT
- `latitude` REAL
- `longitude` REAL
- `distance_km` REAL DEFAULT 0
- `phone` TEXT NOT NULL
- `custom_note` TEXT (Tortga yozuv yoki tabriknoma matni)
- `custom_image_id` TEXT (Agar mijoz o'z torti rasmini yuklagan bo'lsa)
- `payment_type` TEXT NOT NULL ('cash', 'card_on_delivery', 'click', 'payme')
- `payment_status` TEXT DEFAULT 'pending' ('pending', 'paid', 'failed')
- `status` TEXT DEFAULT 'new' ('new', 'confirmed', 'preparing', 'delivering', 'completed', 'cancelled')
- `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP

### 6. `order_items` (Buyurtma tarkibidagi mahsulotlar)
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `order_id` INTEGER REFERENCES orders(id)
- `product_id` INTEGER REFERENCES products(id)
- `quantity` INTEGER NOT NULL
- `price_at_purchase` INTEGER NOT NULL

### 7. `settings` (Do'kon sozlamalari va yetkazish tariflari)
- `key` TEXT PRIMARY KEY
- `value` TEXT NOT NULL
(Standart sozlamalar: `store_lat`, `store_lon`, `base_delivery_price`=12000, `price_per_km`=2500, `free_delivery_threshold`=250000, `work_start`='09:00', `work_end`='22:00')

---

## 5. Foydalanuvchi Tajribasi (UX) va Ssenariylar

### 1-Ssenariy: Botga kirish va Bosh menyu
1. Foydalanuvchi `/start` bosadi.
2. Agar birinchi marta kirgan bo'lsa, til tanlash taklif etiladi: `🇺🇿 O'zbekcha` | `🇷🇺 Русский`.
3. So'ng samimiy qutlov bilan Bosh Menyu ochiladi (Reply Keyboard):
   - `🍰 Shirinliklar katalogi`
   - `🛒 Savatcha (0)`
   - `🤖 Shirinlik maslahatchisi (AI)`
   - `📦 Buyurtmalarim`
   - `ℹ️ Biz haqimizda & Aloqa`
   - `🌐 Tilni o'zgartirish`

### 2-Ssenariy: Katalog va Savat
1. Mijoz `🍰 Shirinliklar katalogi`ni tanlaydi.
2. Kategoriyalar chiqadi (masalan: *🎂 Tortlar, 🧁 Kapkeyklar, 🥐 Pishiriqlar, 🍫 Shokoladlar*).
3. Kategoriya tanlangach, mahsulotlar sahifalab (yoki alohida kartalarda) ko'rsatiladi:
   - Rasm
   - Nomi va narxi
   - Ishtahani ochuvchi ta'mi va og'irligi
   - `➕ Savatga qo'shish` yoki `➖ 1 ➕` inline tugmalari.
4. Savatga mahsulot qo'shilganda yuqori menyudagi `🛒 Savatcha (X)` soni darhol yangilanadi.

### 3-Ssenariy: Aniq va Shaffof Buyurtma (FSM)
1. Mijoz `🛒 Savatcha` tugmasini bosadi: mahsulotlar, jami summa ko'rsatiladi va `✅ Buyurtma berish` tugmasi chiqadi.
2. **1-qadam (Vaqt tanlash):** `[ ⚡️ Hozir (60-90 daqiqada) ]` yoki `[ 📅 Oldindan buyurtma (Sana/soat) ]`. Agar do'kon yopiq bo'lsa, faqat oldindan buyurtma rejimi taklif etiladi.
3. **2-qadam (Yetkazish usuli):** `[ 🚗 Yetkazib berish ]` yoki `[ 🛍️ Do'kondan olib ketish ]`.
4. **3-qadam (Manzil va Masofa hisobi):** 
   - `[ 📍 Lokatsiyani yuborish ]` bosilganda bot do'kongacha bo'lgan masofani (km) hisoblaydi.
   - Masalan: *"Sizgacha masofa: 4.2 km. Yetkazib berish narxi: 15,000 so'm"*.
   - Agar savat 250,000 so'mdan oshgan bo'lsa: *"🎉 Tabriklaymiz! Siz uchun yetkazib berish bepul!"*.
5. **4-qadam (Telefon raqam):** `[ 📱 Mening raqamimni yuborish ]` orqali tasdiqlanadi.
6. **5-qadam (Sovg'a/Tabriknoma):** *"Shirinlik bayramga atalganmi? Tort ustiga yozuv yoki bepul tabriknoma matnini yozishingiz mumkin 💌"* (Ostida `[ ➡️ O'tkazib yuborish ]` tugmasi).
7. **6-qadam (To'lov turi):** 
   - `[ 💵 Yetkazilganda naqd ]`
   - `[ 💳 Yetkazilganda karta (terminal) ]`
   - `[ 📲 Click orqali onlayn to'lov ]`
   - `[ 📲 Payme orqali onlayn to'lov ]`
8. **7-qadam (Tasdiqlash):** Mijozga barcha xarajatlar shaffof ko'rsatilgan chek (Mahsulotlar + Yetkazish = Jami) beriladi va tasdiqlangach adminga darhol xabar boradi.

### 4-Ssenariy: 🎨 "O'z tortingizga buyurtma" (Custom Cake Flow)
1. Bosh menyudan `🎨 O'z tortingizga buyurtma` tanlanadi.
2. Bot mijozdan internetdan yoki o'zida bor tort rasmini yuborishni so'raydi.
3. Kutilayotgan vazn (masalan, 2 kg) va tilak/nachinka talablarini yozadi.
4. Telefon va yetkazish vaqti kiritiladi.
5. So'rov adminga yuboriladi: admin narx chiqaradi va mijozga tasdiqlash uchun xabar qaytadi.

### 4-Ssenariy: Gemini AI Maslahatchisi ("Shirinlik Somelyesi")
- Mijoz `🤖 Shirinlik maslahatchisi` bo'limiga o'tganda:
  *"Assalomu alaykum! Men shirinliklar bo'yicha maslahatchiman. Sizga qanday shirinlik yoqadi? Necha kishilik mehmondorchilik yoki qanday bayram rejalashtiryapsiz? Menga yozing, do'konimiz menyusidan eng mosini tanlab beraman! ✨"*
- Gemini do'konning haqiqiy menyusi va tarkibidan kelib chiqib mehmondorchilik hajmiga mos porsiyani tavsiya qiladi va xaridorni to'g'ridan-to'g'ri o'sha mahsulot kartasiga yo'naltiradi.

### 5-Ssenariy: Admin Paneli va Buyurtmalar Nazorati
1. Yangi buyurtma tushganda barcha adminlarga (yoki admin guruhiga) ovozli xabar va to'liq ma'lumot boradi (Mijoz ismi, tel, manzil, xaritadagi lokatsiya, mahsulotlar ro'yxati, yozuv/tilak, to'lov turi).
2. Xabar ostida tezkor tugmalar bo'ladi:
   - `[ ✅ Qabul qilish ]` -> Mijozga: *"Buyurtmangiz tasdiqlandi, qandolatchilar tayyorlashni boshladi 👩‍🍳"*
   - `[ 🎁 Tayyor bo'ldi ]` -> Mijozga: *"Shirinligingiz tayyor va qadoqlandi 🎁"*
   - `[ 🚗 Kuryerga berildi ]` -> Mijozga: *"Kuryerimiz yo'lga chiqdi 🚗"*
   - `[ 🎉 Yetkazildi ]` -> Mijozga: *"Buyurtma yetkazildi. Yoqimli ishtaha! Bizni tanlaganingiz uchun rahmat 🧁"*
   - `[ ❌ Bekor qilish ]` (sababini yozish bilan).
3. Admin paneli orqali mahsulot qo'shish, narxini o'zgartirish va kunlik sotuv statistikasini ko'rish.

---

## 6. Xavfsizlik, Xatoliklarni Bartaraf Etish va Barqarorlik

- **Ma'lumotlar butunligi:** SQLite tranzaksiyalari (ACID), buyurtma berilayotgan paytda mahsulot mavjudligini qayta tekshirish.
- **To'lov xavfsizligi:** Telegram Payments API protokoli bo'yicha `PreCheckoutQuery` da summa va buyurtma holatini solishtirish; muvaffaqiyatli to'lov (`SuccessfulPayment`) kelgandagina statusni `paid` qilish.
- **Geolokatsiya nazorati:** Koordinata kelganda teskari geokodlash yoki xarita ssilkasi (`https://maps.google.com/?q=lat,lng`) yaratish orqali kuryerga qulaylik yaratish.
- **FSM xatoliklari:** Foydalanuvchi adashib boshqa tugmani bosib yuborsa yoki ortga qaytmoqchi bo'lsa, har bir bosqichda `[ ❌ Bekor qilish ]` va `[ ⬅️ Ortga ]` tugmalari bo'lishi.

---

## 7. Tekshirish va Sinov Rejasi

1. **DB va CRUD testlari:** Foydalanuvchi yaratish, kategoriyalar, mahsulotlarni qidirish, savat hisob-kitoblari.
2. **Savat matematikasi:** Narxlar, miqdorlarni oshirish/kamaytirish, umumiy summaning to'g'ri hisoblanishi.
3. **FSM Order Flow:** Buyurtma zanjiri bo'yicha test ssenariylari (to'g'ri ma'lumotlar bilan ham, xato kiritishlar bilan ham).
4. **Lokalizatsiya testi:** `uz.json` va `ru.json` dagi barcha kalitlarning to'liqligi va uyg'unligi.
5. **AI test:** Gemini API orqali menyu asosida to'g'ri tavsiya bera olishi.
