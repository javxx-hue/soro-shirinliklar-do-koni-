import pytest
from shop_config import Config
from services.delivery import (
    calculate_distance_km,
    calculate_delivery_cost,
    is_store_open,
)


@pytest.fixture
def sample_config():
    return Config(
        bot_token="test_token",
        admin_ids=[123456],
        store_lat=41.311081,
        store_lon=69.240562,
        base_delivery_price=12000,
        price_per_km=2500,
        free_delivery_threshold=250000,
        work_start="09:00",
        work_end="22:00",
    )


class TestCalculateDistanceKm:
    def test_same_point_returns_zero(self):
        distance = calculate_distance_km(41.311081, 69.240562, 41.311081, 69.240562)
        assert distance == 0.0

    def test_known_tashkent_points(self):
        # Amir Timur Square (41.311081, 69.240562) to Chorsu Bazaar (41.3275, 69.2361)
        # Expected distance ~ 1.9 km
        distance = calculate_distance_km(41.311081, 69.240562, 41.3275, 69.2361)
        assert distance == pytest.approx(1.9, abs=0.1)

        # Amir Timur Square to Tashkent TV Tower (41.3458, 69.2847)
        # Expected distance ~ 5.3 km
        distance_tower = calculate_distance_km(41.311081, 69.240562, 41.3458, 69.2847)
        assert distance_tower == pytest.approx(5.3, abs=0.2)

    def test_symmetry(self):
        d1 = calculate_distance_km(41.311081, 69.240562, 41.3458, 69.2847)
        d2 = calculate_distance_km(41.3458, 69.2847, 41.311081, 69.240562)
        assert d1 == d2

    def test_returns_one_decimal_place(self):
        distance = calculate_distance_km(41.311081, 69.240562, 41.3275, 69.2361)
        # Check string representation or round invariant
        assert round(distance, 1) == distance


class TestCalculateDeliveryCost:
    def test_free_delivery_when_threshold_reached_or_exceeded(self, sample_config):
        cost, is_free = calculate_delivery_cost(5.5, 250000, sample_config)
        assert cost == 0
        assert is_free is True

        cost, is_free = calculate_delivery_cost(15.0, 300000, sample_config)
        assert cost == 0
        assert is_free is True

    def test_base_delivery_up_to_3km(self, sample_config):
        cost, is_free = calculate_delivery_cost(0.5, 100000, sample_config)
        assert cost == 12000
        assert is_free is False

        cost, is_free = calculate_delivery_cost(3.0, 100000, sample_config)
        assert cost == 12000
        assert is_free is False

    def test_extra_km_rounding_and_calculation(self, sample_config):
        # 3.1 km -> extra = 0.1 -> ceil = 1 km extra -> 12000 + 2500 = 14500
        cost, is_free = calculate_delivery_cost(3.1, 100000, sample_config)
        assert cost == 14500
        assert is_free is False

        # 4.0 km -> extra = 1.0 -> ceil = 1 km extra -> 12000 + 2500 = 14500
        cost, is_free = calculate_delivery_cost(4.0, 100000, sample_config)
        assert cost == 14500
        assert is_free is False

        # 4.2 km -> extra = 1.2 -> ceil = 2 km extra -> 12000 + 5000 = 17000
        cost, is_free = calculate_delivery_cost(4.2, 50000, sample_config)
        assert cost == 17000
        assert is_free is False

        # 7.0 km -> extra = 4.0 -> ceil = 4 km extra -> 12000 + 10000 = 22000
        cost, is_free = calculate_delivery_cost(7.0, 50000, sample_config)
        assert cost == 22000
        assert is_free is False

    def test_just_below_threshold_is_not_free(self, sample_config):
        cost, is_free = calculate_delivery_cost(2.0, 249999, sample_config)
        assert cost == 12000
        assert is_free is False


class TestIsStoreOpen:
    def test_open_during_regular_hours(self, sample_config):
        assert is_store_open(sample_config, test_time="09:00") is True
        assert is_store_open(sample_config, test_time="14:30") is True
        assert is_store_open(sample_config, test_time="22:00") is True

    def test_closed_outside_regular_hours(self, sample_config):
        assert is_store_open(sample_config, test_time="08:59") is False
        assert is_store_open(sample_config, test_time="22:01") is False
        assert is_store_open(sample_config, test_time="03:00") is False

    def test_overnight_operating_hours(self):
        night_config = Config(
            bot_token="test_token",
            work_start="21:00",
            work_end="04:00",
        )
        assert is_store_open(night_config, test_time="21:00") is True
        assert is_store_open(night_config, test_time="23:30") is True
        assert is_store_open(night_config, test_time="02:00") is True
        assert is_store_open(night_config, test_time="04:00") is True
        assert is_store_open(night_config, test_time="04:01") is False
        assert is_store_open(night_config, test_time="12:00") is False
        assert is_store_open(night_config, test_time="20:59") is False

    def test_default_current_time_returns_boolean(self, sample_config):
        result = is_store_open(sample_config)
        assert isinstance(result, bool)
