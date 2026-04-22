from __future__ import annotations
from db_services import get_settings_cached, update_settings_bulk
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from telegram.helpers import create_deep_linked_url
from telegram import Bot
import csv
import io
import asyncio

from auth_utils import generate_salt, hash_password, verify_password
from config import (
    APP_HOST,
    APP_PORT,
    BOT_USERNAME,
    DEFAULT_BRANCH_ADDRESS,
    DEFAULT_BRANCH_LOCATION_GOOGLE_URL,
    DEFAULT_BRANCH_LOCATION_YANDEX_URL,
    DEFAULT_BRANCH_NAME,
    SESSION_SECRET,
    validate_basic_config,
)
from constants import ROLE_ADMIN, ROLE_MANAGER, ROLE_OWNER, STATUS_CHOICES, STATUS_LABELS, STATUS_LINK_SENT
from db_services import (
    append_lead_dict,
    append_user_dict,
    ensure_headers,
    find_lead_by_id,
    find_user_by_login,
    get_all_leads,
    get_all_users,
    update_lead_fields,
    update_user_fields,
    save_message,
    get_messages,
    count_unread_messages,
    mark_messages_read,
)

from utils import bool_to_sheet, make_lead_id, now_local, normalize_bool, parse_meeting_datetime

BASE_DIR = Path(__file__).resolve().parent
app = FastAPI(title='Newton Admin Panel')
app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='static')
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))


def current_user(request: Request) -> dict | None:
    login = request.session.get('login')
    if not login:
        return None
    return find_user_by_login(login)


def require_user(request: Request) -> dict:
    user = current_user(request)
    if not user or not normalize_bool(user.get('active', '')):
        raise PermissionError
    return user


def is_admin(user: dict) -> bool:
    return user.get('role') == ROLE_ADMIN

def is_owner(user: dict) -> bool:
    return user.get('role') == ROLE_OWNER

def is_manager(user: dict) -> bool:
    return user.get('role') == ROLE_MANAGER

def lead_visible_to_user(lead: dict, user: dict) -> bool:
    if is_admin(user) or is_owner(user):
        return True
    if is_manager(user):
        return str(lead.get('manager_login', '')).strip().lower() == str(user.get('login', '')).strip().lower()
    return False


def base_stats(leads: list[dict]) -> dict:
    statuses = Counter(lead.get('status', '') for lead in leads)
    bot_started = sum(1 for lead in leads if normalize_bool(lead.get('bot_started', '')))
    confirmed = sum(1 for lead in leads if normalize_bool(lead.get('confirmed', '')))
    arrived = sum(1 for lead in leads if normalize_bool(lead.get('arrived', '')))
    bought = sum(1 for lead in leads if normalize_bool(lead.get('bought', '')))
    meetings = Counter(str(lead.get('meeting_date', '')).strip() for lead in leads if str(lead.get('meeting_date', '')).strip())
    recent_dates = sorted(meetings.keys())[-7:]
    dates_chart = {d: meetings[d] for d in recent_dates} if recent_dates else {}

    return {
        'total': len(leads),
        'bot_started': bot_started,
        'confirmed': confirmed,
        'arrived': arrived,
        'bought': bought,
        'statuses': statuses,
        'dates_chart': dates_chart,
    }

def has_owner() -> bool:
    for u in get_all_users():
        if str(u.get('role', '')).strip() == ROLE_OWNER and normalize_bool(u.get('active', '')):
            return True
    return False

@app.get('/bootstrap-owner', response_class=HTMLResponse)
def bootstrap_owner_page(request: Request):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    if has_owner():
        return RedirectResponse('/', status_code=303)

    return templates.TemplateResponse(
        'bootstrap_owner.html',
        {'request': request, 'user': user},
    )

@app.post('/bootstrap-owner')
def bootstrap_owner_submit(request: Request):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    if has_owner():
        return RedirectResponse('/', status_code=303)

    update_user_fields(user['login'], {'role': ROLE_OWNER})
    return RedirectResponse('/', status_code=303)

