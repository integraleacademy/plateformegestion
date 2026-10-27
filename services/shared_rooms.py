"""Shared room reservations; no trainee information leaves this application."""
from contextlib import contextmanager
from datetime import date, timedelta
import hashlib
import hmac
import json
import logging
import os
import re
import secrets

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


def projection_v1(row):
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


def session_metadata(row):
    planning = row.get('a3pPlanningData') if row.get('formation') == 'A3P' else row.get('apsPlanningData')
    days, exams = [], set()
    for day in planning or []:
        for slot in day.get('slots') or []:
            modality = str(slot.get('modality') or day.get('modality') or '').lower().replace('-', '').replace('_', '')
            if modality in ('elearning','distanciel','remote','distance'):
                continue
            exam_code=any(str(slot.get(k) or '').upper().startswith('EXAM') for k in ('uv','part','category','afcCategory','title'))
            if day.get('exam') or day.get('isExam') or slot.get('exam') or modality in ('exam','examen') or exam_code:
                exams.add(day['date'])
            else:
                days.append(day['date'])
    embedded=sorted(exams)
    for key in ('date_exam','exam_date'):
        if row.get(key):
            exams.add(date.fromisoformat(row[key]).isoformat())
            break
    config = row.get('sharedRoom') or {}
    formation = str(row.get('formation') or '').upper()
    code = 'DESP' if formation in ('DIRIGEANT','DESP') else 'SSIAP' if formation.startswith('SSIAP') else 'APS' if formation=='AFC_APS_SSIAP' else formation
    start = min(days) if days else config.get('presence_start') or row.get('despPresentielStart') or row.get('date_presentiel_debut')
    end = max(days) if days else config.get('presence_end') or row.get('despPresentielEnd') or row.get('date_presentiel_fin') or row.get('date_fin')
    if not start and not planning and (code in ('A3P','SSIAP') or row.get('apsPlanningMode')=='full_presentiel'):
        start = row.get('date_debut')
    return dict(name=row.get('display_name') or row.get('name') or row.get('nom') or formation or 'Session',
                formation=code, start=start, end=end, formation_start=row.get('date_debut'),
                exam_dates=sorted(exams),embedded_exam_dates=embedded,assignment=config.get('assignment',''))


def projection(row):
    """v2: actual presence plus exams; legacy hash permits a guarded upgrade."""
    old = projection_v1(row)
    metadata = session_metadata(row)
    config = row.get('sharedRoom') or {}
    planning = row.get('a3pPlanningData') if row.get('formation')=='A3P' else row.get('apsPlanningData')
    slots = [dict(s) for s in old['slots']]
    if planning:
        slots=[]
        for day in planning:
            for slot in day.get('slots') or []:
                modality=str(slot.get('modality') or day.get('modality') or '').lower().replace('-','').replace('_','')
                if modality in ('elearning','distanciel','remote','distance'):continue
                name=physical_name(slot.get('room') or day.get('room') or row.get('salle') or row.get('room'))
                room={'room_id':config['room_id']} if config.get('room_id') else {'room_name':name} if name else {}
                if room:slots.append(dict(date=day['date'],start=clock(slot.get('start')),end=clock(slot.get('end'),True),**room))
    # Without a detailed timetable, an explicit presence range replaces the
    # old whole-formation range. Unknown existing ranges remain conservative.
    if not planning and metadata['start'] and metadata['end'] and slots:
        first,last=map(date.fromisoformat,(metadata['start'],metadata['end']))
        if not 0 <= (last-first).days <= 1100:
            raise RoomError('Complétez les dates du présentiel.')
        room={key:slots[0][key] for key in ('room_id','room_name') if key in slots[0]}
        start,end=(clock(config.get('start','08:00')),clock(config.get('end','18:00'),True)) if config else ('00:00','24:00')
        weekdays=config.get('weekdays',[0,1,2,3,4]) if config else list(range(7))
        slots=[dict(date=(first+timedelta(days=n)).isoformat(),start=start,end=end,**room)
               for n in range((last-first).days+1) if (first+timedelta(days=n)).weekday() in weekdays]
    represented_exams=set()
    for day in planning or []:
        if day['date'] in metadata['embedded_exam_dates'] and any(s['date']==day['date'] for s in slots):
            represented_exams.add(day['date'])
    assumed=[]
    for exam in metadata['exam_dates']:
        if exam in represented_exams:
            continue
        name=physical_name(row.get('exam_room') or row.get('ssiapExamRoom') or row.get('salle') or row.get('room') or row.get('a3pRoom'))
        room={'room_id':config['room_id']} if config.get('room_id') else {'room_name':name} if name else {}
        if not room and slots:
            previous=sorted(slots,key=lambda s:s['date'])[-1]
            room={key:previous[key] for key in ('room_id','room_name') if key in previous}
        if not room:
            continue
        start=row.get('exam_start_time') or row.get('ssiapExamStartTime')
        end=row.get('exam_end_time') or row.get('ssiapExamEndTime')
        if not start or not end:
            start,end='00:00','24:00';assumed.append(exam)
        # A separate exam is reserved even outside the training period and
        # irrespective of the selected teaching weekdays.
        slots.append(dict(date=exam,start=clock(start),end=clock(end,True),**room))
    metadata['exam_full_day']=assumed
    canonical=dict(owner=old['owner'],title=metadata['name'],slots=sorted(slots,key=lambda s:json.dumps(s,sort_keys=True)),metadata=metadata)
    revision=hashlib.sha256(json.dumps(canonical,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return dict(canonical,revision=revision,legacy_revision=old['revision'],schema=2)


def empty_projection(item):
    empty = dict(owner=item['owner'], title=item['title'], slots=[],metadata=item.get('metadata',{}))
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
            result = call('prepare', dict(new, previous_revision=old['revision'],previous_projection=old))
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
                                 **{key:p['metadata'][key] for key in ('start','end','formation_start','formation','exam_dates','exam_full_day')},
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
            config=dict(room_id=rid,start=start,end=end,weekdays=weekdays,assignment=secrets.token_urlsafe(16))
            if not (row.get('a3pPlanningData') or row.get('apsPlanningData')):
                metadata=session_metadata(row)
                try:
                    first=date.fromisoformat(payload.get('presence_start') or metadata['start'])
                    last=date.fromisoformat(payload.get('presence_end') or metadata['end'])
                except (ValueError,TypeError):
                    raise RoomError('Précisez les dates de début et de fin du présentiel.')
                if first>last or (last-first).days>1100 or (row.get('date_debut') and first<date.fromisoformat(row['date_debut'])):
                    raise RoomError('Vérifiez les dates du présentiel.')
                config.update(presence_start=first.isoformat(),presence_end=last.isoformat())
            row['sharedRoom'] = config
            save_sessions(data)
        else:
            raise RoomError('Choisissez une session de la page Sessions.',status=400)
        return jsonify(ok=True, message='La salle est réservée pour cette session.')
