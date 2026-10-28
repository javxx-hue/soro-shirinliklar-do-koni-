# Task 3 Brief: Lokalizatsiya (O'zbek va Rus tillari i18n)

## Goal
Implement a robust, warm, appetizing localization system in Uzbek (Latin) and Russian:
- `locales/uz.json`
- `locales/ru.json`
- `middlewares/i18n.py`
- `tests/test_i18n.py`

## Requirements
1. Key parity: All keys in `locales/uz.json` must exist in `locales/ru.json` without exception.
2. In `middlewares/i18n.py`:
   - `get_text(key: str, lang: str = "uz", **kwargs) -> str`
     - If key not found in given language, fall back to "uz", then return key name if missing.
     - Supports `.format(**kwargs)` string interpolation safely without crashing on missing placeholders.
   - `class I18nMiddleware(BaseMiddleware)`:
     - Detects user language from Telegram `event.from_user.id` using `database.crud.get_user` (or falls back to user's Telegram `language_code` or "uz").
     - Injects `lang` and `_t` helper into the handler data dictionary so handlers can call `data["_t"]("key", **kwargs)`.
3. In `tests/test_i18n.py`:
   - Test key parity between `uz.json` and `ru.json`.
   - Test `get_text` with existing keys, missing keys, formatting placeholders, and fallback behavior.
   - Test `I18nMiddleware` language detection logic.
4. TDD:
   - First write `tests/test_i18n.py` and run to ensure it fails.
   - Implement `locales/uz.json`, `locales/ru.json`, and `middlewares/i18n.py`.
   - Run tests: `.\.venv\Scripts\pytest tests/test_i18n.py -v`.
   - Run full suite: `.\.venv\Scripts\pytest -v`.
   - Commit: `git add locales/ middlewares/ tests/test_i18n.py` and commit with `feat: implement bilingual i18n system with warm appetizing texts`.
