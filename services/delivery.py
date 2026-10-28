import math
from datetime import datetime, time
from shop_config import Config


def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great circle distance between two points on Earth

    using the Haversine formula (Earth radius = 6371.0 km).
    Returns distance in kilometers rounded to 1 decimal place.
    """
    radius_km = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    distance = radius_km * c

    return round(distance, 1)


def calculate_delivery_cost(
    distance_km: float, cart_total: int, config: Config
) -> tuple[int, bool]:
    """Calculate delivery cost based on distance and cart total.

    - If cart_total >= config.free_delivery_threshold: returns (0, True).
    - Else:
        - Up to 3.0 km: config.base_delivery_price.
        - For extra distance beyond 3.0 km: ceil(extra_km) * config.price_per_km.
        - Returns (total_cost, False).
    """
    if cart_total >= config.free_delivery_threshold:
        return 0, True

    if distance_km <= 3.0:
        return int(config.base_delivery_price), False

    extra_km = max(0.0, distance_km - 3.0)
    extra_cost = math.ceil(extra_km) * config.price_per_km
    total_cost = config.base_delivery_price + extra_cost

    return int(total_cost), False


def _parse_time(time_str: str) -> time:
    """Helper to parse HH:MM into a datetime.time object."""
    parts = time_str.strip().split(":")
    return time(int(parts[0]), int(parts[1]))


def is_store_open(config: Config, test_time: str | None = None) -> bool:
    """Check if the store is open based on config operating hours.

    Compares HH:MM against config.work_start and config.work_end.
    If test_time is provided, parses it as HH:MM.
    Otherwise uses current local time.
    Supports overnight operating hours (e.g. 21:00 to 04:00).
    """
    if test_time is not None:
        current = _parse_time(test_time)
    else:
        now = datetime.now()
        current = time(now.hour, now.minute)

    start = _parse_time(config.work_start)
    end = _parse_time(config.work_end)

    if start <= end:
        return start <= current <= end
    else:
        return current >= start or current <= end
