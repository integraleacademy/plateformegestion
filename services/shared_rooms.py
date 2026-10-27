"""Shared room reservations; no trainee information leaves this application."""
from contextlib import contextmanager
from datetime import date, timedelta
import hashlib
import hmac
import json
import logging
import os
import re

import requests
from flask import abort, jsonify, request

from services.session_storage import SessionStorageError, _locked, _read

log = logging.getLogger(__name__)


class RoomError(SessionStorageError):
    def __init__(self, message, conflicts=None, status=409):
        super().__init__(message)
        self.conflicts, self.status = conflicts or [], status


def enabled():
    return bool(os.environ.get('SHARED_ROOMS_TOKEN') and os.environ.get('BTS_ROOMS_URL'))


def call(path, data):
    if not enabled():
        raise RoomError('La liaison des salles n’est pas configurée.', status=503)
    try:
        response = requests.post(os.environ['BTS_ROOMS_URL'].rstrip('/') + '/internal/rooms/' + path,
                                 json=data, headers={'Authorization': 'Bearer ' + os.environ['SHARED_ROOMS_TOKEN']},
                                 timeout=(5, 25), allow_redirects=False)
        value = response.json()
    except (requests.RequestException, ValueError):
        raise RoomError('Le planning commun des salles est indisponible. La modification n’a pas été enregistrée.', status=503)
    if not response.ok or value.get('ok') is False:
        raise RoomError(value.get('message', 'Réservation de salle refusée.'), value.get('conflicts'),
                        409 if response.status_code == 409 else 503)
    return value


def clock(value, end=False):
    value = str(value or '').strip()
    if end and value == '24:00':
        return value
    if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', value):
        raise RoomError('Les horaires du planning doivent être complétés avant de réserver une salle.')
    return value


def physical_name(value):
    value = str(value or '').strip()
    # Addresses and generic training locations are not physical room identities.
    return value if re.match(r'^salle\s+\S', value, re.I) and len(value) <= 100 else ''


