from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()


def _env_int(name: str, default: int) -> int:
    raw = (os.getenv(name) or '').strip()
    try:
        return int(float(raw)) if raw else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = (os.getenv(name) or '').strip().replace(',', '.')
    try:
        return float(raw) if raw else default
    except ValueError:
        return default

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")

TIMEZONE = os.getenv("TIMEZONE", "Asia/Tashkent")
POLL_INTERVAL_SECONDS = _env_int("POLL_INTERVAL_SECONDS", 60)
SESSION_SECRET = os.getenv("SESSION_SECRET", "change_me_super_secret")

DEFAULT_BRANCH_NAME = os.getenv("DEFAULT_BRANCH_NAME", "Newton Academy")
DEFAULT_BRANCH_ADDRESS = os.getenv("DEFAULT_BRANCH_ADDRESS", "")
DEFAULT_BRANCH_LOCATION_YANDEX_URL = os.getenv("DEFAULT_BRANCH_LOCATION_YANDEX_URL", "")
DEFAULT_BRANCH_LOCATION_GOOGLE_URL = os.getenv("DEFAULT_BRANCH_LOCATION_GOOGLE_URL", "")
# Координаты филиала для нативной локации в Telegram (широта, долгота)
DEFAULT_BRANCH_LATITUDE = _env_float("DEFAULT_BRANCH_LATITUDE", 41.293504)
DEFAULT_BRANCH_LONGITUDE = _env_float("DEFAULT_BRANCH_LONGITUDE", 69.245394)

APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = _env_int("APP_PORT", 8000)

# Публичный адрес панели (например https://xxx.up.railway.app).
# Если задан — клиентам отправляется красивая ссылка-лендинг {PUBLIC_BASE_URL}/go/{lead_id}
# вместо «голой» t.me ссылки. Если не задан — используется прямая ссылка на бота.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")


def validate_basic_config() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not found in .env")

    if not BOT_USERNAME:
        raise ValueError("BOT_USERNAME not found in .env")

    if not GOOGLE_SHEET_ID and not GOOGLE_SHEET_NAME:
        raise ValueError("Set GOOGLE_SHEET_ID or GOOGLE_SHEET_NAME in .env")

    if not SERVICE_ACCOUNT_FILE:
        raise ValueError("SERVICE_ACCOUNT_FILE not found in .env")