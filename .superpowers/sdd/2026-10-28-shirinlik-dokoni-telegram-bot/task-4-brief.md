# Task 4 Brief: Masofa va Yetkazib Berish Narxini Hisoblash Dvigateli (Delivery Engine)

## Goal
Implement business logic for:
1. GPS distance calculation using the Haversine formula.
2. Delivery cost calculation considering base price (first 3 km), per-km price, and free delivery threshold.
3. Store operating hours check (open/closed) based on config settings.

## Files to Create
- `services/__init__.py`
- `services/delivery.py`
- `tests/test_delivery.py`

## Requirements & Specifications
1. In `services/delivery.py`:
   - `def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float`:
     - Uses mathematical Haversine formula (Earth radius = 6371.0 km).
     - Returns distance in kilometers rounded to 1 decimal place (e.g. `4.2`).
   - `def calculate_delivery_cost(distance_km: float, cart_total: int, config: Config) -> tuple[int, bool]`:
     - If `cart_total >= config.free_delivery_threshold`: return `(0, True)` (delivery is free!).
     - Else:
       - Up to 3.0 km: `config.base_delivery_price` (e.g. 12000 so'm).
       - For extra distance beyond 3.0 km: `extra_km = max(0.0, distance_km - 3.0)`, `extra_cost = math.ceil(extra_km) * config.price_per_km`.
       - Total cost = `config.base_delivery_price + extra_cost`.
       - Return `(int(total_cost), False)`.
   - `def is_store_open(config: Config, test_time: str | None = None) -> bool`:
     - Compares HH:MM against `config.work_start` and `config.work_end`.
     - Returns `True` if current time is within open hours, `False` otherwise.
2. In `tests/test_delivery.py`:
   - Test `calculate_distance_km` with known points (e.g. Tashkent coordinates).
   - Test `calculate_delivery_cost` under 3 km, over 3 km, and when cart exceeds `free_delivery_threshold`.
   - Test `is_store_open` during day and at night.
3. TDD:
   - Write tests in `tests/test_delivery.py` first and verify failure.
   - Implement `services/__init__.py` and `services/delivery.py`.
   - Run tests: `.\.venv\Scripts\pytest tests/test_delivery.py -v`.
   - Run full suite: `.\.venv\Scripts\pytest -v`.
   - Commit: `git add services/ tests/test_delivery.py` with message `feat: implement delivery cost calculation and store hours engine`.
