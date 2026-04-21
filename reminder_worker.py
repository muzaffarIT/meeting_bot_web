from __future__ import annotations
from texts import reminder_text, button_labels
import asyncio
import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup

from config import BOT_TOKEN, POLL_INTERVAL_SECONDS, validate_basic_config
from db_services import ensure_headers, get_all_leads, update_lead_fields, get_settings_cached
from utils import normalize_bool, now_local, parse_meeting_datetime
from config import DEFAULT_BRANCH_LOCATION_GOOGLE_URL, DEFAULT_BRANCH_LOCATION_YANDEX_URL
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)

CHECKPOINT_DEFS = [
    ('3 дня', 'remind_3d_sent', 'remind_3d_enabled', 'remind_3d_hours'),
    ('1 день', 'remind_1d_sent', 'remind_1d_enabled', 'remind_1d_hours'),
    ('6 часов', 'remind_6h_sent', 'remind_6h_enabled', 'remind_6h_hours'),
    ('3 часа', 'remind_3h_sent', 'remind_3h_enabled', 'remind_3h_hours'),
    ('2 часа', 'remind_2h_sent', 'remind_2h_enabled', 'remind_2h_hours'),
]


def _settings_str(s: dict, key: str, default: str = "") -> str:
    return str(s.get(key, default) or default).strip()


def _settings_float(s: dict, key: str, default: float) -> float:
    raw = _settings_str(s, key, str(default)).replace(',', '.')
    try:
        return float(raw)
    except ValueError:
        return default


def _settings_int(s: dict, key: str, default: int) -> int:
    raw = _settings_str(s, key, str(default)).replace(',', '.')
    try:
        return int(float(raw))
    except ValueError:
        return default


def build_checkpoints() -> list[tuple[str, str, float, float]]:
    """Build time windows in HOURS from settings.

    Result format: [(label, field_name, upper_hours, lower_hours), ...]
    Example windows (defaults): (72..24], (24..6], (6..3], (3..2], (2..0]
    """
    s = get_settings_cached(force=False)
    enabled: list[tuple[str, str, float]] = []

    for label, field_name, enabled_key, hours_key in CHECKPOINT_DEFS:
        if not normalize_bool(_settings_str(s, enabled_key, 'НЕТ')):
            continue
        hours = _settings_float(s, hours_key, 0.0)
        if hours <= 0:
            continue
        enabled.append((label, field_name, hours))

    windows: list[tuple[str, str, float, float]] = []
    for idx, (label, field_name, upper) in enumerate(enabled):
        lower = enabled[idx + 1][2] if idx + 1 < len(enabled) else 0.0
        lower = min(lower, upper)
        windows.append((label, field_name, upper, lower))
    return windows


def lead_with_settings(lead: dict) -> dict:
    """Overlay settings onto lead so changes affect existing leads too."""
    s = get_settings_cached(force=False)
    out = dict(lead)

    branch_name = _settings_str(s, 'branch_name', '').strip()
    branch_address = _settings_str(s, 'branch_address', '').strip()
    if branch_name:
        out['branch_name'] = branch_name
    if branch_address:
        out['address_text'] = branch_address

    return out


def manager_contact_button(lead: dict, lang: str) -> InlineKeyboardButton | None:
    labels = button_labels(lang)
    manager_tg = str(lead.get("manager_telegram", "")).strip().lstrip("@")
    manager_phone = str(lead.get("manager_phone", "")).strip()

    if manager_tg:
        return InlineKeyboardButton(
            labels["contact_tg"],
            url=f"https://t.me/{manager_tg}"
        )

    if manager_phone:
        digits = "".join(ch for ch in manager_phone if ch.isdigit())
        if digits:
            return InlineKeyboardButton(
                labels["contact_phone"],
                url=f"https://wa.me/{digits}"
            )

    return None


