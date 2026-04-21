from __future__ import annotations
from constants import HEADERS_SETTINGS
import time
from requests.exceptions import ConnectionError as RequestsConnectionError

from functools import lru_cache
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_SHEET_ID, GOOGLE_SHEET_NAME, SERVICE_ACCOUNT_FILE
from constants import (
    HEADERS_LEADS,
    HEADERS_USERS,
    HEADER_MAP_LEADS,
    HEADER_MAP_USERS,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
DEFAULT_SETTINGS = {
    # Филиал
    'branch_name': 'Newton Academy',
    'branch_address': '',
    'location_google_url': '',
    'location_yandex_url': '',

    # Напоминания (в часах)
    'remind_3d_enabled': 'ДА',
    'remind_3d_hours': '72',

    'remind_1d_enabled': 'ДА',
    'remind_1d_hours': '24',

    'remind_6h_enabled': 'ДА',
    'remind_6h_hours': '6',

    'remind_3h_enabled': 'ДА',
    'remind_3h_hours': '3',

    'remind_2h_enabled': 'ДА',
    'remind_2h_hours': '2',

    # Интервал проверки воркера
    'poll_interval_seconds': '60',
}


import os
import json
from google.oauth2.service_account import Credentials
@lru_cache(maxsize=1)
def _client():
    json_str = os.getenv("SERVICE_ACCOUNT_JSON")

    if json_str:
        info = json.loads(json_str)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    return gspread.authorize(creds)


@lru_cache(maxsize=1)
def spreadsheet() -> gspread.Spreadsheet:
    client = _client()
    if GOOGLE_SHEET_ID:
        return client.open_by_key(GOOGLE_SHEET_ID)
    return client.open(GOOGLE_SHEET_NAME)


@lru_cache(maxsize=8)
def get_or_create_worksheet(title: str, rows: int = 1000, cols: int = 40) -> gspread.Worksheet:
    sh = spreadsheet()
    try:
        return sh.worksheet(title)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=title, rows=rows, cols=cols)

def _with_retry(fn, *args, **kwargs):
    last_exc = None
    for attempt in range(4):
        try:
            return fn(*args, **kwargs)
        except (RequestsConnectionError, gspread.exceptions.APIError) as exc:
            if isinstance(exc, gspread.exceptions.APIError):
                try:
                    # In older gspread, response might be a dictionary or object
                    status = None
                    if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
                        status = exc.response.status_code
                    elif isinstance(exc.args[0], dict) and "code" in exc.args[0]:
                        status = exc.args[0]["code"]
                    
                    if status and 400 <= status < 500 and status != 429:
                        raise exc
                except Exception:
                    pass # Fallback to retry if we can't parse status code
            
            last_exc = exc
            time.sleep(2 ** attempt)
    raise last_exc

def ensure_headers() -> None:
    leads_ws = get_or_create_worksheet("leads")
    users_ws = get_or_create_worksheet("users")

    if leads_ws.row_values(1) != HEADERS_LEADS:
        leads_ws.update("A1", [HEADERS_LEADS])

    if users_ws.row_values(1) != HEADERS_USERS:
        users_ws.update("A1", [HEADERS_USERS])

    # ✅ всегда
    ensure_settings_sheet()

def _rows_to_dicts(values: list[list[str]], header_map: dict[str, str]) -> list[dict[str, Any]]:
    if not values:
        return []

    headers = values[0]
    records: list[dict[str, Any]] = []

    for row in values[1:]:
        if not any(str(cell).strip() for cell in row):
            continue

        raw = {headers[i]: row[i] if i < len(row) else "" for i in range(len(headers))}
        normalized = {py_name: raw.get(sheet_name, "") for py_name, sheet_name in header_map.items()}
        records.append(normalized)

    return records


_LEADS_CACHE = {"ts": 0.0, "data": None}
_USERS_CACHE = {"ts": 0.0, "data": None}
_DATA_TTL = 30  # seconds

def get_all_leads() -> list[dict[str, Any]]:
    now = time.time()
    if _LEADS_CACHE["data"] is not None and (now - _LEADS_CACHE["ts"] < _DATA_TTL):
        return _LEADS_CACHE["data"]
        
    ws = get_or_create_worksheet("leads")
    values = _with_retry(ws.get_all_values)
    data = _rows_to_dicts(values, HEADER_MAP_LEADS)
    _LEADS_CACHE["data"] = data
    _LEADS_CACHE["ts"] = now
    return data


def get_all_users() -> list[dict[str, Any]]:
    now = time.time()
    if _USERS_CACHE["data"] is not None and (now - _USERS_CACHE["ts"] < _DATA_TTL):
        return _USERS_CACHE["data"]
        
    ws = get_or_create_worksheet("users")
    values = _with_retry(ws.get_all_values)
    data = _rows_to_dicts(values, HEADER_MAP_USERS)
    _USERS_CACHE["data"] = data
    _USERS_CACHE["ts"] = now
    return data


def find_lead_by_id(lead_id: str) -> dict[str, Any] | None:
    needle = str(lead_id).strip()
    for row in get_all_leads():
        if str(row.get("lead_id", "")).strip() == needle:
            return row
    return None


