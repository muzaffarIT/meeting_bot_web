from __future__ import annotations

HEADERS_LEADS = [
    'ID лида',
    'Дата создания',
    'Логин менеджера',
    'Имя менеджера',
    'Телефон менеджера',
    'Telegram менеджера',
    'ФИО родителя',
    'Телефон родителя',
    'Язык',
    'Дата встречи',
    'Время встречи',
    'Дата-время встречи ISO',
    'Название филиала',
    'Адрес филиала',
    'Ссылка на локацию',
    'Статус',
    'Telegram user id родителя',
    'Telegram username родителя',
    'Бот запущен',
    'Подтверждено',
    'Время подтверждения',
    'Напоминание 3 дня',
    'Напоминание 1 день',
    'Напоминание 6 часов',
    'Напоминание 3 часа',
    'Напоминание 2 часа',
    'Пришел',
    'Купил',
    'Заметки',
]

HEADERS_USERS = [
    'Логин',
    'ФИО',
    'Роль',
    'Телефон',
    'Telegram',
    'Активен',
    'Salt',
    'Хэш пароля',
    'Дата создания',
]

ROLE_MANAGER = 'manager'
ROLE_ADMIN = 'admin'
ROLE_OWNER = 'owner'

STATUS_NEW = 'NEW'
STATUS_LINK_SENT = 'LINK_SENT'
STATUS_BOT_STARTED = 'BOT_STARTED'
STATUS_CONFIRMED = 'CONFIRMED'
STATUS_RESCHEDULED = 'RESCHEDULED'
STATUS_ARRIVED = 'ARRIVED'
STATUS_NO_SHOW = 'NO_SHOW'
STATUS_BOUGHT = 'BOUGHT'
STATUS_LOST = 'LOST'

STATUS_CHOICES = [
    STATUS_NEW,
    STATUS_LINK_SENT,
    STATUS_BOT_STARTED,
    STATUS_CONFIRMED,
    STATUS_RESCHEDULED,
    STATUS_ARRIVED,
    STATUS_NO_SHOW,
    STATUS_BOUGHT,
    STATUS_LOST,
]
STATUS_LABELS = {
    'NEW': 'Новый',
    'LINK_SENT': 'Ссылка отправлена',
    'BOT_STARTED': 'Бот запущен',
    'CONFIRMED': 'Подтверждено',
    'RESCHEDULED': 'Перенесено',
    'ARRIVED': 'Пришел',
    'NO_SHOW': 'Не пришел',
    'BOUGHT': 'Купил',
    'LOST': 'Потерян',
}

HEADER_MAP_LEADS = {
    'lead_id': 'ID лида',
    'created_at': 'Дата создания',
    'manager_login': 'Логин менеджера',
    'manager_name': 'Имя менеджера',
    'manager_phone': 'Телефон менеджера',
    'manager_telegram': 'Telegram менеджера',
    'parent_name': 'ФИО родителя',
    'parent_phone': 'Телефон родителя',
    'language': 'Язык',
    'meeting_date': 'Дата встречи',
    'meeting_time': 'Время встречи',
    'meeting_datetime_iso': 'Дата-время встречи ISO',
    'branch_name': 'Название филиала',
    'address_text': 'Адрес филиала',
    'location_url': 'Ссылка на локацию',
    'status': 'Статус',
    'telegram_user_id': 'Telegram user id родителя',
    'telegram_username': 'Telegram username родителя',
    'bot_started': 'Бот запущен',
    'confirmed': 'Подтверждено',
    'confirmed_at': 'Время подтверждения',
    'remind_3d_sent': 'Напоминание 3 дня',
    'remind_1d_sent': 'Напоминание 1 день',
    'remind_6h_sent': 'Напоминание 6 часов',
    'remind_3h_sent': 'Напоминание 3 часа',
    'remind_2h_sent': 'Напоминание 2 часа',
    'arrived': 'Пришел',
    'bought': 'Купил',
    'notes': 'Заметки',
}

HEADER_MAP_USERS = {
    'login': 'Логин',
    'full_name': 'ФИО',
    'role': 'Роль',
    'phone': 'Телефон',
    'telegram': 'Telegram',
    'active': 'Активен',
    'salt': 'Salt',
    'password_hash': 'Хэш пароля',
    'created_at': 'Дата создания',
}

HEADERS_SETTINGS = ['Key', 'Value']
# =========================
# SETTINGS (лист settings)
# =========================

HEADERS_SETTINGS = [
    "Ключ",
    "Значение",
]

# python_name -> sheet_column_title
HEADER_MAP_SETTINGS = {
    "key": "Ключ",
    "value": "Значение",
}

DEFAULT_SETTINGS = {
    # филиал
    "branch_name": "Newton Academy",
    "branch_address": "",
    "location_google_url": "",
    "location_yandex_url": "",

    # напоминания
    "remind_3d_enabled": "ДА",
    "remind_3d_hours": "72",

    "remind_1d_enabled": "ДА",
    "remind_1d_hours": "24",

    "remind_6h_enabled": "ДА",
    "remind_6h_hours": "6",

    "remind_3h_enabled": "ДА",
    "remind_3h_hours": "3",

    "remind_2h_enabled": "ДА",
    "remind_2h_hours": "2",

    # воркер
    "poll_interval_seconds": "60",
}