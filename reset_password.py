"""
reset_password.py — сброс пароля пользователя.

Использование:
    python reset_password.py                         # интерактивный режим
    python reset_password.py --login admin --password NewPass123
"""
from __future__ import annotations

import argparse
import sys

from auth_utils import generate_salt, hash_password
from db_services import find_user_by_login, update_user_fields


def reset(login: str, new_password: str) -> None:
    user = find_user_by_login(login)
    if not user:
        print(f"❌ Пользователь '{login}' не найден в БД.")
        sys.exit(1)

    salt = generate_salt()
    password_hash = hash_password(new_password, salt)
    ok = update_user_fields(login, {'salt': salt, 'password_hash': password_hash})
    if ok:
        print(f"✅ Пароль для '{login}' успешно обновлён.")
    else:
        print(f"❌ Не удалось обновить пароль для '{login}'.")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description='Сброс пароля пользователя')
    parser.add_argument('--login', help='Логин пользователя')
    parser.add_argument('--password', help='Новый пароль')
    args = parser.parse_args()

    if args.login and args.password:
        reset(args.login, args.password)
    else:
        import getpass
        login = input("Логин: ").strip()
        if not login:
            print("❌ Логин не может быть пустым.")
            sys.exit(1)
        new_pass = getpass.getpass("Новый пароль: ")
        confirm = getpass.getpass("Повторите пароль: ")
        if new_pass != confirm:
            print("❌ Пароли не совпадают.")
            sys.exit(1)
        reset(login, new_pass)


if __name__ == '__main__':
    main()