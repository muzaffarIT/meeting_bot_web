from __future__ import annotations

from html import escape
from datetime import date


BRAND_DIVIDER = '━━━━━━━━━━━━━━━'

_MONTHS = {
    'ru': ['', 'января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
           'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'],
    'uz': ['', 'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
           'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr'],
}
_WEEKDAYS = {
    'ru': ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'],
    'uz': ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba'],
}


def _fmt_date(raw: str, lang: str) -> str:
    """2026-08-20 -> «20 августа 2026, четверг» (или исходная строка при ошибке)."""
    raw = str(raw or '').strip()
    try:
        parts = raw.split('-')
        if len(parts) != 3:
            return raw
        d = date(int(parts[0]), int(parts[1]), int(parts[2]))
        months = _MONTHS.get(lang, _MONTHS['ru'])
        weekdays = _WEEKDAYS.get(lang, _WEEKDAYS['ru'])
        return f'{d.day} {months[d.month]} {d.year}, {weekdays[d.weekday()]}'
    except (ValueError, IndexError):
        return raw


def _brand_header(lang: str) -> str:
    if lang == 'uz':
        return '🎓 <b>NEWTON ACADEMY</b>\n<i>Rasmiy bot</i> ✅'
    return '🎓 <b>NEWTON ACADEMY</b>\n<i>Официальный бот</i> ✅'


def _first_name(parent_name: str) -> str:
    name = str(parent_name or '').strip()
    if not name:
        return ''
    return name.split()[0]


def _hello(lang: str, parent_name: str) -> str:
    first = escape(_first_name(parent_name))
    if lang == 'uz':
        return f'Assalomu alaykum, <b>{first}</b>!' if first else 'Assalomu alaykum!'
    return f'Здравствуйте, <b>{first}</b>!' if first else 'Здравствуйте!'


def choose_language_text() -> str:
    return (
        f'{_brand_header("ru")}\n'
        f'{BRAND_DIVIDER}\n\n'
        '👋 <b>Добро пожаловать!</b>\n\n'
        'Этот официальный бот Newton Academy поможет вам:\n'
        '  ✅ — подтвердить встречу\n'
        '  📍 — получить адрес и локацию\n'
        '  ⏰ — не пропустить встречу (напомним заранее)\n'
        '  💬 — связаться с менеджером\n\n'
        '🔐 <i>Это безопасно: мы никогда не просим номера карт, коды из SMS или пароли.</i>\n\n'
        '<b>🌐 Выберите язык / Tilni tanlang:</b>'
    )


def invalid_link_text() -> str:
    return (
        f'{_brand_header("ru")}\n'
        f'{BRAND_DIVIDER}\n\n'
        '😕 <b>Ссылка недействительна</b>\n\n'
        'Пожалуйста, откройте персональную ссылку, которую прислал вам менеджер Newton Academy.\n\n'
        'Если ссылка потерялась — просто попросите менеджера прислать её заново.'
    )


def lead_not_found_text() -> str:
    return (
        f'{_brand_header("ru")}\n'
        f'{BRAND_DIVIDER}\n\n'
        '😕 <b>Запись не найдена</b>\n\n'
        'Возможно, ссылка устарела. Пожалуйста, свяжитесь с вашим менеджером — он пришлёт новую персональную ссылку.'
    )


def preconfirm_text(lang: str, lead: dict | None = None) -> str:
    parent_name = str((lead or {}).get('parent_name', '') or '')
    date_ = _fmt_date((lead or {}).get('meeting_date', ''), lang)
    time_ = str((lead or {}).get('meeting_time', '') or '')

    meeting_lines = ''
    if date_ or time_:
        if lang == 'uz':
            meeting_lines = f'\n🗓 <b>Sana:</b> {escape(date_)}\n🕒 <b>Vaqt:</b> {escape(time_)}\n'
        else:
            meeting_lines = f'\n🗓 <b>Дата:</b> {escape(date_)}\n🕒 <b>Время:</b> {escape(time_)}\n'

    if lang == 'uz':
        return (
            f'{_brand_header(lang)}\n'
            f'{BRAND_DIVIDER}\n\n'
            f'{_hello(lang, parent_name)}\n'
            f'{meeting_lines}'
            '\n📌 Manzil, xarita va eslatmalarni olish uchun uchrashuvni tasdiqlang — pastdagi tugmani bosing.\n\n'
            '⏱ Bu atigi 5 soniya oladi ✨'
        )

    return (
        f'{_brand_header(lang)}\n'
        f'{BRAND_DIVIDER}\n\n'
        f'{_hello(lang, parent_name)}\n'
        f'{meeting_lines}'
        '\n📌 Чтобы получить адрес, карту и напоминания — подтвердите встречу, нажав кнопку ниже.\n\n'
        '⏱ Это займёт всего 5 секунд ✨'
    )


