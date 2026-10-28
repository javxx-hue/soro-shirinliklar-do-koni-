# Task 1 Brief: Loyiha Muhiti va Konfiguratsiyasi (Config & Requirements)

## Goal
Implement validated configuration loading in `shop_config.py` and ensure all required dependencies (`aiosqlite>=0.20`, `aiogram>=3.13`, etc.) are documented in `requirements.txt` and `.env.example`.

## Files
- Modify: `requirements.txt`
- Modify: `.env.example`
- Create: `shop_config.py`
- Create / Test: `tests/test_shop_config.py`

## Specifications
Follow the implementation plan Task 1 strictly:
- `shop_config.py` must define `Config` dataclass with fields:
  - `bot_token: str`
  - `admin_ids: List[int]`
  - `gemini_api_key: str = ""`
  - `click_token: str = ""`
  - `payme_token: str = ""`
  - `store_lat: float = 41.311081`
  - `store_lon: float = 69.240562`
  - `base_delivery_price: int = 12000`
  - `price_per_km: int = 2500`
  - `free_delivery_threshold: int = 250000`
  - `work_start: str = "09:00"`
  - `work_end: str = "22:00"`
- `load_config() -> Config` function that loads from environment via `dotenv`.
- Write `tests/test_shop_config.py` as specified in plan.
- Run tests: `.venv\Scripts\pytest tests/test_shop_config.py -v`
- Once test passes, commit with message: `feat: implement shop configuration and update requirements`
- Report back with status and commit hash.