@app.on_event('startup')
def startup_event() -> None:
    import os
    validate_basic_config()
    ensure_headers()

    # Auto-migrate from Google Sheets on boot if database is completely empty
    migrated = False
    try:
        from db_models import SessionLocal, User
        db = SessionLocal()
        count = db.query(User).count()
        db.close()
        if count == 0:
            import migrate_from_gs
            print("Database is empty. Starting automatic migration from Google Sheets...")
            migrate_from_gs.migrate()
            migrated = True
    except Exception as e:
        print(f"Failed to auto-migrate from Google Sheets: {e}")

    # Fallback: seed first user from env vars if DB is still empty
    # Set SEED_LOGIN, SEED_PASSWORD, SEED_ROLE (default: owner) in Railway env vars
    if not migrated:
        try:
            seed_login = os.getenv('SEED_LOGIN', '').strip().lower()
            seed_password = os.getenv('SEED_PASSWORD', '').strip()
            seed_role = os.getenv('SEED_ROLE', 'owner').strip()
            if seed_login and seed_password:
                from db_models import SessionLocal, User
                db = SessionLocal()
                existing = db.query(User).filter(User.login == seed_login).first()
                db.close()
                if not existing:
                    from auth_utils import generate_salt, hash_password
                    from utils import now_local
                    salt = generate_salt()
                    pw_hash = hash_password(seed_password, salt)
                    from db_services import append_user_dict
                    append_user_dict({
                        'login': seed_login,
                        'full_name': seed_login,
                        'role': seed_role,
                        'phone': '',
                        'telegram': '',
                        'active': 'ДА',
                        'salt': salt,
                        'password_hash': pw_hash,
                        'created_at': now_local().isoformat(timespec='seconds'),
                    })
                    print(f"Seeded user '{seed_login}' with role '{seed_role}' from env vars.")
        except Exception as e:
            print(f"Failed to seed user from env vars: {e}")


