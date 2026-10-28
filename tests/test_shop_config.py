import pytest
import os
from shop_config import load_config, Config

def test_load_config_defaults(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    monkeypatch.setenv("ADMIN_IDS", "12345678,87654321")
    monkeypatch.setenv("STORE_LAT", "41.311081")
    monkeypatch.setenv("STORE_LON", "69.240562")
    
    # Ensure optional/default env vars are unset for defaults test
    monkeypatch.delenv("BASE_DELIVERY_PRICE", raising=False)
    monkeypatch.delenv("PRICE_PER_KM", raising=False)
    monkeypatch.delenv("FREE_DELIVERY_THRESHOLD", raising=False)
    monkeypatch.delenv("WORK_START", raising=False)
    monkeypatch.delenv("WORK_END", raising=False)
    monkeypatch.delenv("CLICK_TOKEN", raising=False)
    monkeypatch.delenv("PAYME_TOKEN", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    
    cfg = load_config()
    assert cfg.bot_token == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    assert cfg.admin_ids == [12345678, 87654321]
    assert cfg.store_lat == 41.311081
    assert cfg.store_lon == 69.240562
    assert cfg.free_delivery_threshold == 250000
    assert cfg.base_delivery_price == 12000
    assert cfg.price_per_km == 2500
    assert cfg.work_start == "09:00"
    assert cfg.work_end == "22:00"
    assert cfg.click_token == ""
    assert cfg.payme_token == ""
    assert cfg.gemini_api_key == ""

def test_load_config_custom_values(monkeypatch):
    monkeypatch.setenv("BOT_TOKEN", "my_custom_token")
    monkeypatch.setenv("ADMIN_IDS", "999, 888 , invalid, 777")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini_secret_123")
    monkeypatch.setenv("CLICK_TOKEN", "click_tok")
    monkeypatch.setenv("PAYME_TOKEN", "payme_tok")
    monkeypatch.setenv("STORE_LAT", "41.2995")
    monkeypatch.setenv("STORE_LON", "69.2401")
    monkeypatch.setenv("BASE_DELIVERY_PRICE", "15000")
    monkeypatch.setenv("PRICE_PER_KM", "3000")
    monkeypatch.setenv("FREE_DELIVERY_THRESHOLD", "300000")
    monkeypatch.setenv("WORK_START", "08:30")
    monkeypatch.setenv("WORK_END", "23:00")

    cfg = load_config()
    assert cfg.bot_token == "my_custom_token"
    assert cfg.admin_ids == [999, 888, 777]
    assert cfg.gemini_api_key == "gemini_secret_123"
    assert cfg.click_token == "click_tok"
    assert cfg.payme_token == "payme_tok"
    assert cfg.store_lat == 41.2995
    assert cfg.store_lon == 69.2401
    assert cfg.base_delivery_price == 15000
    assert cfg.price_per_km == 3000
    assert cfg.free_delivery_threshold == 300000
    assert cfg.work_start == "08:30"
    assert cfg.work_end == "23:00"
