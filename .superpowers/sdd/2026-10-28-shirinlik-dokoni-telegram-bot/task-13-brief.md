# Task 13 Brief: Bosh Bot Fayli va Routerlarni Birlashtirish (Main Entrypoint)

## Goal
Implement `handlers/common.py` (for `/start`, language selection, about & contact info, order history, and help) and rewrite `bot.py` as the clean main application entrypoint connecting database lifecycle, middlewares, config injection, bot commands, and all 8 routers.

## Files to Create / Modify
- Modify: `handlers/common.py` (or create if not present)
- Modify: `handlers/__init__.py` (export `common_router`)
- Modify: `bot.py`
- Create: `tests/test_app_startup.py`

## Requirements
1. In `handlers/common.py`:
   - Define `common_router = Router(name="common")`.
   - `/start` handler:
     * Upserts user in DB with `crud.upsert_user`.
     * If user has no language or wants language selection, prompts `language_kb()`.
     * Otherwise displays warm welcome and `main_menu_kb(lang, is_admin=(user.id in config.admin_ids))`.
   - Language callbacks:
     * `lang_uz`, `lang_ru`: updates user language in DB via `crud.set_user_language`, confirms in chosen language, and shows `main_menu_kb`.
   - Navigation buttons / commands:
     * `btn_change_lang` / `/language`: prompts `language_kb()`.
     * `btn_about_contact` / `/about`: displays sweet shop information, working hours, address, phone.
     * `btn_my_orders` / `/my_orders`: lists recent orders for user via `crud.get_user_orders`.
     * `/help`: displays help guide.
2. In `bot.py`:
   - `build_app(config: Config | None = None, db_connection: aiosqlite.Connection | None = None) -> tuple[Bot, Dispatcher]`:
     * Returns configured bot and dispatcher ready for testing or polling.
     * Registers `I18nMiddleware`.
     * Injects `db` and `config` into dispatcher workflow data.
     * Registers all routers: `common_router`, `admin_router`, `catalog_router`, `cart_router`, `order_router`, `custom_cake_router`, `payments_router`, `ai_consultant_router`.
   - `async def main()`:
     * Loads config via `load_config()`.
     * Initializes DB connection at `data/shop.db` and runs `init_db(db)`.
     * Builds app, registers bot menu commands (`/start`, `/catalog`, `/cart`, `/custom_cake`, `/my_orders`, `/ai`, `/language`, `/about`, `/help`).
     * Runs `await dp.start_polling(bot)`.
     * On shutdown, closes DB and bot session cleanly.
3. In `tests/test_app_startup.py`:
   - Tests that `build_app` registers all routers and middlewares.
   - Tests `/start` handler flow with new user and language change.
   - Tests `/about` and `/my_orders` handlers.
4. TDD:
   - Write tests first and verify failure.
   - Implement `handlers/common.py` and `bot.py`.
   - Run tests: `.\.venv\Scripts\pytest tests/test_app_startup.py -v`.
   - Run full suite: `.\.venv\Scripts\pytest -v`.
   - Commit: `git add bot.py handlers/common.py handlers/__init__.py tests/test_app_startup.py` with message `feat: implement main entrypoint and common navigation handlers`.