@app.get('/login', response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse('login.html', {'request': request, 'error': None})


@app.post('/login', response_class=HTMLResponse)
def login_submit(request: Request, login: str = Form(...), password: str = Form(...)):
    user = find_user_by_login(login)
    if not user or not normalize_bool(user.get('active', '')):
        return templates.TemplateResponse('login.html', {'request': request, 'error': 'Неверный логин или пароль'})
    if not verify_password(password, str(user.get('salt', '')), str(user.get('password_hash', ''))):
        return templates.TemplateResponse('login.html', {'request': request, 'error': 'Неверный логин или пароль'})

    request.session['login'] = user['login']
    return RedirectResponse(url='/', status_code=303)


@app.get('/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url='/login', status_code=303)


@app.get('/', response_class=HTMLResponse)
def dashboard(request: Request):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    leads = [lead for lead in get_all_leads() if lead_visible_to_user(lead, user)]
    stats = base_stats(leads)
    upcoming = sorted(
        [lead for lead in leads if parse_meeting_datetime(lead) and parse_meeting_datetime(lead) >= now_local()],
        key=lambda x: parse_meeting_datetime(x),
    )[:10]
    return templates.TemplateResponse('dashboard.html', {'request': request, 'user': user, 'stats': stats, 'upcoming': upcoming})


@app.get('/leads', response_class=HTMLResponse)
def leads_list(request: Request, status: str = '', day: str = '', q: str = ''):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    leads = [lead for lead in get_all_leads() if lead_visible_to_user(lead, user)]
    if status:
        leads = [lead for lead in leads if str(lead.get('status', '')).strip() == status]
    if day:
        leads = [lead for lead in leads if str(lead.get('meeting_date', '')).strip() == day]
    if q:
        q_lower = q.lower().strip()
        filtered = []
        for lead in leads:
            searchable = " ".join([
                str(lead.get('parent_name', '')),
                str(lead.get('parent_phone', '')),
                str(lead.get('manager_name', '')),
                str(lead.get('manager_login', '')),
                str(lead.get('manager_phone', '')),
                str(lead.get('lead_id', ''))
            ]).lower()
            if q_lower in searchable:
                filtered.append(lead)
        leads = filtered

    leads = sorted(leads, key=lambda x: parse_meeting_datetime(x) or now_local(), reverse=False)
    return templates.TemplateResponse(
    'leads.html',
    {
        'request': request,
        'user': user,
        'leads': leads,
        'status_choices': STATUS_CHOICES,
        'status_labels': STATUS_LABELS,
        'current_status': status,
        'current_day': day,
        'current_q': q,
    },
)

@app.get('/leads/export')
def leads_export(request: Request, status: str = '', day: str = '', q: str = ''):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    leads = [lead for lead in get_all_leads() if lead_visible_to_user(lead, user)]
    if status:
        leads = [lead for lead in leads if str(lead.get('status', '')).strip() == status]
    if day:
        leads = [lead for lead in leads if str(lead.get('meeting_date', '')).strip() == day]
    if q:
        q_lower = q.lower().strip()
        filtered = []
        for lead in leads:
            searchable = " ".join([
                str(lead.get('parent_name', '')), str(lead.get('parent_phone', '')),
                str(lead.get('manager_name', '')), str(lead.get('manager_login', '')),
                str(lead.get('manager_phone', '')), str(lead.get('lead_id', ''))
            ]).lower()
            if q_lower in searchable:
                filtered.append(lead)
        leads = filtered

    leads = sorted(leads, key=lambda x: parse_meeting_datetime(x) or now_local(), reverse=False)

    from constants import HEADERS_LEADS, HEADER_MAP_LEADS
    output = io.StringIO()
    # Write BOM for Excel UTF-8 compatibility
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(HEADERS_LEADS)
    
    # Reverse map dictionary
    py_to_sheet = {k: v for k, v in HEADER_MAP_LEADS.items()}
    
    for lead in leads:
        row = []
        for header in HEADERS_LEADS:
            # find py_key that matches the header
            py_key = None
            for pk, sh in py_to_sheet.items():
                if sh == header:
                    py_key = pk
                    break
            
            val = str(lead.get(py_key, '')) if py_key else ''
            row.append(val)
        writer.writerow(row)

    response = Response(content=output.getvalue(), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=leads_export.csv"
    return response


@app.get('/leads/new', response_class=HTMLResponse)
def lead_new_page(request: Request):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    # admin, owner и manager могут создавать клиентов
    if not (is_admin(user) or is_owner(user) or is_manager(user)):
        return RedirectResponse('/leads', status_code=303)

    managers = [
        u for u in get_all_users()
        if normalize_bool(u.get('active', '')) and str(u.get('role', '')).strip() == ROLE_MANAGER
    ]
    return templates.TemplateResponse(
        'lead_form.html',
        {'request': request, 'user': user, 'lead': None, 'managers': managers},
    )
@app.post('/leads/new')
def lead_create(
    request: Request,
    parent_name: str = Form(...),
    parent_phone: str = Form(...),
    meeting_date: str = Form(...),
    meeting_time: str = Form(...),
    manager_login: str = Form(...),
    language: str = Form('ru'),
    notes: str = Form(''),
):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    # admin, owner и manager могут создавать клиентов
    if not (is_admin(user) or is_owner(user) or is_manager(user)):
        return RedirectResponse('/leads', status_code=303)

    manager = find_user_by_login(manager_login)
    if not manager:
        return RedirectResponse('/leads/new', status_code=303)

    # выбранный менеджер должен быть активным manager
    if str(manager.get('role', '')).strip() != ROLE_MANAGER:
        return RedirectResponse('/leads/new', status_code=303)
    if not normalize_bool(manager.get('active', '')):
        return RedirectResponse('/leads/new', status_code=303)

    lead_id = make_lead_id()
    meeting_iso = f'{meeting_date}T{meeting_time}:00+05:00'

    s = get_settings_cached(force=False)
    branch_name_value = str(s.get('branch_name') or DEFAULT_BRANCH_NAME or '').strip()
    branch_address_value = str(s.get('branch_address') or DEFAULT_BRANCH_ADDRESS or '').strip()
    location_google_url_value = str(s.get('location_google_url') or DEFAULT_BRANCH_LOCATION_GOOGLE_URL or '').strip()

    append_lead_dict(
        {
            'lead_id': lead_id,
            'created_at': now_local().isoformat(timespec='seconds'),
            'manager_login': manager_login,
            'manager_name': manager.get('full_name', ''),
            'manager_phone': manager.get('phone', ''),
            'manager_telegram': manager.get('telegram', ''),
            'parent_name': parent_name,
            'parent_phone': parent_phone,
            'language': language,
            'meeting_date': meeting_date,
            'meeting_time': meeting_time,
            'meeting_datetime_iso': meeting_iso,
            'branch_name': branch_name_value,
            'address_text': branch_address_value,
            'location_url': location_google_url_value,
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
            'notes': notes,
        }
    )
    return RedirectResponse(url=f'/leads/{lead_id}', status_code=303)

@app.get('/api/notifications')
def get_notifications(request: Request):
    try:
        user = require_user(request)
    except PermissionError:
        return {'new_leads_count': 0, 'unread_messages': 0, 'new_leads': []}
        
    leads = [lead for lead in get_all_leads() if lead_visible_to_user(lead, user)]
    new_leads = [l for l in leads if str(l.get('status', '')).strip() == 'NEW']
    unread = count_unread_messages()
    # Return up to 8 new leads for dropdown
    items = [
        {
            'lead_id': l.get('lead_id', ''),
            'parent_name': l.get('parent_name', '—'),
            'parent_phone': l.get('parent_phone', ''),
            'manager_name': l.get('manager_name', ''),
            'created_at': (l.get('created_at') or '')[:10],
        }
        for l in sorted(new_leads, key=lambda x: x.get('created_at',''), reverse=True)[:8]
    ]
    return {'new_leads_count': len(new_leads), 'unread_messages': unread, 'new_leads': items}

@app.get('/api/messages/{lead_id}')
def api_get_messages(request: Request, lead_id: str):
    try:
        user = require_user(request)
    except PermissionError:
        return Response(status_code=403)
    lead = find_lead_by_id(lead_id)
    if not lead or not lead_visible_to_user(lead, user):
        return Response(status_code=403)
    mark_messages_read(lead_id)
    return {'messages': get_messages(lead_id)}

from pydantic import BaseModel

class StatusUpdate(BaseModel):
    status: str

class BulkStatusUpdate(BaseModel):
    lead_ids: list[str]
    status: str

@app.put('/api/leads/{lead_id}/status')
def api_update_status(request: Request, lead_id: str, data: StatusUpdate):
    try:
        user = require_user(request)
    except PermissionError:
        return Response(status_code=403)
        
    lead = find_lead_by_id(lead_id)
    if not lead or not lead_visible_to_user(lead, user):
        return Response(status_code=403)
        
    update_lead_fields(lead_id, {'status': data.status})
    return {'status': 'ok'}

from fastapi import BackgroundTasks

def run_bulk_update(lead_ids: list[str], status: str, user: dict):
    for lead_id in lead_ids:
        lead = find_lead_by_id(lead_id)
        if lead and lead_visible_to_user(lead, user):
            update_lead_fields(lead_id, {'status': status})

@app.put('/api/leads/bulk-status')
def api_bulk_update_status(request: Request, data: BulkStatusUpdate, bg_tasks: BackgroundTasks):
    try:
        user = require_user(request)
    except PermissionError:
        return Response(status_code=403)
        
    bg_tasks.add_task(run_bulk_update, data.lead_ids, data.status, user)
    return {'status': 'processing'}

@app.get('/leads/{lead_id}', response_class=HTMLResponse)
def lead_detail(request: Request, lead_id: str):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)
    lead = find_lead_by_id(lead_id)
    if not lead or not lead_visible_to_user(lead, user):
        return RedirectResponse('/leads', status_code=303)
    deep_link = create_deep_linked_url(BOT_USERNAME, lead_id)
    bot_started = normalize_bool(lead.get('bot_started', ''))
    # Mark messages as read when manager opens the lead
    mark_messages_read(lead_id)
    messages = get_messages(lead_id)
    return templates.TemplateResponse(
    'lead_detail.html',
    {
        'request': request,
        'user': user,
        'lead': lead,
        'deep_link': deep_link,
        'status_choices': STATUS_CHOICES,
        'status_labels': STATUS_LABELS,
        'bot_started': bot_started,
        'chat_messages': messages,
    },
)


@app.post('/leads/{lead_id}/send_message')
async def lead_send_message(
    request: Request,
    lead_id: str,
    message: str = Form(...),
):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    lead = find_lead_by_id(lead_id)
    if not lead or not lead_visible_to_user(lead, user):
        return RedirectResponse('/leads', status_code=303)

    tg_id = str(lead.get('telegram_user_id', '')).strip()
    if not tg_id:
        return templates.TemplateResponse('lead_detail.html', {
            'request': request, 'user': user, 'lead': lead,
            'deep_link': create_deep_linked_url(BOT_USERNAME, lead_id),
            'status_choices': STATUS_CHOICES, 'status_labels': STATUS_LABELS,
            'bot_started': normalize_bool(lead.get('bot_started', '')),
            'msg_error': '❌ Клиент ещё не запустил бота — Telegram ID неизвестен.',
        })

    try:
        from config import BOT_TOKEN
        bot = Bot(token=BOT_TOKEN)
        manager_name = str(user.get('full_name') or user.get('login', '')).strip()
        full_text = f"💬 <b>Сообщение от менеджера {manager_name}:</b>\n\n{message}"
        await bot.send_message(chat_id=int(tg_id), text=full_text, parse_mode='HTML')
        save_message(lead_id=lead_id, direction='out',
                     sender=manager_name or 'Менеджер', text=message)
        msg_success = '✅ Сообщение успешно отправлено клиенту в Telegram!'
    except Exception as e:
        msg_success = None
        msg_error = f'❌ Ошибка отправки: {e}'
        return templates.TemplateResponse('lead_detail.html', {
            'request': request, 'user': user, 'lead': lead,
            'deep_link': create_deep_linked_url(BOT_USERNAME, lead_id),
            'status_choices': STATUS_CHOICES, 'status_labels': STATUS_LABELS,
            'bot_started': normalize_bool(lead.get('bot_started', '')),
            'msg_error': msg_error,
        })

    return templates.TemplateResponse('lead_detail.html', {
        'request': request, 'user': user, 'lead': lead,
        'deep_link': create_deep_linked_url(BOT_USERNAME, lead_id),
        'status_choices': STATUS_CHOICES, 'status_labels': STATUS_LABELS,
        'bot_started': normalize_bool(lead.get('bot_started', '')),
        'msg_success': msg_success,
    })


@app.post('/leads/{lead_id}/clone')
def lead_clone(request: Request, lead_id: str):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    original = find_lead_by_id(lead_id)
    if not original or not lead_visible_to_user(original, user):
        return RedirectResponse('/leads', status_code=303)

    # Build new lead: copy parent/manager info, reset status fields
    new_id = make_lead_id()
    new_lead = {
        'lead_id': new_id,
        'created_at': now_local().strftime('%Y-%m-%d %H:%M:%S'),
        'manager_login': original.get('manager_login', ''),
        'manager_name': original.get('manager_name', ''),
        'manager_phone': original.get('manager_phone', ''),
        'manager_telegram': original.get('manager_telegram', ''),
        'parent_name': original.get('parent_name', ''),
        'parent_phone': original.get('parent_phone', ''),
        'language': original.get('language', ''),
        'branch_name': original.get('branch_name', ''),
        'address_text': original.get('address_text', ''),
        'location_url': original.get('location_url', ''),
        # reset all meeting/bot/status fields
        'meeting_date': '',
        'meeting_time': '',
        'meeting_datetime_iso': '',
        'status': 'NEW',
        'telegram_user_id': '',
        'telegram_username': '',
        'bot_started': 'НЕТ',
        'confirmed': 'НЕТ',
        'confirmed_at': '',
        'remind_3d_sent': '',
        'remind_1d_sent': '',
        'remind_6h_sent': '',
        'remind_3h_sent': '',
        'remind_2h_sent': '',
        'arrived': 'НЕТ',
        'bought': 'НЕТ',
        'notes': f'Повтор лида {lead_id}',
    }
    append_lead_dict(new_lead)
    return RedirectResponse(url=f'/leads/{new_id}', status_code=303)


@app.get('/inbox', response_class=HTMLResponse)
def inbox_page(request: Request):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    from db_models import SessionLocal, Message
    from sqlalchemy import func

    leads = {l['lead_id']: l for l in get_all_leads() if lead_visible_to_user(l, user)}

    db = SessionLocal()
    try:
        # Get latest message per lead that has any messages
        subq = (
            db.query(Message.lead_id, func.max(Message.id).label('max_id'))
            .filter(Message.lead_id.in_(list(leads.keys())))
            .group_by(Message.lead_id)
            .subquery()
        )
        latest_msgs = (
            db.query(Message)
            .join(subq, Message.id == subq.c.max_id)
            .all()
        )
        # Count unread per lead
        unread_counts = dict(
            db.query(Message.lead_id, func.count(Message.id))
            .filter(Message.direction == 'in', Message.is_read == '0',
                    Message.lead_id.in_(list(leads.keys())))
            .group_by(Message.lead_id)
            .all()
        )
    finally:
        db.close()

    threads = []
    for msg in sorted(latest_msgs, key=lambda m: m.id, reverse=True):
        lead = leads.get(msg.lead_id)
        if not lead:
            continue
        threads.append({
            'lead_id': msg.lead_id,
            'parent_name': lead.get('parent_name', ''),
            'parent_phone': lead.get('parent_phone', ''),
            'manager_name': lead.get('manager_name', ''),
            'manager_login': lead.get('manager_login', ''),
            'last_text': msg.text[:80] + ('…' if len(msg.text) > 80 else ''),
            'last_time': msg.created_at[11:16] if msg.created_at and len(msg.created_at) > 10 else '',
            'last_direction': msg.direction,
            'unread': unread_counts.get(msg.lead_id, 0),
        })

    return templates.TemplateResponse('inbox.html', {
        'request': request,
        'user': user,
        'threads': threads,
    })


@app.get('/stats', response_class=HTMLResponse)
def stats_page(request: Request):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)
    # доступ к статистике: admin ИЛИ owner
    if not (is_admin(user) or is_owner(user)):
        return RedirectResponse('/', status_code=303)

    leads = get_all_leads()
    users = [
    u for u in get_all_users()
    if normalize_bool(u.get('active', '')) and str(u.get('role', '')).strip() in {ROLE_MANAGER, ROLE_ADMIN, ROLE_OWNER}
]
    per_manager = []
    for manager in users:
        manager_leads = [lead for lead in leads if str(lead.get('manager_login', '')).strip().lower() == str(manager.get('login', '')).strip().lower()]
        stats = base_stats(manager_leads)
        per_manager.append({'manager': manager, 'stats': stats})
    return templates.TemplateResponse('stats.html', {'request': request, 'user': user, 'per_manager': per_manager, 'global_stats': base_stats(leads)})

@app.get('/users', response_class=HTMLResponse)
def users_list(request: Request, q: str = ''):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    if not (is_admin(user) or is_owner(user)):
        return RedirectResponse('/', status_code=303)

    users = get_all_users()
    if q:
        q_lower = q.lower().strip()
        filtered = []
        for u in users:
            searchable = " ".join([
                str(u.get('login', '')),
                str(u.get('full_name', '')),
                str(u.get('phone', '')),
                str(u.get('telegram', ''))
            ]).lower()
            if q_lower in searchable:
                filtered.append(u)
        users = filtered

    return templates.TemplateResponse(
        'users.html',
        {
            'request': request,
            'user': user,
            'users': users,
            'current_q': q,
        },
    )


@app.get('/users/new', response_class=HTMLResponse)
def user_new_page(request: Request):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)
    if not (is_admin(user) or is_owner(user)):
        return RedirectResponse('/', status_code=303)

    allowed_roles = ['manager']  # admin может создавать только менеджеров
    if is_owner(user):
        allowed_roles = ['manager', 'admin']  # owner может создавать admin тоже

    return templates.TemplateResponse(
        'user_form.html',
        {
            'request': request,
            'user': user,
            'allowed_roles': allowed_roles,
            'error': None,
        },
    )

