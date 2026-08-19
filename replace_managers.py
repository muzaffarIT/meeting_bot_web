"""
replace_managers.py — обновление состава менеджеров.

Режимы:
    python replace_managers.py --list     # показать текущее состояние (ничего не меняет)
    python replace_managers.py            # dry-run: что будет изменено
    python replace_managers.py --apply    # применить изменения

Что делает --apply:
  1. Менеджерам, которых нет в новом составе, ставит Активен = НЕТ.
     Они не смогут войти в панель и исчезнут из списка выбора менеджера,
     но их лиды остаются привязанными и видны в статистике.
  2. Менеджерам из нового состава, у которых уже есть аккаунт, обновляет
     ФИО / telegram / телефон. Логин и пароль не трогает — история лидов цела,
     людям не нужно заново входить.
  3. Создаёт аккаунты тем, кого в базе не было, и печатает их пароли.
  4. Переписывает лист users в Google Sheets по состоянию базы.

Аккаунты admin / owner не затрагиваются.
"""
from __future__ import annotations

import argparse
import secrets
import sys

from auth_utils import generate_salt, hash_password
from constants import HEADERS_USERS, ROLE_MANAGER
from db_models import SessionLocal, Lead, User
from utils import now_local

# (логин, ФИО, telegram, телефон, логин существующего аккаунта или None)
NEW_MANAGERS: list[tuple[str, str, str, str, str | None]] = [
    ('hurliqo',  'Хурлико',  'newtonacademyuz',       '+998998120233', 'Hurliqo'),
    ('ziyodilla', 'Зиёдилла', 'newton_uzb',           '+998871352505', 'Ziyod'),
    ('mirahmad', 'Мирахмад', 'aa774k',                '+998503016688', None),
    ('jasur',    'Жасур',    'Jasur_newton',          '+998939234232', None),
    ('diyora',   'Диёра',    'newton_diyora',         '+998946594008', None),
    ('zufar',    'Зуфар',    'Newton_Y',              '+998883330511', 'zufar'),
    ('sevinch',  'Севинч',   'Newton_academySevinch', '+998777144785', None),
    ('behruz',   'Бехруз',   'bexruz_newton',         '',              'behruz'),
    ('uktamjon', 'Уктамжон', 'NewtonUk69',            '+998771825908', None),
    ('hilola',   'Хилола',   'hilolanewton',          '+998700411363', 'Hilola'),
    ('gozal',    'Гозаль',   'newton_academy_g',      '',              'Gozal'),
    ('sunnat',   'Суннат',   'Sunnat06I',             '+998777242541', 'Sunnat'),
    ('nilufar',  'Нилюфар',  'nil_0403',              '+998947438082', None),
]

# Без похожих символов (0/O, 1/l/I), чтобы пароль можно было продиктовать голосом
_ALPHABET = 'abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def make_password(length: int = 10) -> str:
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))


def lead_counts() -> dict[str, int]:
    db = SessionLocal()
    try:
        counts: dict[str, int] = {}
        for (login,) in db.query(Lead.manager_login).all():
            key = str(login or '').strip().lower()
            counts[key] = counts.get(key, 0) + 1
        return counts
    finally:
        db.close()


def snapshot() -> list[dict]:
    db = SessionLocal()
    try:
        return [
            {c.name: getattr(u, c.name) for c in u.__table__.columns}
            for u in db.query(User).all()
        ]
    finally:
        db.close()


def print_state() -> None:
    users = snapshot()
    counts = lead_counts()
    print(f'Всего пользователей в базе: {len(users)}\n')
    for u in sorted(users, key=lambda x: (str(x['role'] or ''), str(x['login'] or '').lower())):
        n = counts.get(str(u['login'] or '').strip().lower(), 0)
        print(
            f'  {str(u["login"] or ""):<20} роль={str(u["role"] or ""):<8} '
            f'ФИО={str(u["full_name"] or ""):<22} tg={str(u["telegram"] or ""):<22} '
            f'тел={str(u["phone"] or ""):<15} активен={str(u["active"] or ""):<4} лидов={n}'
        )
    print(f'\nВсего лидов: {sum(counts.values())}')


def plan() -> tuple[list[dict], list[tuple], list[tuple]]:
    """Возвращает (кого деактивировать, кого обновить, кого создать)."""
    users = snapshot()
    by_login = {str(u['login'] or '').strip().lower(): u for u in users}

    keep_logins = set()
    to_update: list[tuple] = []
    to_create: list[tuple] = []

    for login, name, tg, phone, existing_login in NEW_MANAGERS:
        existing = by_login.get(str(existing_login or '').strip().lower()) if existing_login else None
        if existing:
            keep_logins.add(str(existing['login']).strip().lower())
            to_update.append((existing, name, tg, phone))
        else:
            to_create.append((login, name, tg, phone))

    to_deactivate = [
        u for u in users
        if str(u['role'] or '').strip().lower() == ROLE_MANAGER
        and str(u['login'] or '').strip().lower() not in keep_logins
        and str(u['active'] or '').strip().upper() != 'НЕТ'
    ]
    return to_deactivate, to_update, to_create


