# 🚀 SORO Shirinliklari Telegram Botini Render.com Serveriga O'rnatish Qo'llanmasi

Ushbu qo'llanma orqali siz **SORO - SHIRINLIKLARI** botini [Render.com](https://render.com) bulutli serverida **100% BEPUL** va **24/7 uzluksiz** ishlaydigan qilib sozlashingiz mumkin.

---

## 💡 Qanday qilib bepul ishlaydi?

Render.com da botlar odatda ikki usulda o'rnatiladi:
1. **Background Worker** — faqat pullik tarifda mavjud ($7/oy).
2. **Web Service (Free tier)** — **mutlaqo bepul** (oyiga 750 soat bepul resurs).

Biz bot kodiga (`bot.py`) maxsus yengil `aiohttp` HTTP server qo'shdik. U Render talab qiladigan `$PORT` (10000) orqali `/health` manzilida `200 OK` javob beradi va bir vaqtning o'zida Telegram'dan yangi buyurtmalarni tinglaydi (`long-polling`).

---

## 🛠 Bosqichma-bosqich o'rnatish

### 1-qadam: Kodni GitHub'ga yuklash (Push)

Terminalda quyidagi buyruqlar orqali o'zgarishlarni GitHub omboringizga yuboring:

```powershell
git add .
git commit -m "feat: configure Render.com web service deployment with health check"
git push origin feature/sweet-shop-bot
```

*(Agar asosiy `main` branch orqali ulamoqchi bo'lsangiz, `git checkout main` qilib, `git merge feature/sweet-shop-bot` va `git push origin main` qilishingiz mumkin).*

---

### 2-qadam: Render.com da ro'yxatdan o'tish

1. Brauzerda [dashboard.render.com](https://dashboard.render.com) saytiga kiring.
2. **GitHub** akkauntingiz orqali kiring (Sign in with GitHub).

---

### 3-qadam: Yangi Web Service yaratish

1. Render boshqaruv panelida yuqori o'ng burchakdagi **"New +"** tugmasini bosing.
2. Ro'yxatdan **"Web Service"** ni tanlang.
3. **"Build and deploy from a Git repository"** bandini tanlang va **Next** bosing.
4. O'zingizning GitHub profilingizdagi `tg-asisent` repository'sini tanlang (**Connect** tugmasini bosing).

---

### 4-qadam: Server parametrlarini sozlash

Quyidagi maydonlarni to'ldiring:

| Maydon | Qiymat | Izoh |
| :--- | :--- | :--- |
| **Name** | `soro-shirinliklari-bot` | Xizmatingiz nomi (ixtiyoriy) |
| **Region** | `Frankfurt (EU Central)` | O'zbekistonga eng yaqin server |
| **Branch** | `feature/sweet-shop-bot` yoki `main` | Qaysi branch'dagi kodni olib chiqish |
| **Root Directory** | *(bo'sh qoldiring)* | Asosiy papka |
| **Runtime** | `Python 3` | Dasturlash muhiti |
| **Build Command** | `pip install -r requirements.txt` | Kutubxonalarni o'rnatish buyrug'i |
| **Start Command** | `python bot.py` | Botni ishga tushirish buyrug'i |
| **Instance Type** | **Free** ($0/month) | Bepul tarif |

---

### 5-qadam: Maxfiy o'zgaruvchilarni (Environment Variables) kiritish

Sahifaning pastrog'idagi **"Environment Variables"** bo'limida **"Add Environment Variable"** tugmasini bosib, quyidagi o'zgaruvchilarni qo'shing:

| Key (Kalit) | Value (Qiymat) | Izoh |
| :--- | :--- | :--- |
| `PYTHON_VERSION` | `3.11.9` | Barqaror Python versiyasi |
| `BOT_TOKEN` | `9056386490:AAEaZTMVTN3-C3rGqxcwa_CHaavzNgvwf7U` | BotFather'dan olingan token |
| `ADMIN_IDS` | `7629355296` | Admin Telegram ID |
| `GEMINI_API_KEY` | *(Sizning Gemini API kalitingiz)* | Shirinlik maslahatchisi AI uchun |
| `STORE_LAT` | `39.684100` | Samarqand SORO do'koni kengligi |
| `STORE_LON` | `66.927500` | Samarqand SORO do'koni uzunligi |
| `BASE_DELIVERY_PRICE` | `12000` | Boshlang'ich yetkazib berish narxi (so'm) |
| `PRICE_PER_KM` | `2500` | Har bir km uchun narx (so'm) |
| `FREE_DELIVERY_THRESHOLD` | `250000` | Bepul yetkazib berish chegarasi (so'm) |
| `WORK_START` | `08:30` | Ish boshlanish vaqti |
| `WORK_END` | `22:00` | Ish tugash vaqti |

*(Agar Click yoki Payme orqali onlayn to'lov ulamoqchi bo'lsangiz, `CLICK_TOKEN` va `PAYME_TOKEN` ni ham kiritishingiz mumkin).*

---

### 6-qadam: Ishga tushirish (Deploy)

1. Sahifaning eng pastidagi **"Deploy Web Service"** tugmasini bosing.
2. Render avtomatik ravishda kutubxonalarni o'rnatadi va botni ishga tushiradi.
3. Loglar oynasida quyidagi yozuvlar chiqqach, bot to'liq ishga tushgan bo'ladi:
   ```text
   Render health check HTTP server listening on http://0.0.0.0:10000
   Bot commands configured. Starting sweet shop bot polling...
   ```

---

### 7-qadam: 24/7 Uzluksiz ishlashini ta'minlash (Muhim sir! ⚡️)

Render'ning bepul Web Service'i agar **15 daqiqa** davomida tashqi HTTP so'rov kelmasa, avtomatik ravishda uyqu rejimiga (sleep) o'tadi.

Bot doimo, tun-u kun o'chmasdan ishlashi uchun:
1. Render sizning xizmatingizga bergan havolani nusxalang (masalan: `https://soro-shirinliklari-bot.onrender.com`).
2. Mutlaqo bepul [cron-job.org](https://cron-job.org) yoki [uptimerobot.com](https://uptimerobot.com) saytiga kiring.
3. Yangi monitor / cron-job yarating:
   - **URL:** `https://soro-shirinliklari-bot.onrender.com/health`
   - **Interval:** Har `10 daqiqada` (Every 10 minutes)
4. Bu har 10 daqiqada botingizga yengil ping jo'natib turadi va Render uni hech qachon uyqu rejimiga o'tkazmaydi!

---

### 8-qadam: Kompyuteringizdagi lokal botni to'xtatish

⚠️ **Eslatma:** Render serverda bot ishga tushgach, kompyuteringizda fon rejimida ishlab turgan lokal botni to'xtatish zarur. Chunki bitta Telegram bot tokeni birdaniga ikkita joydan ishlasa, `Conflict: terminated by other getUpdates request` xatoligi yuzaga keladi.

Kompyuterdagi jarayonni to'xtatish:
- Agar terminalda ishlayotgan bo'lsa: `Ctrl + C` bosing.