@app.post('/users/new', response_class=HTMLResponse)
def user_create(
    request: Request,
    login: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    phone: str = Form(''),
    telegram: str = Form(''),
    password: str = Form(...),
    active: str = Form('ДА'),
):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    # доступ: admin или owner
    if not (is_admin(user) or is_owner(user)):
        return RedirectResponse('/', status_code=303)

    # нормализация
    login = login.strip()
    full_name = full_name.strip()
    role = role.strip()
    phone = phone.strip()
    telegram = telegram.strip().lstrip('@')
    password = password.strip()
    active = active.strip()

    # разрешённые роли для создания
    allowed_roles = ['manager']          # admin
    if is_owner(user):
        allowed_roles = ['manager', 'admin']  # owner

    # проверка роли
    if role not in allowed_roles:
        return templates.TemplateResponse(
            'user_form.html',
            {
                'request': request,
                'user': user,
                'allowed_roles': allowed_roles,
                'error': 'Недопустимая роль.',
            },
        )

    # обязательные поля
    if not login or not full_name or not password:
        return templates.TemplateResponse(
            'user_form.html',
            {
                'request': request,
                'user': user,
                'allowed_roles': allowed_roles,
                'error': 'Заполни логин, ФИО и пароль.',
            },
        )

    # уникальность логина
    existing = find_user_by_login(login)
    if existing:
        return templates.TemplateResponse(
            'user_form.html',
            {
                'request': request,
                'user': user,
                'allowed_roles': allowed_roles,
                'error': 'Пользователь с таким логином уже существует.',
            },
        )

    # хеш пароля
    salt = generate_salt()
    password_hash = hash_password(password, salt)

    append_user_dict(
        {
            'login': login,
            'full_name': full_name,
            'role': role,
            'phone': phone,
            'telegram': telegram,
            'active': active if active in {'ДА', 'НЕТ'} else 'ДА',
            'salt': salt,
            'password_hash': password_hash,
            'created_at': now_local().isoformat(timespec='seconds'),
        }
    )

    return RedirectResponse('/users', status_code=303)

