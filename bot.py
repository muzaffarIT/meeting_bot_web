from __future__ import annotations
import logging
from datetime import datetime

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import (
    BOT_TOKEN,
    DEFAULT_BRANCH_LOCATION_GOOGLE_URL,
    DEFAULT_BRANCH_LOCATION_YANDEX_URL,
    validate_basic_config,
)
from constants import STATUS_BOT_STARTED, STATUS_CONFIRMED
from db_services import ensure_headers, find_lead_by_id, find_lead_by_tg_id, update_lead_fields, get_settings_cached, save_message
from texts import (
    choose_language_text,
    confirmed_details_text,
    invalid_link_text,
    lead_not_found_text,
    preconfirm_text,
    button_labels,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)



def contact_menu_text(lead: dict, lang: str) -> str:
    manager_name = str(lead.get("manager_name", "")).strip()
    manager_tg = str(lead.get("manager_telegram", "")).strip().lstrip("@")
    manager_phone = str(lead.get("manager_phone", "")).strip()

    if lang == "uz":
        lines = ["Menejer bilan bog‘lanish:"]
        if manager_name:
            lines.append(f"👤 Menejer: {manager_name}")
        if manager_phone:
            lines.append(f"📞 Telefon: {manager_phone}")
        if manager_tg:
            lines.append(f"💬 Telegram: @{manager_tg}")
        lines.append("")
        lines.append("Quyidagi usulni tanlang.")
        return "\n".join(lines)

    lines = ["Связь с менеджером:"]
    if manager_name:
        lines.append(f"👤 Менеджер: {manager_name}")
    if manager_phone:
        lines.append(f"📞 Телефон: {manager_phone}")
    if manager_tg:
        lines.append(f"💬 Telegram: @{manager_tg}")
    lines.append("")
    lines.append("Выберите способ связи ниже.")
    return "\n".join(lines)

def contact_menu_keyboard(lead: dict, lang: str) -> InlineKeyboardMarkup:
    lead_id = str(lead.get("lead_id", "")).strip()
    manager_tg = str(lead.get("manager_telegram", "")).strip().lstrip("@")

    rows = [
        [
            InlineKeyboardButton(
                "📞 Позвонить" if lang == "ru" else "📞 Qo‘ng‘iroq qilish",
                callback_data=f"show_phone:{lead_id}",
            )
        ]
    ]

    if manager_tg:
        rows.append([
            InlineKeyboardButton(
                "💬 Написать в Telegram" if lang == "ru" else "💬 Telegram’da yozish",
                url=f"https://t.me/{manager_tg}",
            )
        ])

    rows.append([
        InlineKeyboardButton(
            "⬅️ Назад" if lang == "ru" else "⬅️ Orqaga",
            callback_data=f"contact_back:{lead_id}",
        )
    ])

    return InlineKeyboardMarkup(rows)

def language_keyboard(lead_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("Русский", callback_data=f"lang:ru:{lead_id}"),
            InlineKeyboardButton("O'zbekcha", callback_data=f"lang:uz:{lead_id}"),
        ]
    ])


def preconfirm_keyboard(lead: dict, lang: str) -> InlineKeyboardMarkup:
    labels = button_labels(lang)
    lead_id = str(lead.get("lead_id", "")).strip()

    rows = [
        [InlineKeyboardButton(labels["confirm"], callback_data=f"confirm:{lead_id}")]
    ]

    rows.append([
        InlineKeyboardButton(
            labels["contact_phone"],
            callback_data=f"contact:{lead_id}"
        )
    ])

    return InlineKeyboardMarkup(rows)

