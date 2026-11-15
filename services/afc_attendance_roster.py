"""Read and update the authoritative enrolments used by the AFC attendance sheets."""
from collections import Counter
from datetime import date
import os
import re
import unicodedata

import requests


FEED_URL = 'https://gestionstagiaires-r5no.onrender.com/api/integrations/plateformegestion/afc-attendance'


class RosterUnavailable(Exception):
    def __init__(self, message, status=503):
        super().__init__(message)
        self.status = status


def name_key(row):
    def normalized(value):
        value = unicodedata.normalize('NFKD', str(value or '').casefold())
        return ''.join(c for c in value if c.isalnum())
    return (normalized(row.get('lastName') or row.get('nom')),
            normalized(row.get('firstName') or row.get('prenom')))


def source_students(local, rows):
    # Slots can reference an old local ID or a zero-based local list position.
    # The order of the remote roster must never reassign individual support.
    by_id = {str(s['id']): i for i, s in enumerate(local) if s.get('id')}
    local_names = {}
    for i, student in enumerate(local):
        local_names.setdefault(name_key(student), []).append(i)
    remote_names = Counter(name_key(s) for s in rows)
    matched_by_id = {by_id[s['id']] for s in rows if s['id'] in by_id}
    result = []
    for student in rows:
        source_id = student['id']
        key = name_key(student)
        index = by_id.get(source_id)
        if index is None and remote_names[key] == 1 and len(local_names.get(key, [])) == 1:
            name_index = local_names[key][0]
            if name_index not in matched_by_id:
                index = name_index
        aliases = [source_id]
        exit_date = student['exitDate']
        if index is not None:
            prior = local[index]
            aliases.extend([str(index), str(prior.get('id') or prior.get('studentId') or f'student-{index + 1}')])
            early_exit = prior.get('abandonDate') or prior.get('dateSortie') or prior.get('exitDate')
            if early_exit:
                exit_date = min(exit_date, date.fromisoformat(early_exit).isoformat())
        result.append({**student, 'attendanceSlotIds': aliases, 'exitDate': exit_date})
    return result


def source_query(session):
    source_id = session.get('afcAttendanceSourceSessionId')
    if source_id:
        return {'session_id': source_id}
    return {'date_start': session.get('date_debut'), 'date_end': session.get('date_fin')}


def attendance_roster(session):
    token = os.environ.get('AFC_ATTENDANCE_SYNC_TOKEN', '').strip()
    if not token:
        return session, None
    source_id = session.get('afcAttendanceSourceSessionId')
    try:
        response = requests.get(FEED_URL, params=source_query(session), headers={'Authorization': 'Bearer ' + token},
                                timeout=(15, 20), allow_redirects=False)
        if response.status_code in (404, 409):
            message = ('Plusieurs sessions AFC correspondent à ces dates.' if response.status_code == 409
                       else 'Aucune session AFC correspondante dans Gestion des stagiaires.')
            raise RosterUnavailable(message + ' Vérifiez la session source dans « Configurer France Travail ».', 409)
        response.raise_for_status()
        payload = response.json()
        if not payload['ok'] or not isinstance(payload['students'], list):
            raise ValueError('invalid roster')
        source = payload['session']
        if not isinstance(source['id'], str) or not source['id'] or (source_id and source_id != source['id']):
            raise ValueError('invalid source')
        students = payload['students']
        seen = set()
        for row in students:
            if not all(name_key(row)) or not isinstance(row['id'], str) or not row['id'] or row['id'] in seen:
                raise ValueError('invalid enrolment')
            seen.add(row['id'])
            if not isinstance(row['france_travail_id'], str) or date.fromisoformat(row['entryDate']) > date.fromisoformat(row['exitDate']):
                raise ValueError('invalid attendance data')
        resolved = source_students(session.get('apsAttendanceStudents') or [], students)
        return {**session, 'apsAttendanceStudents': resolved}, source
    except (requests.RequestException, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise RosterUnavailable('Impossible de récupérer la liste et les dates auprès de Gestion des stagiaires. Réessayez dans un instant.') from exc


def update_attendance_student(session, student_id, payload):
    token = os.environ.get('AFC_ATTENDANCE_SYNC_TOKEN', '').strip()
    if not token:
        raise RosterUnavailable('La liaison avec Gestion des stagiaires est indisponible.')
    if not isinstance(payload, dict):
        raise RosterUnavailable('Modification de stagiaire invalide.', 400)
    body = {key: payload.get(key) for key in ('sourceSessionId', 'changes', 'previous')}
    body['studentId'] = student_id
    try:
        response = requests.patch(FEED_URL, params=source_query(session), json=body,
                                  headers={'Authorization': 'Bearer ' + token},
                                  timeout=(15, 50), allow_redirects=False)
        if response.status_code in (400, 404, 409):
            message = response.json().get('error') or 'Vérifiez les données du stagiaire.'
            raise RosterUnavailable(message, response.status_code)
        response.raise_for_status()
        result = response.json()
        student = result['student']
        if (not result['ok'] or student['id'] != student_id or
                not {'france_travail_id', 'entryDate', 'ranHours'} <= student.keys()):
            raise ValueError('invalid enrolment response')
        return student
    except (requests.RequestException, KeyError, TypeError, ValueError, AttributeError) as exc:
        raise RosterUnavailable('Enregistrement non confirmé par Gestion des stagiaires. Réessayez pour vérifier la modification.') from exc


def parse_source_session(value):
    value = str(value or '').strip()
    if not value:
        return ''
    match = re.fullmatch(r'(?:https://gestionstagiaires-r5no\.onrender\.com/admin/sessions/)?([\w-]{1,100})(?:/trainees)?/?', value, re.ASCII)
    if not match:
        raise ValueError('Indiquez l’identifiant de la session source ou le lien vers sa liste de stagiaires.')
    return match.group(1)