@app.get('/users/{login}/edit', response_class=HTMLResponse)
def user_edit_page(request: Request, login: str):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    if not (is_admin(user) or is_owner(user)):
        return RedirectResponse('/', status_code=303)

    edit_user = find_user_by_login(login)
    if not edit_user:
        return RedirectResponse('/users', status_code=303)

    # admin НЕ трогает admin/owner
    if is_admin(user) and login != user.get('login') and str(edit_user.get('role','')).strip() != ROLE_MANAGER:
        return RedirectResponse('/users', status_code=303)
    allowed_roles = ['manager']
    if is_owner(user):
        allowed_roles = ['manager', 'admin']

    return templates.TemplateResponse(
        "user_form.html",
        {
            "request": request,
            "user": user,
            "edit_user": edit_user,
            "allowed_roles": allowed_roles,
            "error": None,
        },
    )

@app.post('/users/{login}/edit', response_class=HTMLResponse)
def user_edit_submit(
    request: Request,
    login: str,
    full_name: str = Form(...),
    role: str = Form(...),
    phone: str = Form(''),
    telegram: str = Form(''),
    password: str = Form(''),
    active: str = Form('ДА'),
):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    # ✅ доступ: admin ИЛИ owner
    if not (is_admin(user) or is_owner(user)):
        return RedirectResponse('/', status_code=303)

    edit_user = find_user_by_login(login)
    if not edit_user:
        return RedirectResponse('/users', status_code=303)

    # ✅ admin НЕ может трогать admin/owner (только manager)
    if is_admin(user) and login != user.get('login') and str(edit_user.get('role', '')).strip() != ROLE_MANAGER:
        return RedirectResponse('/users', status_code=303)

    # ✅ admin не меняет роль (игнорируем то, что пришло из формы)
    if is_admin(user):
        role = str(edit_user.get('role', ROLE_MANAGER)).strip()

    updates = {
        'full_name': full_name.strip(),
        'role': role.strip(),
        'phone': phone.strip(),
        'telegram': telegram.strip().lstrip('@'),
        'active': active.strip(),
    }

    if password.strip():
        salt = generate_salt()
        password_hash = hash_password(password.strip(), salt)
        updates['salt'] = salt
        updates['password_hash'] = password_hash

    update_user_fields(login, updates)
    return RedirectResponse('/users', status_code=303)