def projection(row):
    row = dict(row)
    owner = 'session:' + str(row['id'])
    title = str(row.get('nom') or row.get('formation') or 'Session') + ' · ' + str(row.get('date_debut') or '')
    config = row.get('sharedRoom') or {}
    room_id = config.get('room_id')
    slots = []
    planning = row.get('a3pPlanningData') if row.get('formation') == 'A3P' else row.get('apsPlanningData')
    if isinstance(planning, list) and planning:
        for day in planning:
            for slot in day.get('slots') or []:
                modality = str(slot.get('modality') or '').lower().replace('-', '').replace('_', '')
                if modality in ('elearning', 'distanciel', 'remote', 'distance'):
                    continue
                name = physical_name(slot.get('room') or day.get('room') or row.get('salle') or row.get('room'))
                if not room_id and not name:
                    continue
                slots.append(dict(date=date.fromisoformat(day['date']).isoformat(), start=clock(slot.get('start')),
                                  end=clock(slot.get('end'), True), **({'room_id': room_id} if room_id else {'room_name': name})))
    else:
        name = physical_name(row.get('salle') or row.get('room') or row.get('a3pRoom'))
        if room_id or name:
            try:
                first, last = date.fromisoformat(row['date_debut']), date.fromisoformat(row['date_fin'])
            except (KeyError, ValueError, TypeError):
                raise RoomError('Complétez les dates de la session avant de lui affecter une salle.')
            if not 0 <= (last-first).days <= 1100:
                raise RoomError('La période de réservation est invalide.')
            start, end = ('00:00', '24:00') if not config else (clock(config.get('start', '08:00')), clock(config.get('end', '18:00'), True))
            weekdays = list(range(7)) if not config else config.get('weekdays', [0, 1, 2, 3, 4])
            for offset in range((last-first).days+1):
                day = first + timedelta(days=offset)
                if day.weekday() in weekdays:
                    slots.append(dict(date=day.isoformat(), start=start, end=end,
                                      **({'room_id': room_id} if room_id else {'room_name': name})))
    canonical = dict(owner=owner, title=title, slots=sorted(slots, key=lambda s: json.dumps(s, sort_keys=True)))
    revision = hashlib.sha256(json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return dict(canonical, revision=revision)


def empty_projection(item):
    empty = dict(owner=item['owner'], title=item['title'], slots=[])
    return dict(empty, revision=hashlib.sha256(json.dumps(empty, sort_keys=True, ensure_ascii=False).encode()).hexdigest())


@contextmanager
def reserve_changes(changes):
    if not enabled():
        yield
        return
    tokens = []
    saving = False
    try:
        for old, new in changes:
            if old['revision'] == new['revision']:
                continue
            result = call('prepare', dict(new, previous_revision=old['revision']))
            if result.get('token'):
                tokens.append(result['token'])
        saving = True
        yield
    except BaseException:
        # A failed fsync can occur after rename: retain both sets until recovery.
        for token in ([] if saving else tokens):
            try:
                call('finish', dict(token=token, commit=False))
            except RoomError:
                log.warning('ROOM_ABORT_PENDING; rooms remain held until reconciliation')
        raise
    else:
        for token in tokens:
            try:
                call('finish', dict(token=token, commit=True))
            except RoomError:
                # The source has been durably saved. Never report a failed save
                # or release either reservation; a later locked save reconciles.
                log.warning('ROOM_COMMIT_PENDING; rooms remain held until reconciliation')


@contextmanager
def session_guard(current, candidate):
    if not enabled():
        yield
        return
    before = {str(s['id']): s for s in current['sessions']}
    after = {str(s['id']): s for s in candidate['sessions']}
    changes = []
    for sid in before.keys() | after.keys():
        if before.get(sid) == after.get(sid):
            continue
        old = projection(before[sid]) if sid in before else None
        new = projection(after[sid]) if sid in after else None
        old, new = old or empty_projection(new), new or empty_projection(old)
        changes.append((old, new))
    with reserve_changes(changes):
        yield


def register(app, load_sessions, save_sessions, sessions_file):
    def authorized():
        token = os.environ.get('SHARED_ROOMS_TOKEN', '')
        if not token or not hmac.compare_digest(request.headers.get('Authorization', ''), 'Bearer '+token):
            abort(403)

    @app.errorhandler(RoomError)
    def room_error(exc):
        if request.path.startswith('/api/') or request.is_json:
            return jsonify(ok=False, message=str(exc), conflicts=exc.conflicts), exc.status
        from flask import render_template
        return render_template('shared_room_error.html', message=str(exc), conflicts=exc.conflicts,
                               rooms_url=os.environ.get('BTS_ROOMS_URL', '').rstrip('/')+'/admin/salles'), exc.status

    @app.post('/api/shared-rooms/bootstrap')
    def bootstrap_rooms():
        authorized()
        # Prevent any source writer from slipping between snapshot and ledger seed.
        with _locked(sessions_file, exclusive=True):
            data = _read(sessions_file, False)
            owners = [projection(s) for s in data['sessions']]
            result = call('bootstrap', dict(owners=owners))
        return jsonify(ok=True, count=result['count'])

    @app.route('/api/shared-rooms/sessions', methods=['GET', 'POST'])
    def shared_room_sessions():
        authorized()
        if request.method == 'GET':
            rows = []
            with _locked(sessions_file, exclusive=True):
                data = _read(sessions_file, False)
                sources = data['sessions']
                registry = call('reconcile', dict(owners=[projection(s) for s in sources],complete=True))
            for source in sources:
                p = projection(source)
                rows.append(dict(owner=p['owner'], title=p['title'], revision=p['revision'],
                                 name=source.get('display_name') or source.get('name') or source.get('nom') or source.get('formation') or 'Session',
                                 start=source.get('date_debut'), end=source.get('date_fin'),
                                 count=len(p['slots']), assigned=bool(p['slots']),
                                 generated=bool(source.get('a3pPlanningData') or source.get('apsPlanningData')),
                                 config=source.get('sharedRoom') or {}))
            return jsonify(ok=True, sessions=rows, source='sessions', registry=registry)
        data = load_sessions()
        payload = request.get_json(silent=True) or {}
        owner = payload.get('owner', '')
        rid = payload.get('room_id')
        if not isinstance(rid, str) or not rid or len(rid) > 100:
            raise RoomError('Choisissez une salle dans le planning commun.')
        if isinstance(owner,str) and owner.startswith('session:'):
            row = next((s for s in data['sessions'] if str(s['id']) == owner[8:]), None)
            if not row or projection(row)['revision'] != payload.get('revision'):
                raise RoomError('La session a changé. Rechargez la liste.')
            start, end = clock(payload.get('start', '08:00')), clock(payload.get('end', '18:00'), True)
            weekdays = payload.get('weekdays', [0, 1, 2, 3, 4])
            if start >= end or not isinstance(weekdays, list) or not weekdays or any(type(d) is not int or d not in range(7) for d in weekdays):
                raise RoomError('Choisissez les jours et les horaires de présence.')
            row['sharedRoom'] = dict(room_id=rid, start=start, end=end, weekdays=weekdays)
            save_sessions(data)
        else:
            raise RoomError('Choisissez une session de la page Sessions.',status=400)
        return jsonify(ok=True, message='La salle est réservée pour cette session.')
