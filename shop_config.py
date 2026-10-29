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
    store_lat: float = 41.311081
    store_lon: float = 69.240562
    base_delivery_price: int = 12000
    price_per_km: int = 2500
    free_delivery_threshold: int = 250000
    work_start: str = "09:00"
    work_end: str = "22:00"

def load_config() -> Config:
    bot_token = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN", "")
    admin_ids_raw = os.getenv("ADMIN_IDS") or os.getenv("OWNER_ID") or "7629355296"
    clean_raw = admin_ids_raw.replace('"', '').replace("'", "").strip()
    admin_ids = [int(i.strip()) for i in clean_raw.split(",") if i.strip().isdigit()]
    
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