@app.get('/users/{login}/reset-password', response_class=HTMLResponse)
def user_reset_password_page(request: Request, login: str):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    # доступ: admin или owner
    if not (is_admin(user) or is_owner(user)):
        return RedirectResponse('/', status_code=303)

    target_user = find_user_by_login(login)
    if not target_user:
        return RedirectResponse('/users', status_code=303)

    # admin может сбрасывать пароль: себе и менеджерам
    if is_admin(user) and login != user.get('login') and str(target_user.get('role', '')).strip() != ROLE_MANAGER:
        return RedirectResponse('/users', status_code=303)

    return templates.TemplateResponse(
        "user_reset_password.html",
        {
            "request": request,
            "user": user,
            "target_user": target_user,
            "error": None,
        },
    )

@app.post('/users/{login}/reset-password', response_class=HTMLResponse)
def user_reset_password_submit(
    request: Request,
    login: str,
    new_password: str = Form(...),
):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    # ✅ доступ: admin ИЛИ owner
    if not (is_admin(user) or is_owner(user)):
        return RedirectResponse('/', status_code=303)

    target_user = find_user_by_login(login)
    if not target_user:
        return RedirectResponse('/users', status_code=303)

    # ✅ admin может сбрасывать пароль только менеджеру
    if is_admin(user) and str(target_user.get('role', '')).strip() != ROLE_MANAGER:
        return RedirectResponse('/users', status_code=303)

    new_password = new_password.strip()
    if len(new_password) < 4:
        return templates.TemplateResponse(
            'user_reset_password.html',
            {
                'request': request,
                'user': user,
                'target_user': target_user,
                'error': 'Пароль должен быть минимум 4 символа.',
            },
        )

    salt = generate_salt()
    password_hash = hash_password(new_password, salt)

    update_user_fields(
        login,
        {
            'salt': salt,
            'password_hash': password_hash,
        },
    )

    return RedirectResponse('/users', status_code=303)

