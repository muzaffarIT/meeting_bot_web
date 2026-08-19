"""
replace_managers.py — удаление старых менеджеров и создание нового состава.

Режимы:
    python replace_managers.py --list     # только показать текущее состояние (ничего не меняет)
    python replace_managers.py            # dry-run: что будет удалено и создано
    python replace_managers.py --apply    # применить изменения

Удаляются только пользователи с ролью manager. Аккаунты admin/owner не трогаются.
Лиды не удаляются: в строке лида менеджер сохранён отдельными полями
(manager_name / manager_phone / manager_telegram), поэтому история остаётся читаемой.
"""
from __future__ import annotations

import argparse
import secrets
import sys

from auth_utils import generate_salt, hash_password
from constants import ROLE_MANAGER
from db_models import SessionLocal, Lead, User
from utils import now_local

# (логин, ФИО, telegram, телефон)
NEW_MANAGERS: list[tuple[str, str, str, str]] = [
    ('hurliqo',  'Хурлико',   'newtonacademyuz',       '+998998120233'),
    ('ziyodilla', 'Зиёдилла',  'newton_uzb',            '+998871352505'),
    ('mirahmad', 'Мирахмад',  'aa774k',                '+998503016688'),
    ('jasur',    'Жасур',     'Jasur_newton',          '+998939234232'),
    ('diyora',   'Диёра',     'newton_diyora',         '+998946594008'),
    ('zufar',    'Зуфар',     'Newton_Y',              '+998883330511'),
    ('sevinch',  'Севинч',    'Newton_academySevinch', '+998777144785'),
    ('behruz',   'Бехруз',    'bexruz_newton',         ''),
    ('uktamjon', 'Уктамжон',  'NewtonUk69',            '+998771825908'),
    ('hilola',   'Хилола',    'hilolanewton',          '+998700411363'),
    ('gozal',    'Гозаль',    'newton_academy_g',      ''),
    ('sunnat',   'Суннат',    'Sunnat06I',             '+998777242541'),
    ('nilufar',  'Нилюфар',   'nil_0403',              '+998947438082'),
]

# Без похожих друг на друга символов (0/O, 1/l/I), чтобы пароль можно было продиктовать
_ALPHABET = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def make_password(length: int = 10) -> str:
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))


def fetch_state() -> tuple[list[User], dict[str, int]]:
    db = SessionLocal()
    try:
        users = db.query(User).all()
        counts: dict[str, int] = {}
        for lead in db.query(Lead).all():
            key = str(lead.manager_login or '').strip().lower()
            counts[key] = counts.get(key, 0) + 1
        db.expunge_all()
        return users, counts
    finally:
        db.close()


def print_state() -> None:
    users, counts = fetch_state()
    print(f'Всего пользователей в базе: {len(users)}\n')
    for u in sorted(users, key=lambda x: (str(x.role or ''), str(x.login or ''))):
        login = str(u.login or '')
        n = counts.get(login.strip().lower(), 0)
        print(
            f'  {login:<20} роль={str(u.role or ""):<8} '
            f'ФИО={str(u.full_name or ""):<20} tg={str(u.telegram or ""):<22} '
            f'тел={str(u.phone or ""):<15} активен={str(u.active or ""):<4} лидов={n}'
        )
    orphan = {k: v for k, v in counts.items() if k and k not in {str(u.login or "").strip().lower() for u in users}}
    if orphan:
        print('\n  Лиды с логином менеджера, которого уже нет в базе:')
        for k, v in sorted(orphan.items()):
            print(f'    {k:<20} лидов={v}')
    total_leads = sum(counts.values())
    print(f'\nВсего лидов: {total_leads}')


