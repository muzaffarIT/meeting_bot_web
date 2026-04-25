from __future__ import annotations


def choose_language_text() -> str:
    return 'Выберите язык / Tilni tanlang'


def invalid_link_text() -> str:
    return 'Ссылка недействительна. Пожалуйста, используйте персональную ссылку от менеджера.'


def lead_not_found_text() -> str:
    return 'Запись не найдена. Пожалуйста, свяжитесь с менеджером.'


def preconfirm_text(lang: str) -> str:
    if lang == 'uz':
        return (
            "Siz Newton Academy konsultatsiyasiga yozilgansiz.\n\n"
            '📌 Manzil va uchrashuv tafsilotlarini olish uchun avval uchrashuvni tasdiqlang.'
        )
    return (
        'Вы записаны на консультацию в Newton Academy.\n\n'
        '📌 Чтобы получить адрес и детали встречи, сначала подтвердите встречу.'
    )


def confirmed_details_text(lead: dict, lang: str) -> str:
    date_ = lead.get('meeting_date', '')
    time_ = lead.get('meeting_time', '')
    address = lead.get('address_text', '')

    if lang == 'uz':
        return (
            '✅ Rahmat, uchrashuv tasdiqlandi.\n\n'
            f'📍 Manzil: {address}\n'
            f'📅 Sana: {date_}\n'
            f'🕒 Vaqt: {time_}\n\n'
            '—————————————\n'
            '📍 Lokatsiyani olish uchun quyidagi tugmani bosing.'
        )

    return (
        '✅ Спасибо, встреча подтверждена.\n\n'
        f'📍 Адрес: {address}\n'
        f'📅 Дата: {date_}\n'
        f'🕒 Время: {time_}\n\n'
        '—————————————\n'
        '📍 Чтобы получить локацию, нажмите кнопку ниже.'
    )


def reminder_text(lead: dict, lang: str, label: str, confirmed: bool) -> str:
    date_ = lead.get('meeting_date', '')
    time_ = lead.get('meeting_time', '')
    address = lead.get('address_text', '')

    if lang == 'uz':
        tail = (
            '—————————————\n📍 Lokatsiyani olish uchun quyidagi tugmani bosing.'
            if confirmed
            else 'Iltimos, uchrashuvni tasdiqlang.'
        )
        return (
            f"⏰ Eslatma: uchrashuvgacha {label} qoldi.\n\n"
            f'📍 Manzil: {address}\n'
            f'📅 Sana: {date_}\n'
            f'🕒 Vaqt: {time_}\n\n'
            f'{tail}'
        )

    tail = (
        '—————————————\n📍 Чтобы получить локацию, нажмите кнопку ниже.'
        if confirmed
        else 'Пожалуйста, подтвердите встречу.'
    )

    return (
        f'⏰ Напоминание: до вашей встречи осталось {label}.\n\n'
        f'📍 Адрес: {address}\n'
        f'📅 Дата: {date_}\n'
        f'🕒 Время: {time_}\n\n'
        f'{tail}'
    )

def button_labels(lang: str) -> dict:
    if lang == "uz":
        return {
            "confirm": "✅ Uchrashuvni tasdiqlayman",
            "contact_tg": "💬 Menejer bilan bog‘lanish",
            "contact_phone": "📞 Menejer bilan bog‘lanish",
            "get_location": "📍 Lokatsiyani olish",
        }

    return {
        "confirm": "✅ Подтверждаю встречу",
        "contact_tg": "💬 Связаться с менеджером",
        "contact_phone": "📞 Связаться с менеджером",
        "get_location": "📍 Получить локацию",
    }