def show_plan(to_deactivate, to_update, to_create) -> None:
    counts = lead_counts()

    print(f'=== ДЕАКТИВИРОВАТЬ ({len(to_deactivate)}) — Активен: ДА → НЕТ ===')
    for u in to_deactivate:
        n = counts.get(str(u['login'] or '').strip().lower(), 0)
        print(f'  {str(u["login"] or ""):<20} {str(u["full_name"] or ""):<22} лидов={n} (лиды сохраняются)')

    print(f'\n=== ОБНОВИТЬ ({len(to_update)}) — логин и пароль не меняются ===')
    for existing, name, tg, phone in to_update:
        n = counts.get(str(existing['login'] or '').strip().lower(), 0)
        print(f'  {str(existing["login"] or ""):<20} лидов={n}')
        print(f'      ФИО:      {str(existing["full_name"] or "")!r} → {name!r}')
        print(f'      telegram: {str(existing["telegram"] or "")!r} → {tg!r}')
        old_phone = str(existing['phone'] or '')
        new_phone = f'{phone!r}' if phone else f'{old_phone!r} (номер не прислан — оставляем прежний)'
        print(f'      телефон:  {old_phone!r} → {new_phone}')

    print(f'\n=== СОЗДАТЬ ({len(to_create)}) ===')
    for login, name, tg, phone in to_create:
        print(f'  {login:<12} {name:<12} @{tg:<24} {phone or "— телефон позже"}')


def apply_changes(to_deactivate, to_update, to_create) -> None:
    created: list[tuple[str, str, str]] = []
    db = SessionLocal()
    try:
        for u in to_deactivate:
            db.query(User).filter(User.login == u['login']).update({'active': 'НЕТ'})

        for existing, name, tg, phone in to_update:
            updates = {'full_name': name, 'telegram': tg, 'active': 'ДА', 'role': ROLE_MANAGER}
            if phone:
                updates['phone'] = phone
            db.query(User).filter(User.login == existing['login']).update(updates)

        now_iso = now_local().isoformat(timespec='seconds')
        for login, name, tg, phone in to_create:
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
            created.append((login, name, password))

        db.commit()
    except Exception as e:
        db.rollback()
        print(f'\n❌ Ошибка, изменения откачены: {e}')
        sys.exit(1)
    finally:
        db.close()

    print(f'\n✅ Деактивировано: {len(to_deactivate)}. Обновлено: {len(to_update)}. Создано: {len(created)}.')

    if created:
        print('\n=== ПАРОЛИ НОВЫХ АККАУНТОВ (повторно не показать) ===')
        for login, name, password in created:
            print(f'  {name:<12} логин: {login:<12} пароль: {password}')

    if to_update:
        print('\nУ обновлённых аккаунтов пароли прежние — входят как раньше:')
        print('  ' + ', '.join(str(e['login']) for e, _, _, _ in to_update))

    sync_sheet()


def sync_sheet() -> None:
    """Переписывает лист users в Google Sheets по текущему состоянию базы.

    Нужно потому, что при пустой базе приложение на старте восстанавливает
    пользователей из Google Sheets (startup_event в app.py) — расхождение
    вернуло бы старый состав.
    """
    try:
        import sheets

        ws = sheets.get_or_create_worksheet('users')
        old_rows = max(len(ws.get_all_values()) - 1, 0)

        users = snapshot()
        rows = [[str(u.get(py_name) or '') for py_name in (
            'login', 'full_name', 'role', 'phone', 'telegram',
            'active', 'salt', 'password_hash', 'created_at',
        )] for u in users]

        if rows:
            ws.update(f'A2:I{len(rows) + 1}', rows, value_input_option='RAW')
        if old_rows > len(rows):
            ws.batch_clear([f'A{len(rows) + 2}:I{old_rows + 1}'])

        sheets._USERS_CACHE['ts'] = 0
        print(f'\n✅ Google Sheets: лист users перезаписан ({len(rows)} строк).')
    except Exception as e:
        print(f'\n⚠️  Google Sheets не синхронизирован: {e}')
        print(f'   База обновлена корректно. Лист users сверь вручную (колонка «{HEADERS_USERS[0]}»).')


def main() -> None:
    parser = argparse.ArgumentParser(description='Обновление состава менеджеров')
    parser.add_argument('--list', action='store_true', help='показать текущее состояние')
    parser.add_argument('--apply', action='store_true', help='применить изменения')
    args = parser.parse_args()

    if args.list:
        print_state()
        return

    to_deactivate, to_update, to_create = plan()
    show_plan(to_deactivate, to_update, to_create)

    if args.apply:
        apply_changes(to_deactivate, to_update, to_create)
    else:
        print('\nЭто dry-run, база не тронута. Для применения: --apply')


if __name__ == '__main__':
    main()