def reminder_keyboard(lead: dict, confirmed: bool, lang: str) -> InlineKeyboardMarkup | None:
    labels = button_labels(lang)
    rows = []

    s = get_settings_cached(force=False)
    google_url = _settings_str(s, 'location_google_url', DEFAULT_BRANCH_LOCATION_GOOGLE_URL or '')
    yandex_url = _settings_str(s, 'location_yandex_url', DEFAULT_BRANCH_LOCATION_YANDEX_URL or '')

    if confirmed:
        if google_url:
            rows.append([
                InlineKeyboardButton(labels.get("google_maps", "📍 Google Maps"), url=google_url)
            ])

        if yandex_url:
            rows.append([
                InlineKeyboardButton(labels.get("yandex_maps", "📍 Яндекс Карты"), url=yandex_url)
            ])

    contact_btn = manager_contact_button(lead, lang)
    if contact_btn:
        rows.append([contact_btn])

    return InlineKeyboardMarkup(rows) if rows else None

async def send_reminder(lead: dict, label: str, field_name: str) -> None:
    chat_id = str(lead.get("telegram_user_id", "")).strip()
    if not chat_id:
        logger.info("skip lead_id=%s: empty telegram_user_id", lead.get("lead_id", ""))
        return
    
    lead = lead_with_settings(lead)

    lang = str(lead.get("language", "ru")).strip() or "ru"
    confirmed = str(lead.get("confirmed", "")).strip().upper() in {"YES", "TRUE", "1", "ДА"}

    text = reminder_text(lead, lang, label, confirmed)

    manager_phone = str(lead.get("manager_phone", "")).strip()
    if manager_phone:
        if lang == "uz":
            text += f"\n\n📞 Menejer raqami: {manager_phone}"
        else:
            text += f"\n\n📞 Номер менеджера: {manager_phone}"

    await bot.send_message(
        chat_id=int(chat_id),
        text=text,
        reply_markup=reminder_keyboard(lead, confirmed, lang),
        parse_mode='HTML',
    )

    update_lead_fields(lead["lead_id"], {field_name: "ДА"})
    logger.info("Reminder sent: lead_id=%s label=%s", lead["lead_id"], label)

async def process_once() -> None:
    now_dt = now_local()
    leads = get_all_leads()
    logger.info('Checking %s leads for reminders...', len(leads))

    checkpoints = build_checkpoints()

    for lead in leads:
        lead_id = str(lead.get("lead_id", "")).strip()
        bot_started = normalize_bool(lead.get("bot_started", ""))

        if not lead_id:
            logger.info("skip lead: empty lead_id")
            continue

        if not bot_started:
            logger.info("skip lead_id=%s: bot_started is false", lead_id)
            continue

        meeting_dt = parse_meeting_datetime(lead)
        if not meeting_dt or meeting_dt <= now_dt:
            continue

        hours_left = (meeting_dt - now_dt).total_seconds() / 3600
        logger.info(
            "lead_id=%s bot_started=%s confirmed=%s chat_id=%s hours_left=%.4f",
            lead_id,
            lead.get("bot_started", ""),
            lead.get("confirmed", ""),
            lead.get("telegram_user_id", ""),
            hours_left,
        )

        for label, field_name, upper_bound, lower_bound in checkpoints:
            if normalize_bool(lead.get(field_name, '')):
                continue
            if lower_bound < hours_left <= upper_bound:
                try:
                    await send_reminder(lead, label, field_name)
                    logger.info('Reminder sent: lead_id=%s label=%s', lead_id, label)
                except Exception as exc:  # noqa: BLE001
                    logger.exception('Failed to send reminder lead_id=%s label=%s: %s', lead_id, label, exc)
                break


async def main() -> None:
    validate_basic_config()
    ensure_headers()
    logger.info('Reminder worker started...')
    while True:
        try:
            await process_once()
        except Exception as exc:  # noqa: BLE001
            logger.exception('Reminder worker cycle failed: %s', exc)

        s = get_settings_cached(force=False)
        poll = _settings_int(s, 'poll_interval_seconds', POLL_INTERVAL_SECONDS)
        poll = max(5, poll)
        await asyncio.sleep(poll)


if __name__ == '__main__':
    asyncio.run(main())