def confirmed_details_text(lead: dict, lang: str) -> str:
    date_ = _fmt_date(lead.get('meeting_date', ''), lang)
    time_ = lead.get('meeting_time', '')
    address = lead.get('address_text', '')

    if lang == 'uz':
        return (
            f'{_brand_header(lang)}\n'
            f'{BRAND_DIVIDER}\n\n'
            '✅ <b>Uchrashuv tasdiqlandi!</b>\n\n'
            'Sizni kutamiz:\n'
            f'🗓 <b>Sana:</b> {escape(str(date_))}\n'
            f'🕒 <b>Vaqt:</b> {escape(str(time_))}\n'
            f'📍 <b>Manzil:</b> {escape(str(address))}\n\n'
            '🚀 Uchrashuvga qadar eslatma yuboramiz — hech narsani unutmaysiz.\n\n'
            f'{BRAND_DIVIDER}\n'
            '📍 Quyidagi tugma orqali lokatsiyani olishingiz mumkin.'
        )

    return (
        f'{_brand_header(lang)}\n'
        f'{BRAND_DIVIDER}\n\n'
        '✅ <b>Встреча подтверждена!</b>\n\n'
        'Мы вас ждём:\n'
        f'🗓 <b>Дата:</b> {escape(str(date_))}\n'
        f'🕒 <b>Время:</b> {escape(str(time_))}\n'
        f'📍 <b>Адрес:</b> {escape(str(address))}\n\n'
        '🚀 Перед встречей мы пришлём напоминание — вы ничего не пропустите.\n\n'
        f'{BRAND_DIVIDER}\n'
        '📍 Нажмите кнопку ниже, чтобы получить локацию.'
    )


def reminder_text(lead: dict, lang: str, label: str, confirmed: bool) -> str:
    date_ = _fmt_date(lead.get('meeting_date', ''), lang)
    time_ = lead.get('meeting_time', '')
    address = lead.get('address_text', '')

    if lang == 'uz':
        tail = (
            f'{BRAND_DIVIDER}\n📍 Quyidagi tugma orqali lokatsiyani olishingiz mumkin.'
            if confirmed
            else '⚠️ Iltimos, uchrashuvni tasdiqlang — pastdagi tugmani bosing.'
        )
        return (
            f'{_brand_header(lang)}\n'
            f'{BRAND_DIVIDER}\n\n'
            f'⏰ <b>Eslatma:</b> uchrashuvga {escape(label)} qoldi\n\n'
            f'🗓 <b>Sana:</b> {escape(str(date_))}\n'
            f'🕒 <b>Vaqt:</b> {escape(str(time_))}\n'
            f'📍 <b>Manzil:</b> {escape(str(address))}\n\n'
            f'{tail}'
        )

    tail = (
        f'{BRAND_DIVIDER}\n📍 Нажмите кнопку ниже, чтобы получить локацию.'
        if confirmed
        else '⚠️ Пожалуйста, подтвердите встречу — нажмите кнопку ниже.'
    )
    return (
        f'{_brand_header(lang)}\n'
        f'{BRAND_DIVIDER}\n\n'
        f'⏰ <b>Напоминание:</b> до вашей встречи осталось {escape(label)}\n\n'
        f'🗓 <b>Дата:</b> {escape(str(date_))}\n'
        f'🕒 <b>Время:</b> {escape(str(time_))}\n'
        f'📍 <b>Адрес:</b> {escape(str(address))}\n\n'
        f'{tail}'
    )


def button_labels(lang: str) -> dict:
    if lang == "uz":
        return {
            "confirm": "✅ Uchrashuvni tasdiqlayman",
            "contact_tg": "💬 Menejer bilan bog'lanish",
            "contact_phone": "📞 Menejer bilan bog'lanish",
            "get_location": "📍 Lokatsiyani olish",
            "google_maps": "📍 Google Maps",
            "yandex_maps": "📍 Yandex Xaritalar",
        }

    return {
        "confirm": "✅ Подтверждаю встречу",
        "contact_tg": "💬 Связаться с менеджером",
        "contact_phone": "📞 Связаться с менеджером",
        "get_location": "📍 Получить локацию",
        "google_maps": "📍 Google Maps",
        "yandex_maps": "📍 Яндекс Карты",
    }
