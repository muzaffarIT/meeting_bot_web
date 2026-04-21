"""
fix_users.py — диагностика и исправление проблем с паролями пользователей.

Запустите в Railway Shell:
    python fix_users.py

Покажет список пользователей с проблемами и предложит сбросить пароли.
"""
from __future__ import annotations

from db_models import SessionLocal, User
from auth_utils import generate_salt, hash_password, verify_password


def main() -> None:
    db = SessionLocal()
    users = db.query(User).all()
    db.close()

    print(f"\n{'='*60}")
    print(f"  ДИАГНОСТИКА ПОЛЬЗОВАТЕЛЕЙ  ({len(users)} шт.)")
    print(f"{'='*60}")
    print(f"{'Логин':<20} {'Роль':<10} {'Активен':<10} {'Salt':<8} {'Hash':<8}")
    print(f"{'-'*60}")

    broken = []
    for u in users:
        has_salt = bool(u.salt and u.salt.strip())
        has_hash = bool(u.password_hash and u.password_hash.strip())
        salt_ok = '✅' if has_salt else '❌'
        hash_ok = '✅' if has_hash else '❌'
        print(f"{u.login:<20} {u.role:<10} {u.active:<10} {salt_ok:<8} {hash_ok:<8}")
        if not has_salt or not has_hash:
            broken.append(u.login)

    print(f"{'='*60}")

    if not broken:
        print("\n✅ Все пользователи имеют salt и password_hash.")
        print("   Возможная причина: логин хранится с заглавной буквой,")
        print("   а юзер вводит строчными. Этот баг уже исправлен в коде.")
        print("\n   Убедитесь что деплой с новым кодом прошёл!")
    else:
        print(f"\n❌ Найдено пользователей без пароля: {len(broken)}")
        print(f"   Логины: {', '.join(broken)}")
        print("\n   Чтобы сбросить пароль, запустите:")
        for login in broken:
            print(f"   python seed_users.py --login \"{login}\" --password НовыйПароль123")

    print(f"\n{'='*60}")
    print("  ТЕСТ ВХОДА")
    print(f"{'='*60}")
    test_login = input("\nВведите логин для теста (или Enter чтобы пропустить): ").strip()
    if not test_login:
        return

    import getpass
    test_pass = getpass.getpass(f"Пароль для '{test_login}': ")

    from db_services import find_user_by_login
    user = find_user_by_login(test_login)
    if not user:
        print(f"❌ Пользователь '{test_login}' не найден (даже без учёта регистра)!")
        # Show what we do find
        db = SessionLocal()
        from sqlalchemy import func
        results = db.query(User).filter(func.lower(User.login).contains(test_login.lower())).all()
        db.close()
        if results:
            print(f"   Похожие логины в БД: {[u.login for u in results]}")
        return

    print(f"✅ Пользователь найден: login={user['login']}, role={user['role']}, active={user['active']}")
    if not user.get('salt') or not user.get('password_hash'):
        print(f"❌ Пустой salt или hash — пользователь не может войти!")
        return

    if verify_password(test_pass, user['salt'], user['password_hash']):
        print(f"✅ Пароль верный! Вход работает.")
    else:
        print(f"❌ Пароль неверный!")


if __name__ == '__main__':
    main()
