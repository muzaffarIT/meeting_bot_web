from __future__ import annotations

from getpass import getpass

from auth_utils import generate_salt, hash_password
from db_services import append_user_dict, ensure_headers, find_user_by_login
from utils import now_local


def main() -> None:
    ensure_headers()
    login = input('Логин: ').strip()
    if not login:
        raise SystemExit('Логин обязателен')
    if find_user_by_login(login):
        raise SystemExit('Пользователь уже существует')
    full_name = input('ФИО: ').strip()
    role = input('Роль (manager/admin/owner): ').strip() or 'manager'
    phone = input('Телефон: ').strip()
    telegram = input('Telegram username без @ (необязательно): ').strip()
    password = getpass('Пароль: ')
    password2 = getpass('Повторите пароль: ')
    if password != password2:
        raise SystemExit('Пароли не совпадают')

    salt = generate_salt()
    password_hash = hash_password(password, salt)
    append_user_dict(
        {
            'login': login,
            'full_name': full_name,
            'role': role,
            'phone': phone,
            'telegram': telegram,
            'active': 'ДА',
            'salt': salt,
            'password_hash': password_hash,
            'created_at': now_local().isoformat(timespec='seconds'),
        }
    )
    print(f'Пользователь {login} создан.')


if __name__ == '__main__':
    main()