def reminder_keyboard(lead: dict, confirmed: bool, lang: str) -> InlineKeyboardMarkup | None:
    labels = button_labels(lang)
    lead_id = str(lead.get("lead_id", "")).strip()
    rows = []

    s = get_settings_cached(force=False)
    google_url = str(s.get('location_google_url') or DEFAULT_BRANCH_LOCATION_GOOGLE_URL or '').strip()
    yandex_url = str(s.get('location_yandex_url') or DEFAULT_BRANCH_LOCATION_YANDEX_URL or '').strip()

    if not confirmed:
        rows.append([
            InlineKeyboardButton(labels["confirm"], callback_data=f"confirm:{lead_id}")
        ])

    if confirmed:
        if google_url:
            rows.append([
                InlineKeyboardButton(labels.get('google_maps', '📍 Google Maps'), url=google_url)
            ])

        if yandex_url:
            rows.append([
                InlineKeyboardButton(labels.get('yandex_maps', '📍 Яндекс Карты'), url=yandex_url)
            ])

    rows.append([
        InlineKeyboardButton(
            labels.get('contact_phone', '📞 Связаться с менеджером'),
            callback_data=f"contact:{lead_id}"
        )
    ])

    return InlineKeyboardMarkup(rows) if rows else None


def lead_with_settings(lead: dict) -> dict:
    """Overlay settings onto lead so updates affect existing leads too."""
    s = get_settings_cached(force=False)
    out = dict(lead)

    branch_name = str(s.get('branch_name') or '').strip()
    branch_address = str(s.get('branch_address') or '').strip()
    if branch_name:
        out['branch_name'] = branch_name
    if branch_address:
        out['address_text'] = branch_address

    return out

async def handle_contact_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await safe_answer_callback(query)

    _, lead_id = query.data.split(":", 1)
    lead = find_lead_by_id(lead_id)

    if not lead:
        await safe_edit_message(query, "Запись не найдена.")
        return

    lang = str(lead.get("language", "ru")).strip() or "ru"

    await safe_edit_message(
        query,
        contact_menu_text(lead, lang),
        reply_markup=contact_menu_keyboard(lead, lang),
    )
    
async def handle_contact_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await safe_answer_callback(query)

    _, lead_id = query.data.split(":", 1)
    lead = find_lead_by_id(lead_id)

    if not lead:
        await safe_edit_message(query, "Запись не найдена.")
        return

    lang = str(lead.get("language", "ru")).strip() or "ru"
    confirmed = str(lead.get("confirmed", "")).strip().upper() in {"YES", "TRUE", "1", "ДА"}

    if confirmed:
        await safe_edit_message(
            query,
            confirmed_details_text(lead, lang),
            reply_markup=reminder_keyboard(lead, confirmed=True, lang=lang),
        )
    else:
        await safe_edit_message(
            query,
            preconfirm_text(lang),
            reply_markup=preconfirm_keyboard(lead, lang),
        )

async def handle_show_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await safe_answer_callback(query)

    _, lead_id = query.data.split(":", 1)
    lead = find_lead_by_id(lead_id)

    if not lead:
        await safe_edit_message(query, "Запись не найдена.")
        return

    lang = str(lead.get("language", "ru")).strip() or "ru"
    manager_phone = str(lead.get("manager_phone", "")).strip()

    text = (
        f"📞 Номер менеджера: {manager_phone}\n\nПозвоните по этому номеру."
        if lang == "ru"
        else f"📞 Menejer raqami: {manager_phone}\n\nShu raqamga qo‘ng‘iroq qiling."
    )

    await safe_edit_message(
        query,
        text,
        reply_markup=contact_menu_keyboard(lead, lang),
    )

async def safe_answer_callback(query) -> None:
    try:
        await query.answer()
    except BadRequest as e:
        text = str(e)
        if "Query is too old" in text or "query id is invalid" in text:
            return
        raise