def find_user_by_login(login: str) -> dict[str, Any] | None:
    needle = str(login).strip().lower()
    for row in get_all_users():
        if str(row.get("login", "")).strip().lower() == needle:
            return row
    return None


def _find_row_index(sheet_name: str, id_column_title: str, id_value: str) -> int | None:
    ws = get_or_create_worksheet(sheet_name)
    values = _with_retry(ws.get_all_values)

    if not values:
        return None

    headers = values[0]
    try:
        idx = headers.index(id_column_title)
    except ValueError:
        return None

    target = str(id_value).strip()
    for row_num, row in enumerate(values[1:], start=2):
        if idx < len(row) and str(row[idx]).strip() == target:
            return row_num

    return None


def update_lead_fields(lead_id: str, updates: dict[str, Any]) -> bool:
    ws = get_or_create_worksheet("leads")
    row_idx = _find_row_index("leads", HEADERS_LEADS[0], lead_id)

    if not row_idx:
        return False

    for py_name, value in updates.items():
        header = HEADER_MAP_LEADS.get(py_name)
        if not header:
            continue
        col_idx = HEADERS_LEADS.index(header) + 1
        _with_retry(ws.update_cell, row_idx, col_idx, value)

    _LEADS_CACHE["ts"] = 0
    return True


def update_user_fields(login: str, updates: dict[str, Any]) -> bool:
    ws = get_or_create_worksheet("users")
    row_idx = _find_row_index("users", HEADERS_USERS[0], login)

    if not row_idx:
        return False

    for py_name, value in updates.items():
        header = HEADER_MAP_USERS.get(py_name)
        if not header:
            continue
        col_idx = HEADERS_USERS.index(header) + 1
        _with_retry(ws.update_cell, row_idx, col_idx, value)

    _USERS_CACHE["ts"] = 0
    return True

import time

_SETTINGS_CACHE = {"ts": 0.0, "data": None}
_SETTINGS_TTL = 20  # секунд, чтобы не долбить Google

def ensure_settings_sheet() -> None:
    ws = get_or_create_worksheet('settings', rows=200, cols=2)
    if ws.row_values(1) != HEADERS_SETTINGS:
        ws.update('A1', [HEADERS_SETTINGS])

    values = ws.get_all_values()
    existing = {}
    for row in values[1:]:
        if len(row) >= 2 and str(row[0]).strip():
            existing[str(row[0]).strip()] = str(row[1]).strip()

    # если пусто — засеять дефолтами
    if not existing:
        rows = [[k, v] for k, v in DEFAULT_SETTINGS.items()]
        ws.update('A2', rows)
        _SETTINGS_CACHE["ts"] = 0
        _SETTINGS_CACHE["data"] = None

def get_settings_raw() -> dict[str, str]:
    ws = get_or_create_worksheet('settings', rows=200, cols=2)
    values = ws.get_all_values()
    out: dict[str, str] = {}
    for row in values[1:]:
        if len(row) >= 2 and str(row[0]).strip():
            out[str(row[0]).strip()] = str(row[1]).strip()
    # подмешиваем дефолты (чтобы не было KeyError)
    for k, v in DEFAULT_SETTINGS.items():
        out.setdefault(k, v)
    return out

def get_settings_cached(force: bool = False) -> dict[str, str]:
    now = time.time()
    if not force and _SETTINGS_CACHE["data"] and (now - _SETTINGS_CACHE["ts"] < _SETTINGS_TTL):
        return _SETTINGS_CACHE["data"]
    data = get_settings_raw()
    _SETTINGS_CACHE["data"] = data
    _SETTINGS_CACHE["ts"] = now
    return data

def update_settings_bulk(updates: dict[str, str]) -> None:
    ws = get_or_create_worksheet('settings', rows=200, cols=2)
    values = ws.get_all_values()
    row_map = {}
    for i, row in enumerate(values[1:], start=2):
        if row and str(row[0]).strip():
            row_map[str(row[0]).strip()] = i

    for key, value in updates.items():
        key = str(key).strip()
        value = str(value).strip()
        if key in row_map:
            ws.update_cell(row_map[key], 2, value)
        else:
            ws.append_row([key, value], value_input_option='USER_ENTERED')

    _SETTINGS_CACHE["ts"] = 0
    _SETTINGS_CACHE["data"] = None

def append_lead_dict(data: dict[str, Any]) -> None:
    ws = get_or_create_worksheet("leads")
    row = [data.get(py_name, "") for py_name in HEADER_MAP_LEADS.keys()]
    _with_retry(ws.append_row, row, value_input_option='USER_ENTERED')
    _LEADS_CACHE["ts"] = 0


def append_user_dict(data: dict[str, Any]) -> None:
    ws = get_or_create_worksheet("users")
    row = [data.get(py_name, "") for py_name in HEADER_MAP_USERS.keys()]
    _with_retry(ws.append_row, row, value_input_option='USER_ENTERED')
    _USERS_CACHE["ts"] = 0