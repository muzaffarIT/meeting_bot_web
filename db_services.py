from __future__ import annotations
from typing import Any
import time

from db_models import SessionLocal, Lead, User, Setting, Message
import sheets

def _model_to_dict(obj) -> dict[str, Any]:
    if not obj:
        return {}
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

def get_all_leads() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        leads = db.query(Lead).all()
        return [_model_to_dict(l) for l in leads]
    finally:
        db.close()

def get_all_users() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        users = db.query(User).all()
        return [_model_to_dict(u) for u in users]
    finally:
        db.close()

def find_lead_by_id(lead_id: str) -> dict[str, Any] | None:
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.lead_id == str(lead_id).strip()).first()
        return _model_to_dict(lead) if lead else None
    finally:
        db.close()

def find_user_by_login(login: str) -> dict[str, Any] | None:
    from sqlalchemy import func
    db = SessionLocal()
    try:
        needle = str(login).strip().lower()
        user = db.query(User).filter(func.lower(User.login) == needle).first()
        return _model_to_dict(user) if user else None
    finally:
        db.close()

def update_lead_fields(lead_id: str, updates: dict[str, Any]) -> bool:
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.lead_id == str(lead_id).strip()).first()
        if not lead:
            return False
        for py_name, value in updates.items():
            if hasattr(lead, py_name):
                setattr(lead, py_name, str(value))
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()
        
    try:
        sheets.update_lead_fields(lead_id, updates)
    except Exception as e:
        print(f"Google Sheets sync error (update_lead_fields): {e}")

    return True

def update_user_fields(login: str, updates: dict[str, Any]) -> bool:
    from sqlalchemy import func
    db = SessionLocal()
    try:
        needle = str(login).strip().lower()
        user = db.query(User).filter(func.lower(User.login) == needle).first()
        if not user:
            return False
        for py_name, value in updates.items():
            if hasattr(user, py_name):
                setattr(user, py_name, str(value))
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()

    try:
        sheets.update_user_fields(login, updates)
    except Exception as e:
        print(f"Google Sheets sync error (update_user_fields): {e}")

    return True

def ensure_settings_sheet() -> None:
    # Deprecated for DB, but kept for compatibility
    pass

def ensure_headers() -> None:
    # Deprecated for DB, handled by sqlalchemy create_all
    pass

# Simplified global cache for settings since it's light
_SETTINGS_CACHE = {"ts": 0.0, "data": None}
_SETTINGS_TTL = 30

def get_settings_raw() -> dict[str, str]:
    from constants import DEFAULT_SETTINGS
    db = SessionLocal()
    try:
        settings = db.query(Setting).all()
        out = {s.key: s.value for s in settings}
        for k, v in DEFAULT_SETTINGS.items():
            out.setdefault(k, v)
        return out
    finally:
        db.close()

def get_settings_cached(force: bool = False) -> dict[str, str]:
    now = time.time()
    if not force and _SETTINGS_CACHE["data"] and (now - _SETTINGS_CACHE["ts"] < _SETTINGS_TTL):
        return _SETTINGS_CACHE["data"]
    data = get_settings_raw()
    _SETTINGS_CACHE["data"] = data
    _SETTINGS_CACHE["ts"] = now
    return data

def update_settings_bulk(updates: dict[str, str]) -> None:
    db = SessionLocal()
    try:
        for key, value in updates.items():
            k = str(key).strip()
            v = str(value).strip()
            s = db.query(Setting).filter(Setting.key == k).first()
            if s:
                s.value = v
            else:
                db.add(Setting(key=k, value=v))
        db.commit()
        _SETTINGS_CACHE["ts"] = 0
        _SETTINGS_CACHE["data"] = None
    except Exception:
        db.rollback()
    finally:
        db.close()

def append_lead_dict(data: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        filtered_data = {k: str(v) for k, v in data.items() if hasattr(Lead, k)}
        db_lead = Lead(**filtered_data)
        db.add(db_lead)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    try:
        sheets.append_lead_dict(data)
    except Exception as e:
        print(f"Google Sheets sync error (append_lead): {e}")

def append_user_dict(data: dict[str, Any]) -> None:
    db = SessionLocal()
    try:
        filtered_data = {k: str(v) for k, v in data.items() if hasattr(User, k)}
        db_user = User(**filtered_data)
        db.add(db_user)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

    try:
        sheets.append_user_dict(data)
    except Exception as e:
        print(f"Google Sheets sync error (append_user): {e}")
    finally:
        db.close()

def find_lead_by_tg_id(tg_id: str) -> dict[str, Any] | None:
    """Find lead by telegram_user_id (needed for incoming message handler)."""
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.telegram_user_id == str(tg_id).strip()).order_by(Lead.created_at.desc()).first()
        return _model_to_dict(lead) if lead else None
    finally:
        db.close()

def save_message(lead_id: str, direction: str, sender: str, text: str, created_at: str = '') -> None:
    """Save a chat message. direction='in' (from client) or 'out' (from manager)."""
    from datetime import datetime
    db = SessionLocal()
    try:
        msg = Message(
            lead_id=str(lead_id).strip(),
            direction=direction,
            sender=sender,
            text=text,
            created_at=created_at or datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            is_read='1' if direction == 'out' else '0',  # outgoing always read
        )
        db.add(msg)
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()

def get_messages(lead_id: str) -> list[dict[str, Any]]:
    """Get all chat messages for a lead, ordered by time."""
    db = SessionLocal()
    try:
        msgs = db.query(Message).filter(Message.lead_id == str(lead_id).strip()).order_by(Message.id).all()
        return [_model_to_dict(m) for m in msgs]
    finally:
        db.close()

def count_unread_messages() -> int:
    """Count how many leads have unread messages from clients."""
    db = SessionLocal()
    try:
        leads_with_unread = db.query(Message.lead_id).filter(
            Message.direction == 'in',
            Message.is_read == '0'
        ).distinct().count()
        return leads_with_unread
    finally:
        db.close()

def mark_messages_read(lead_id: str) -> None:
    """Mark all incoming messages for a lead as read."""
    db = SessionLocal()
    try:
        db.query(Message).filter(
            Message.lead_id == str(lead_id).strip(),
            Message.direction == 'in',
            Message.is_read == '0'
        ).update({'is_read': '1'})
        db.commit()
    except Exception:
        db.rollback()
    finally:
        db.close()
