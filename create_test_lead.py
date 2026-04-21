from __future__ import annotations

from telegram.helpers import create_deep_linked_url

from config import (
    BOT_USERNAME,
    DEFAULT_BRANCH_ADDRESS,
    DEFAULT_BRANCH_LOCATION_GOOGLE_URL,
    DEFAULT_BRANCH_NAME,
)
from constants import STATUS_LINK_SENT
from db_services import append_lead_dict, ensure_headers, find_user_by_login
from utils import make_lead_id, now_local


def main() -> None:
    ensure_headers()
    manager_login = input('Логин менеджера для тестового лида: ').strip()
    manager = find_user_by_login(manager_login)
    if not manager:
        raise SystemExit('Менеджер не найден. Сначала создай пользователя через create_user.py')

    lead_id = make_lead_id()
    append_lead_dict(
        {
            'lead_id': lead_id,
            'created_at': now_local().isoformat(timespec='seconds'),
            'manager_login': manager_login,
            'manager_name': manager.get('full_name', ''),
            'manager_phone': manager.get('phone', ''),
            'manager_telegram': manager.get('telegram', ''),
            'parent_name': 'Тестовый родитель',
            'parent_phone': '+998900000000',
            'language': 'ru',
            'meeting_date': '2026-03-01',
            'meeting_time': '18:00',
            'meeting_datetime_iso': '2026-03-01T18:00:00+05:00',
            'branch_name': DEFAULT_BRANCH_NAME,
            'address_text': DEFAULT_BRANCH_ADDRESS,
            "location_url": DEFAULT_BRANCH_LOCATION_GOOGLE_URL,
            'status': STATUS_LINK_SENT,
            'telegram_user_id': '',
            'telegram_username': '',
            'bot_started': 'НЕТ',
            'confirmed': 'НЕТ',
            'confirmed_at': '',
            'remind_3d_sent': 'НЕТ',
            'remind_1d_sent': 'НЕТ',
            'remind_6h_sent': 'НЕТ',
            'remind_3h_sent': 'НЕТ',
            'remind_2h_sent': 'НЕТ',
            'arrived': 'НЕТ',
            'bought': 'НЕТ',
            'notes': 'Тестовая запись',
        }
    )
    print('Тестовый лид создан:')
    print(create_deep_linked_url(BOT_USERNAME, lead_id))


if __name__ == '__main__':
    main()
