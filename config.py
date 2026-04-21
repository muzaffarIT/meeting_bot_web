from __future__ import annotations

import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BOT_USERNAME = os.getenv("BOT_USERNAME", "")

GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
SERVICE_ACCOUNT_FILE = os.getenv("SERVICE_ACCOUNT_FILE", "service_account.json")

TIMEZONE = os.getenv("TIMEZONE", "Asia/Tashkent")
POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", "60"))
SESSION_SECRET = os.getenv("SESSION_SECRET", "change_me_super_secret")

DEFAULT_BRANCH_NAME = os.getenv("DEFAULT_BRANCH_NAME", "Newton Academy")
DEFAULT_BRANCH_ADDRESS = os.getenv("DEFAULT_BRANCH_ADDRESS", "")
DEFAULT_BRANCH_LOCATION_YANDEX_URL = os.getenv("DEFAULT_BRANCH_LOCATION_YANDEX_URL", "")
DEFAULT_BRANCH_LOCATION_GOOGLE_URL = os.getenv("DEFAULT_BRANCH_LOCATION_GOOGLE_URL", "")

APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT = int(os.getenv("APP_PORT", "8000"))


def validate_basic_config() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN not found in .env")

    if not BOT_USERNAME:
        raise ValueError("BOT_USERNAME not found in .env")

    if not GOOGLE_SHEET_ID and not GOOGLE_SHEET_NAME:
        raise ValueError("Set GOOGLE_SHEET_ID or GOOGLE_SHEET_NAME in .env")

    if not SERVICE_ACCOUNT_FILE:
        raise ValueError("SERVICE_ACCOUNT_FILE not found in .env")