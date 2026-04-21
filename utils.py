from __future__ import annotations

import secrets
from datetime import datetime
from zoneinfo import ZoneInfo

from config import TIMEZONE

TZ = ZoneInfo(TIMEZONE)


def now_local() -> datetime:
    return datetime.now(TZ)


def bool_to_sheet(value: bool) -> str:
    return 'ДА' if value else 'НЕТ'


def normalize_bool(value: object) -> bool:
    text = str(value or '').strip().lower()
    return text in {'да', 'yes', 'true', '1'}


def parse_meeting_datetime(lead: dict) -> datetime | None:
    iso_value = str(lead.get('meeting_datetime_iso', '')).strip()
    if iso_value:
        try:
            dt = datetime.fromisoformat(iso_value)
            return dt if dt.tzinfo else dt.replace(tzinfo=TZ)
        except ValueError:
            pass

    date_text = str(lead.get('meeting_date', '')).strip()
    time_text = str(lead.get('meeting_time', '')).strip()
    if not date_text or not time_text:
        return None

    for pattern in ('%Y-%m-%d %H:%M', '%d.%m.%Y %H:%M', '%d/%m/%Y %H:%M'):
        try:
            return datetime.strptime(f'{date_text} {time_text}', pattern).replace(tzinfo=TZ)
        except ValueError:
            continue
    return None


def make_lead_id() -> str:
    return secrets.token_urlsafe(6).replace('-', 'A').replace('_', 'B')[:10]


def safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