def replace(apply: bool) -> None:
    users, counts = fetch_state()

    to_delete = [u for u in users if str(u.role or '').strip().lower() == ROLE_MANAGER]
    keep = [u for u in users if u not in to_delete]

    print('=== БУДУТ УДАЛЕНЫ (роль manager) ===')
    if not to_delete:
        print('  — нет менеджеров в базе')
    for u in to_delete:
        n = counts.get(str(u.login or '').strip().lower(), 0)
        print(f'  {str(u.login or ""):<20} {str(u.full_name or ""):<20} лидов останется без владельца: {n}')

    print('\n=== ОСТАНУТСЯ БЕЗ ИЗМЕНЕНИЙ (admin / owner) ===')
    for u in keep:
        print(f'  {str(u.login or ""):<20} роль={str(u.role or "")}')

    print('\n=== БУДУТ СОЗДАНЫ (роль manager) ===')
    for login, name, tg, phone in NEW_MANAGERS:
        print(f'  {login:<12} {name:<12} @{tg:<24} {phone or "— телефон не указан"}')

    if not apply:
        print('\nЭто dry-run, база не тронута. Для применения: --apply')
        return

    credentials: list[tuple[str, str, str]] = []
    db = SessionLocal()
    try:
        delete_logins = [str(u.login) for u in to_delete]
        if delete_logins:
            db.query(User).filter(User.login.in_(delete_logins)).delete(synchronize_session=False)

        now_iso = now_local().isoformat(timespec='seconds')
        for login, name, tg, phone in NEW_MANAGERS:
            password = make_password()
            salt = generate_salt()
            db.add(User(
                login=login,
                full_name=name,
                role=ROLE_MANAGER,
                phone=phone,
                telegram=tg,
                active='ДА',
                salt=salt,
                password_hash=hash_password(password, salt),
                created_at=now_iso,
            ))
            credentials.append((login, name, password))

        db.commit()
    except Exception as e:
        db.rollback()
        print(f'\n❌ Ошибка, изменения откачены: {e}')
        sys.exit(1)
    finally:
        db.close()

    print(f'\n✅ Удалено менеджеров: {len(to_delete)}. Создано: {len(NEW_MANAGERS)}.')
    print('\n=== ЛОГИНЫ И ПАРОЛИ (сохрани, повторно пароль не показать) ===')
    for login, name, password in credentials:
        print(f'  {name:<12} логин: {login:<12} пароль: {password}')

    sync_sheet(delete_logins=[str(u.login) for u in to_delete])


def sync_sheet(delete_logins: list[str]) -> None:
    """Убирает старых менеджеров из листа users в Google Sheets и дописывает новых.

    Это важно: при пустой базе приложение на старте восстанавливает пользователей
    из Google Sheets (см. startup_event в app.py), и старые менеджеры вернулись бы.
    """
    try:
        import sheets
        from constants import HEADERS_USERS

        ws = sheets.get_or_create_worksheet('users')
        values = ws.get_all_values()
        needles = {l.strip().lower() for l in delete_logins}
        # снизу вверх, чтобы не съезжали индексы
        removed = 0
        for idx in range(len(values), 1, -1):
            row = values[idx - 1]
            if row and str(row[0]).strip().lower() in needles:
                ws.delete_rows(idx)
                removed += 1

        db = SessionLocal()
        try:
            fresh = {str(u.login): u for u in db.query(User).filter(
                User.login.in_([m[0] for m in NEW_MANAGERS])
            ).all()}
        finally:
            db.close()

        rows = []
        for login, _name, _tg, _phone in NEW_MANAGERS:
            u = fresh.get(login)
            if not u:
                continue
            rows.append([
                u.login, u.full_name, u.role, u.phone, u.telegram,
                u.active, u.salt, u.password_hash, u.created_at,
            ])
        if rows:
            ws.append_rows(rows, value_input_option='RAW')

        sheets._USERS_CACHE['ts'] = 0
        print(f'\n✅ Google Sheets: удалено строк {removed}, добавлено {len(rows)}.')
    except Exception as e:
        print(f'\n⚠️  Google Sheets не синхронизирован ({e}). База обновлена корректно.')
        print(f'   Проверь лист users вручную: {HEADERS_USERS[0]} — старые менеджеры должны быть удалены.')


def main() -> None:
    parser = argparse.ArgumentParser(description='Замена состава менеджеров')
    parser.add_argument('--list', action='store_true', help='только показать текущее состояние')
    parser.add_argument('--apply', action='store_true', help='применить изменения')
    args = parser.parse_args()

    if args.list:
        print_state()
        return

    replace(apply=args.apply)


if __name__ == '__main__':
    main()