async def safe_edit_message(query, text: str, reply_markup=None) -> None:
    try:
        await query.edit_message_text(
            text=text,
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return
        raise


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return

    args = context.args
    if not args:
        await update.message.reply_text(invalid_link_text(), parse_mode='HTML')
        return

    lead_id = args[0].strip()
    lead = find_lead_by_id(lead_id)

    if not lead:
        await update.message.reply_text(lead_not_found_text(), parse_mode='HTML')
        return

    # apply settings (branch name/address) so UI changes affect existing leads too
    lead = lead_with_settings(lead)

    user = update.effective_user

    update_lead_fields(
        lead_id,
        {
            "telegram_user_id": str(user.id),
            "telegram_username": user.username or "",
            "bot_started": "ДА",
            "status": STATUS_BOT_STARTED,
        },
    )

    await update.message.reply_text(
        choose_language_text(),
        reply_markup=language_keyboard(lead_id),
        parse_mode='HTML'
    )


async def handle_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await safe_answer_callback(query)

    _, lang, lead_id = query.data.split(":", 2)
    lead = find_lead_by_id(lead_id)

    if not lead:
        await safe_edit_message(query, "Запись не найдена.")
        return

    update_lead_fields(lead_id, {"language": lang})

    # НЕ делаем повторный запрос в таблицу
    lead["language"] = lang

    await safe_edit_message(
        query,
        preconfirm_text(lang),
        reply_markup=preconfirm_keyboard(lead, lang),
    )

async def handle_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return

    await safe_answer_callback(query)

    _, lead_id = query.data.split(":", 1)
    lead = find_lead_by_id(lead_id)

    if not lead:
        await safe_edit_message(query, "Запись не найдена.")
        return

    lead = lead_with_settings(lead)

    lang = str(lead.get("language", "ru")).strip() or "ru"
    already_confirmed = str(lead.get("confirmed", "")).strip().upper() in {"YES", "TRUE", "1", "ДА"}

    if not already_confirmed:
        update_lead_fields(
            lead_id,
            {
                "confirmed": "ДА",
                "confirmed_at": datetime.now().isoformat(timespec="seconds"),
                "status": STATUS_CONFIRMED,
            },
        )
        lead["confirmed"] = "ДА"
        lead["status"] = STATUS_CONFIRMED

    await safe_edit_message(
        query,
        confirmed_details_text(lead, lang),
        reply_markup=reminder_keyboard(lead, confirmed=True, lang=lang),
    )


async def handle_incoming_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle any text message from client - save to messages DB."""
    if not update.message or not update.effective_user:
        return
    tg_id = str(update.effective_user.id)
    text = update.message.text or ''
    if not text:
        return

    # Find which lead this user belongs to
    lead = find_lead_by_tg_id(tg_id)
    if not lead:
        return  # unknown user, ignore

    client_name = str(lead.get('parent_name', '') or update.effective_user.full_name or '').strip()
    save_message(
        lead_id=lead['lead_id'],
        direction='in',
        sender=client_name or 'Клиент',
        text=text,
    )
    logger.info('Saved incoming message from lead_id=%s', lead['lead_id'])

    # Send acknowledgement to client
    lang = str(lead.get('language', 'ru')).strip() or 'ru'
    ack = "Ваше сообщение получено. Менеджер ответит вам в ближайшее время." if lang != 'uz' \
        else "Xabaringiz qabul qilindi. Menejer tez orada javob beradi."
    await update.message.reply_text(ack, parse_mode='HTML')


def main() -> None:
    validate_basic_config()
    ensure_headers()

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_language, pattern=r"^lang:"))
    app.add_handler(CallbackQueryHandler(handle_confirm, pattern=r"^confirm:"))
    app.add_handler(CallbackQueryHandler(handle_contact_menu, pattern=r"^contact:"))
    app.add_handler(CallbackQueryHandler(handle_contact_back, pattern=r"^contact_back:"))
    app.add_handler(CallbackQueryHandler(handle_show_phone, pattern=r"^show_phone:"))
    # Handle any plain text from client (for two-way chat)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_incoming_text))

    logger.info("Bot is running...")
    app.run_polling(drop_pending_updates=True)

    
if __name__ == "__main__":
    main()