@app.get('/settings', response_class=HTMLResponse)
def settings_page(request: Request):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    if not is_owner(user):
        return RedirectResponse('/', status_code=303)

    s = get_settings_cached(force=True)
    return templates.TemplateResponse(
        'settings.html',
        {'request': request, 'user': user, 's': s, 'saved': False},
    )

@app.post('/settings', response_class=HTMLResponse)
def settings_save(
    request: Request,
    branch_name: str = Form(''),
    branch_address: str = Form(''),
    location_google_url: str = Form(''),
    location_yandex_url: str = Form(''),

    remind_3d_enabled: str = Form('НЕТ'),
    remind_3d_hours: str = Form('72'),

    remind_1d_enabled: str = Form('НЕТ'),
    remind_1d_hours: str = Form('24'),

    remind_6h_enabled: str = Form('НЕТ'),
    remind_6h_hours: str = Form('6'),

    remind_3h_enabled: str = Form('НЕТ'),
    remind_3h_hours: str = Form('3'),

    remind_2h_enabled: str = Form('НЕТ'),
    remind_2h_hours: str = Form('2'),

    poll_interval_seconds: str = Form('60'),
):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    if not is_owner(user):
        return RedirectResponse('/', status_code=303)

    updates = {
        'branch_name': branch_name.strip(),
        'branch_address': branch_address.strip(),
        'location_google_url': location_google_url.strip(),
        'location_yandex_url': location_yandex_url.strip(),

        'remind_3d_enabled': remind_3d_enabled.strip(),
        'remind_3d_hours': remind_3d_hours.strip(),

        'remind_1d_enabled': remind_1d_enabled.strip(),
        'remind_1d_hours': remind_1d_hours.strip(),

        'remind_6h_enabled': remind_6h_enabled.strip(),
        'remind_6h_hours': remind_6h_hours.strip(),

        'remind_3h_enabled': remind_3h_enabled.strip(),
        'remind_3h_hours': remind_3h_hours.strip(),

        'remind_2h_enabled': remind_2h_enabled.strip(),
        'remind_2h_hours': remind_2h_hours.strip(),

        'poll_interval_seconds': poll_interval_seconds.strip(),
    }

    update_settings_bulk(updates)
    s = get_settings_cached(force=True)
    return templates.TemplateResponse(
        'settings.html',
        {'request': request, 'user': user, 's': s, 'saved': True},
    )

