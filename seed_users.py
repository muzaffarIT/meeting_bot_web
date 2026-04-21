"""
seed_users.py — создание или сброс пароля пользователя напрямую в БД.

Использование (интерактивно):
    python seed_users.py

Или аргументами (удобно для Railway одноразовых команд):
    python seed_users.py --login admin --password MyPass123 --role owner --name "Администратор"
"""
from __future__ import annotations

import argparse
import sys

from auth_utils import generate_salt, hash_password
from db_models import SessionLocal, User
from utils import now_local


def create_or_update_user(login: str, password: str, role: str, full_name: str, phone: str = '', telegram: str = '') -> None:
    salt = generate_salt()
    pw_hash = hash_password(password, salt)

    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.login == login.strip().lower()).first()
        if existing:
            existing.salt = salt
            existing.password_hash = pw_hash
            existing.role = role
            existing.full_name = full_name
            existing.active = 'ДА'
            if phone:
                existing.phone = phone
            if telegram:
                existing.telegram = telegram.lstrip('@')
            db.commit()
            print(f"✅ Пользователь '{login}' обновлён. Пароль сброшен.")
        else:
            user = User(
                login=login.strip().lower(),
                full_name=full_name,
                role=role,
                phone=phone,
                telegram=telegram.lstrip('@'),
                active='ДА',
                salt=salt,
                password_hash=pw_hash,
                created_at=now_local().isoformat(timespec='seconds'),
            )
            db.add(user)
            db.commit()
            print(f"✅ Пользователь '{login}' создан.")
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка: {e}")
        sys.exit(1)
    finally:
        db.close()


def interactive_mode() -> None:
    print("=== Создание / сброс пользователя в БД ===")
    login = input("Логин: ").strip().lower()
    if not login:
        print("❌ Логин не может быть пустым.")
        sys.exit(1)

    full_name = input("ФИО (необязательно): ").strip() or login
    role = input("Роль [manager/admin/owner] (по умолчанию: owner): ").strip() or 'owner'
    if role not in ('manager', 'admin', 'owner'):
        print(f"❌ Недопустимая роль: {role}")
        sys.exit(1)

    import getpass
    password = getpass.getpass("Пароль: ")
    password2 = getpass.getpass("Повторите пароль: ")
    if password != password2:
        print("❌ Пароли не совпадают.")
        sys.exit(1)
    if len(password) < 6:
        print("❌ Пароль должен быть не менее 6 символов.")
        sys.exit(1)

    create_or_update_user(login=login, password=password, role=role, full_name=full_name)


def main() -> None:
    parser = argparse.ArgumentParser(description='Создание/сброс пользователя напрямую в БД')
    parser.add_argument('--login', help='Логин пользователя')
    parser.add_argument('--password', help='Пароль')
    parser.add_argument('--role', default='owner', help='Роль: manager/admin/owner')
    parser.add_argument('--name', default='', help='ФИО')
    parser.add_argument('--phone', default='', help='Телефон')
    parser.add_argument('--telegram', default='', help='Telegram username')

    args = parser.parse_args()

    if args.login and args.password:
        # Non-interactive mode
        full_name = args.name or args.login
        create_or_update_user(
            login=args.login,
            password=args.password,
            role=args.role,
            full_name=full_name,
            phone=args.phone,
            telegram=args.telegram,
        )
    else:
        interactive_mode()


if __name__ == '__main__':
    main()
