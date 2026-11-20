"""Preview, delivery receipts, follow-ups and confirmed attendance for exam juries."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import hmac
import json
import logging
import os
from pathlib import Path
import re
import secrets
import threading
import time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests
from flask import abort, current_app, flash, redirect, render_template, request, session, url_for
from itsdangerous import BadData, URLSafeTimedSerializer

from services.session_storage import SessionStorageConflict


LOG = logging.getLogger('jury-workflow')
PARIS = ZoneInfo('Europe/Paris')
DESTINATION = 'https://gestionstagiaires-r5no.onrender.com/api/integrations/plateformegestion/jury-confirmations'
CHANNELS = {'email': 'E-mail', 'sms': 'SMS'}
STAGES = ('invitation', '24h', '48h')
FOLLOW_UPS = STAGES[1:]
_worker_guard = threading.Lock()


def utcnow():
    return datetime.now(timezone.utc)


def instant(value):
    if not value:
        return None
    try:
        when = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return (when if when.tzinfo else when.replace(tzinfo=PARIS)).astimezone(timezone.utc)
    except ValueError:
        return None


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


@contextmanager
def member_lock(services, sid, jid):
    directory = Path(services.DATA_DIR) / 'jury_locks'
    directory.mkdir(exist_ok=True)
    with (directory / fingerprint([sid, jid])).open('a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def edit(services, change):
    # Other tabs and workers update the same versioned session file. Only
    # replay the in-memory mutation, never the provider call that preceded it.
    for attempt in range(6):
        data = services.load_sessions()
        result = change(data)
        try:
            services.save_sessions(data)
            return result
        except SessionStorageConflict:
            if attempt == 5:
                raise


def assigned(training, jid):
    return next((j for j in training.get('jurys', []) if str(j.get('id')) == jid), None)


def contact(services, data, training, jid):
    member = assigned(training, jid)
    if member is not None:
        return member
    return next((j for j in data.get('jurys', []) if str(j.get('id')) == jid), None)


def exam_selector(services, training):
    code = str(training.get('formation') or '').upper()
    level = {'APS': 'APS', 'A3P': 'A3P', 'DIRIGEANT': 'DESP initial', 'DESP': 'DESP initial'}.get(code, '')
    if 'SSIAP' in code and 'AFC' not in code:
        descriptor = (training.get('display_name') or '') + ' ' + code
        number = re.search(r'SSIAP\s*([123])', descriptor, re.I)
        level = 'SSIAP ' + (number.group(1) if number else '1')
    when = services.session_input_date(training.get('date_exam'))
    afc = code == 'AFC_APS_SSIAP'
    if afc:
        kinds = {sl.get('afcCategory') for d in training.get('apsPlanningData', [])
                 if services.session_input_date(d.get('date')) == when for sl in d.get('slots', [])}
        if ('EXAM_SSIAP1' in kinds) != ('EXAM_APS' in kinds):
            level = 'SSIAP 1' if 'EXAM_SSIAP1' in kinds else 'APS'
    return {'source_id': str(training['id']), 'level': level, 'afc': afc,
            'site': str(training.get('dirigeant_location') or '').lower() if level == 'DESP initial' else '',
            'target_id': training.get('jury_target_id') or (training.get('afcAttendanceSourceSessionId') if afc else '') or '',
            'date_start': services.session_input_date(training.get('date_debut')),
            'date_end': services.session_input_date(training.get('date_fin')), 'exam_date': when}


def closed(services, training, now):
    last_day = services.parse_date(training.get('date_exam')) or services.parse_date(training.get('date_fin'))
    return bool(training.get('archived') or training.get('cancelled') or training.get('canceled')
                or (last_day and last_day.date() < now.astimezone(PARIS).date()))


def response_urls(training, member):
    base = (os.environ.get('RENDER_EXTERNAL_URL') or 'https://plateformegestion.onrender.com').rstrip('/')
    adapter = current_app.url_map.bind('localhost')
    return [base + adapter.build('jury_response', {'sid': training['id'], 'jid': member['id'], 'response': choice})
            + '?' + urlencode({'token': member['token']}) for choice in ('present', 'absent')]


def message(services, training, member, stage, links):
    selector = exam_selector(services, training)
    label = selector['level'] or training.get('display_name') or services.formation_label(training.get('formation')) or 'Examen'
    if selector['afc'] and selector['level']:
        label += ' · AFC France Travail'
    if selector['site'] in ('puget', 'paris'):
        label += ' · ' + ('Puget-sur-Argens' if selector['site'] == 'puget' else 'Paris')
    date = services.format_date(selector['exam_date']) if selector['exam_date'] else 'Date à préciser'
    title = {'invitation': 'Invitation au jury', '24h': 'Rappel de votre invitation', '48h': 'Dernier rappel pour le jury'}[stage]
    subject = f'{title} · {label} · {date}'
    intro = {'invitation': 'Nous aimerions vous compter parmi les membres du jury pour cet examen.',
             '24h': 'Avez-vous eu le temps de vérifier votre disponibilité pour cet examen ?',
             '48h': 'Nous finalisons la composition du jury. Pouvez-vous nous indiquer si vous serez disponible ?'}[stage]
    html = current_app.jinja_env.get_template('emails/jury_invitation.html').render(title=title, subject=subject, label=label,
                           date=date, intro=intro, member=member, yes_url=links[0], no_url=links[1])
    sms = (f"Intégrale Academy — {title}\n{label} · {date}\n"
           f"Disponible : {links[0]}\nIndisponible : {links[1]}")
    return {'title': title, 'subject': subject, 'html': html, 'sms': sms}


def available_channels(services, member, channels):
    return [ch for ch in channels if ((member.get('email') or '').strip() if ch == 'email'
                                      else services.normalize_phone_number(member.get('telephone') or ''))]


def draft(services, data, training, jid, channels, token):
    person = contact(services, data, training, jid)
    if not person or person.get('status') in ('present', 'absent'):
        return None
    member = {**person, 'id': jid, 'token': person.get('token') or token}
    usable = available_channels(services, member, channels)
    links = response_urls(training, member)
    messages = [message(services, training, member, stage, links) for stage in STAGES]
    digest = fingerprint([jid, member.get('email'), member.get('telephone'), member.get('notified_at'),
                          member.get('deliveries', {}).get('invitation'), usable, messages])
    return {'jid': jid, 'member': member, 'channels': usable, 'messages': messages, 'digest': digest}


def serializer():
    nonce = session.setdefault('jury_preview_nonce', secrets.token_hex(16))
    return URLSafeTimedSerializer(current_app.secret_key, salt='jury-preview-' + nonce)


def due_reminders(services, training, member, now):
    notified = instant(member.get('notified_at'))
    if (not notified or member.get('status', 'pending') != 'pending' or closed(services, training, now)
            or now < notified + timedelta(hours=24)):
        return {}
    deliveries = member.get('deliveries') or {}
    legacy = instant(member.get('reminded_at'))
    result = {}
    for channel in available_channels(services, member, member.get('invited_channels', CHANNELS)):
        first = deliveries.get('24h', {}).get(channel, {})
        first_at = legacy or (instant(first.get('at')) if first.get('status') in ('sent', 'sending', 'unknown') else None)
        if first_at:
            # Keep the regular 48-hour deadline, but space the reminders after an outage.
            if now < max(notified + timedelta(hours=48), first_at + timedelta(hours=23, minutes=59)):
                continue
            stage = '48h'
        else:
            stage = '24h'
        receipt = deliveries.get(stage, {}).get(channel, {})
        if not receipt or (receipt.get('status') == 'failed'
                           and now - instant(receipt['at']) >= timedelta(minutes=30)):
            result.setdefault(stage, []).append(channel)
    return result


def deliver(services, sid, member, stage, channel, content, attempt_id, now):
    jid = member['id']
    def reserve(data):
        training = services.find_session(data, sid)
        if not training or closed(services, training, now):
            return False
        current = assigned(training, jid)
        if current is None:
            if stage != 'invitation' or not contact(services, data, training, jid):
                return False
            current = {k: member.get(k) or '' for k in ('id', 'nom', 'prenom', 'email', 'telephone', 'token')}
            current['status'] = 'pending'
            training.setdefault('jurys', []).append(current)
        if current.get('status') in ('present', 'absent'):
            return False
        current['token'] = current.get('token') or member['token']
        records = current.setdefault('deliveries', {}).setdefault(stage, {})
        prior = records.get(channel, {})
        if prior.get('request_id') == attempt_id or (stage != 'invitation' and prior.get('status') in ('sending', 'sent', 'unknown')):
            return False
        records[channel] = {'status': 'sending', 'at': now.isoformat(), 'request_id': attempt_id}
        return True
    if not edit(services, reserve):
        return 'déjà traité'
    try:
        if channel == 'email':
            ok, error = services.send_email(member['email'], content['subject'], content['html'])
        else:
            ok, error = services.deliver_jury_sms(member['telephone'], content['sms'])
        status = 'sent' if ok else ('unknown' if uncertain(error) else 'failed')
    except Exception:
        LOG.exception('JURY_DELIVERY_UNCONFIRMED stage=%s channel=%s', stage, channel)
        status, error = 'unknown', 'réception par le prestataire à vérifier'

    def finish(data):
        training = services.find_session(data, sid)
        current = assigned(training, jid) if training else None
        if not current:
            return
        receipt = current['deliveries'][stage][channel]
        if receipt['request_id'] != attempt_id:
            return
        receipt.update(status=status, at=now.isoformat())
        if stage == 'invitation' and status == 'sent':
            if current.get('notified_at') and 'invited_channels' not in current:
                current['invited_channels'] = available_channels(services, current, CHANNELS)
            current['notified_at'] = current.get('notified_at') or now.isoformat()
            invited = current.setdefault('invited_channels', [])
            if channel not in invited:
                invited.append(channel)
            training['jury_notification_status'] = 'notified'
    edit(services, finish)
    LOG.info('JURY_DELIVERY stage=%s channel=%s status=%s', stage, channel, status)
    return {'sent': 'envoyé', 'unknown': 'envoi à vérifier', 'failed': str(error or 'échec de l’envoi')}[status]


def uncertain(error):
    text = str(error or '').lower()
    return any(word in text for word in ('timeout', 'timed out', 'connexion interrompue', 'disconnect',
                                         'reset', 'remote end closed', 'urlerror', 'connectionerror', 'broken pipe'))


def integration_key():
    dedicated = os.environ.get('JURY_SYNC_TOKEN', '').strip()
    if dedicated:
        return dedicated
    shared = os.environ.get('AFC_ATTENDANCE_SYNC_TOKEN', '').strip()
    return hmac.new(shared.encode(), b'plateformegestion:jury:v1', hashlib.sha256).hexdigest() if shared else ''


def sync_member(services, training, member, now):
    # Called with this member's lock. The receiver deduplicates by source IDs.
    key = integration_key()
    result = {'at': now.isoformat()}
    http_status = None
    try:
        if not key:
            raise ValueError('La liaison avec Gestion des stagiaires est à configurer.')
        selector = exam_selector(services, training)
        identity = dict(id=str(member['id']), first_name=member.get('prenom'), last_name=member.get('nom'),
                        email=member.get('email') or '', phone=member.get('telephone') or '')
        reply = requests.post(DESTINATION, json={'session': selector, 'member': identity},
                              headers={'Authorization': 'Bearer ' + key}, timeout=(3, 8), allow_redirects=False)
        http_status = reply.status_code
        if reply.status_code in (400, 409):
            raise ValueError(reply.json().get('error') or 'Vérifiez la session associée.')
        reply.raise_for_status()
        body = reply.json()
        if body.get('ok') is not True or not isinstance(body.get('session_id'), str) or not body['session_id']:
            raise ValueError('La plateforme n’a pas confirmé l’enregistrement.')
        result.update(status='synced', target_id=body['session_id'])
    except requests.RequestException:
        previous_delay = (member.get('jury_sync') or {}).get('retry_minutes', 0)
        delay = min(15, max(1, 2 * previous_delay))
        result.update(status='pending', retry_minutes=delay,
                      error=f'Liaison indisponible. Nouvel essai automatique dans {delay} minute' + ('s.' if delay > 1 else '.'))
    except ValueError as exc:
        result.update(status='pending', error=str(exc)[:200])
    def finish(data):
        row = services.find_session(data, training['id'])
        current = assigned(row, str(member['id'])) if row else None
        if current and current.get('status') == 'present':
            current['jury_sync'] = result
    edit(services, finish)
    LOG.info('JURY_SYNC session=%s status=%s http=%s target=%s',
             training['id'], result['status'], http_status, result.get('target_id', ''))
    return result


def needs_sync(services, training, member, now):
    if member.get('status') != 'present':
        return False
    sync = member.get('jury_sync') or {}
    if sync.get('status') == 'synced' or (not sync and closed(services, training, now)):
        return False
    last = instant(sync.get('at'))
    return not last or now - last >= timedelta(minutes=sync.get('retry_minutes', 15))


def scan(services, now=None):
    now = now or utcnow()
    candidates = [(row['id'], str(m['id'])) for row in services.load_sessions()['sessions']
                  for m in row.get('jurys', []) if m.get('id') and (
                      needs_sync(services, row, m, now) or due_reminders(services, row, m, now))]
    for sid, jid in candidates:
        with member_lock(services, sid, jid):
            row = services.find_session(services.load_sessions(), sid)
            member = assigned(row, jid) if row else None
            if not member:
                continue
            if needs_sync(services, row, member, now):
                sync_member(services, row, member, now)
                continue
            for stage, channels in due_reminders(services, row, member, now).items():
                # Old invitations carry the token originally sent to the recipient.
                member = {**member, 'id': jid, 'token': member.get('token') or secrets.token_urlsafe(24)}
                content = message(services, row, member, stage, response_urls(row, member))
                for channel in channels:
                    deliver(services, sid, member, stage, channel, content, secrets.token_hex(12), now)


def scan_once(app, services):
    with (Path(services.DATA_DIR) / 'jury_scan.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        try:
            with app.app_context():
                scan(services)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def start(app, services):
    if not services.IS_RENDER:
        return

    def worker():
        LOG.info('JURY_WORKER_STARTED pid=%s interval=60 sync_configured=%s', os.getpid(), bool(integration_key()))
        while True:
            try:
                scan_once(app, services)
            except Exception:
                LOG.exception('JURY_SCAN_FAILED')
            time.sleep(60)

    with _worker_guard:
        pid = os.getpid()
        registered = app.extensions.get('jury_worker')
        if registered and registered[0] == pid and registered[1].is_alive():
            return
        thread = threading.Thread(target=worker, name='jury-followups', daemon=True)
        thread.start()
        app.extensions['jury_worker'] = (pid, thread)


def register(app, services):
    probe_lock = threading.Lock()
    probe = {'checked': float('-inf'), 'ready': False}

    @app.before_request
    def ensure_jury_worker():
        # Also support WSGI hosts that don't load this project's Gunicorn hook.
        start(app, services)

    @app.get('/healthz/jury-sync')
    def jury_sync_health():
        # Probe only the authenticated handshake. No access to the sessions file
        # and no delivery side effects. Bound traffic from repeated health checks.
        with probe_lock:
            if time.monotonic() - probe['checked'] >= 60:
                key = integration_key()
                try:
                    ready = bool(key) and requests.head(DESTINATION, headers={'Authorization': 'Bearer ' + key},
                                                        timeout=(3, 5), allow_redirects=False).status_code == 204
                except requests.RequestException:
                    ready = False
                probe.update(ready=ready, checked=time.monotonic())
        return '', 204 if probe['ready'] else 503, {'Cache-Control': 'no-store'}

    def back(sid):
        return redirect(url_for('session_detail', sid=sid, _anchor='jury-section'))

    def training_for(data, sid):
        row = services.find_session(data, sid)
        if not row:
            abort(404)
        return row

    @app.post('/sessions/<sid>/jury/preview')
    def preview_jury(sid):
        data = services.load_sessions()
        training = training_for(data, sid)
        ids = list(dict.fromkeys(request.form.getlist('jury_ids')))
        channels = [ch for ch in CHANNELS if ch in request.form.getlist('channels')]
        if not ids or not channels or closed(services, training, utcnow()):
            flash('Sélectionnez un juré et un canal pour une session dont l’examen est à venir.', 'error')
            return back(sid)
        previews, signed = [], []
        for jid in ids:
            item = draft(services, data, training, jid, channels, secrets.token_urlsafe(24))
            if not item:
                continue
            if item['channels']:
                signed.append([jid, item['member']['token'], item['digest']])
            # Keep the actual SMS text. All buttons in the isolated email preview are inert.
            for msg in item['messages']:
                msg['html'] = re.sub(r'<a href="[^"]+"', '<a aria-disabled="true"', msg['html'])
            previews.append(item)
        if not signed:
            flash('Aucun destinataire joignable sur les canaux choisis parmi les jurés sans réponse.', 'error')
            return back(sid)
        token = serializer().dumps({'sid': sid, 'channels': channels, 'members': signed, 'id': secrets.token_hex(12)})
        return render_template('jury_preview.html', training=training, previews=previews, ticket=token), 200, {'Cache-Control': 'no-store'}

    @app.post('/sessions/<sid>/jury/notify')
    def notify_jury(sid):
        try:
            selection = serializer().loads(request.form.get('preview', ''), max_age=1800)
        except BadData:
            flash('Ouvrez un nouvel aperçu avant de confirmer l’envoi.', 'error')
            return back(sid)
        if selection['sid'] != sid:
            abort(400)
        results = []
        for jid, token, digest in selection['members']:
            with member_lock(services, sid, jid):
                data = services.load_sessions()
                training = training_for(data, sid)
                item = draft(services, data, training, jid, selection['channels'], token)
                if closed(services, training, utcnow()) or not item or not hmac.compare_digest(digest, item['digest']):
                    results.append('Sélection déjà traitée ou modifiée. Actualisez l’aperçu.')
                    continue
                member = item['member']
                outcomes = [CHANNELS[ch] + ' ' + deliver(services, sid, member, 'invitation', ch, item['messages'][0],
                                                         selection['id'], utcnow()) for ch in item['channels']]
                results.append(f"{member.get('prenom', '')} {member.get('nom', '')} · " + ' / '.join(outcomes))
        flash(' | '.join(results), 'success' if any(' envoyé' in r for r in results) else 'error')
        return back(sid)

    @app.route('/jury-response/<sid>/<jid>/<response>', methods=['GET', 'POST'])
    def jury_response(sid, jid, response):
        if response not in ('present', 'absent'):
            abort(400)
        token = request.args.get('token') or ''
        def resolve(data):
            row = training_for(data, sid)
            member = assigned(row, jid)
            if not member or not member.get('token') or not hmac.compare_digest(str(member['token']).encode(), token.encode()):
                abort(403)
            return row, member
        if request.method == 'POST':
            with member_lock(services, sid, jid):
                def record(data):
                    row, member = resolve(data)
                    already = member.get('status') in ('present', 'absent')
                    if not already:
                        member.update(status=response, responded_at=utcnow().isoformat())
                        if response == 'present':
                            member['jury_sync'] = {'status': 'pending'}
                    return row, member, already
                row, member, already = edit(services, record)
                if needs_sync(services, row, member, utcnow()):
                    sync_member(services, row, member, utcnow())
        else:
            row, member = resolve(services.load_sessions())
            already = member.get('status') in ('present', 'absent')
        choosing = request.method == 'GET' and not already
        return render_template('jury_response.html', title='Réponse jury', choosing=choosing, session=row, jury=member,
                               response=member['status'] if already else response, already_responded=already), 200, {
                                   'Cache-Control': 'no-store', 'Referrer-Policy': 'no-referrer'}

    def check_admin_nonce():
        csrf = session.get('jury_link_nonce') or ''
        if not csrf or not hmac.compare_digest(csrf.encode(), (request.form.get('csrf') or '').encode()):
            abort(403)

    @app.post('/sessions/<sid>/jury/<jid>/synchroniser')
    def retry_jury_sync(sid, jid):
        check_admin_nonce()
        with member_lock(services, sid, jid):
            row = training_for(services.load_sessions(), sid)
            member = assigned(row, jid)
            if not member or member.get('status') != 'present':
                abort(404)
            result = member.get('jury_sync') or {}
            if result.get('status') != 'synced':
                result = sync_member(services, row, member, utcnow())
        if result['status'] == 'synced':
            flash('Présence enregistrée dans Organisation et jury.', 'success')
        else:
            flash(result['error'], 'error')
        return back(sid)

    @app.post('/sessions/<sid>/jury/association')
    def link_jury_session(sid):
        check_admin_nonce()
        try:
            target = services.parse_source_session(request.form.get('target'))
        except ValueError as exc:
            flash(str(exc), 'error')
            return back(sid)
        def change(data):
            row = training_for(data, sid)
            row['jury_target_id'] = target
            for member in row.get('jurys', []):
                if member.get('status') == 'present' and (member.get('jury_sync') or {}).get('status') != 'synced':
                    member['jury_sync'] = {'status': 'pending'}
        edit(services, change)
        flash('Association enregistrée. Les présences en attente seront transmises au prochain passage.', 'success')
        return back(sid)