@app.post('/leads/{lead_id}/meeting')
def lead_meeting_update(
    request: Request,
    lead_id: str,
    meeting_date: str = Form(...),
    meeting_time: str = Form(...),
    status: str = Form(...),
):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    lead = find_lead_by_id(lead_id)
    if not lead or not lead_visible_to_user(lead, user):
        return RedirectResponse('/leads', status_code=303)

    old_date = str(lead.get('meeting_date', '')).strip()
    old_time = str(lead.get('meeting_time', '')).strip()
    meeting_changed = (meeting_date != old_date) or (meeting_time != old_time)

    meeting_iso = f'{meeting_date}T{meeting_time}:00+05:00'

    updates = {
        'meeting_date': meeting_date,
        'meeting_time': meeting_time,
        'meeting_datetime_iso': meeting_iso,
        'status': status,
    }

    if meeting_changed:
        updates['remind_3d_sent'] = 'НЕТ'
        updates['remind_1d_sent'] = 'НЕТ'
        updates['remind_6h_sent'] = 'НЕТ'
        updates['remind_3h_sent'] = 'НЕТ'
        updates['remind_2h_sent'] = 'НЕТ'

        if normalize_bool(lead.get('confirmed', '')):
            updates['status'] = 'CONFIRMED'

    update_lead_fields(lead_id, updates)
    return RedirectResponse(url=f'/leads/{lead_id}', status_code=303)


@app.post('/leads/{lead_id}/result')
def lead_result_update(
    request: Request,
    lead_id: str,
    arrived: str = Form('НЕТ'),
    bought: str = Form('НЕТ'),
    notes: str = Form(''),
):
    try:
        user = require_user(request)
    except PermissionError:
        return RedirectResponse('/login', status_code=303)

    lead = find_lead_by_id(lead_id)
    if not lead or not lead_visible_to_user(lead, user):
        return RedirectResponse('/leads', status_code=303)

    updates = {
        'arrived': arrived,
        'bought': bought,
        'notes': notes,
    }

    if normalize_bool(bought):
        updates['bought'] = 'ДА'
        updates['arrived'] = 'ДА'
        updates['status'] = 'BOUGHT'
    elif normalize_bool(arrived):
        updates['status'] = 'ARRIVED'
    else:
        current_status = str(lead.get('status', '')).strip()
        if current_status in {'ARRIVED', 'BOUGHT'}:
            updates['status'] = 'CONFIRMED'

    update_lead_fields(lead_id, updates)
    return RedirectResponse(url=f'/leads/{lead_id}', status_code=303)

if __name__ == '__main__':
    import uvicorn

    uvicorn.run('app:app', host=APP_HOST, port=APP_PORT, reload=True)
