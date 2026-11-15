from copy import deepcopy
from io import BytesIO

import pytest
import requests
from openpyxl import load_workbook

import app
from services import afc_attendance_roster as roster


BASE = '/api/sessions/planning/afc-france-travail/'


def day(date, support=False):
    slots = [{'start': '08:30', 'end': '12:30', 'afcKind': 'FT'}]
    if support:
        slots.append({'start': '13:30', 'end': '15:30', 'afcKind': 'SP', 'studentIds': ['0']})
    return {'date': date, 'slots': slots}


@pytest.fixture
def case(monkeypatch):
    planning = {
        'id': 'planning', 'formation': 'AFC_APS_SSIAP', 'date_debut': '2026-11-16', 'date_fin': '2026-11-23',
        'apsAttendanceStudents': [
            {'id': 'local-a', 'lastName': 'DUPRÉ', 'firstName': 'Zoé', 'france_travail_id': 'old'},
            {'lastName': 'Retiré', 'firstName': 'Ancien'}],
        'apsPlanningData': [day('2026-11-16'), day('2026-11-18', True), day('2026-11-23')]
    }
    feed = {'ok': True, 'session': {'id': 'source', 'name': 'Session novembre'}, 'students': [
        {'id': 'new-b', 'lastName': 'Alpha', 'firstName': 'Noé', 'entryDate': '2026-11-18',
         'exitDate': '2026-11-23', 'france_travail_id': '000B', 'ranHours': 0},
        {'id': 'new-a', 'lastName': 'Dupre', 'firstName': 'Zoé', 'entryDate': '2026-11-16',
         'exitDate': '2026-11-23', 'france_travail_id': '000A', 'ranHours': 40}
    ]}
    monkeypatch.setenv('AFC_ATTENDANCE_SYNC_TOKEN', 'test-feed')
    monkeypatch.setattr(app, 'load_sessions', lambda: {'sessions': [planning]})
    monkeypatch.setattr(app, 'save_sessions', lambda _: None)
    calls = []

    class Response:
        status_code = 200
        def raise_for_status(self):
            if self.status_code != 200:
                raise requests.HTTPError()
        def json(self):
            return deepcopy(feed)

    response = Response()

    def get(url, *, params, headers, timeout, allow_redirects):
        assert url == roster.FEED_URL and headers == {'Authorization': 'Bearer test-feed'}
        assert not allow_redirects and timeout
        calls.append(params)
        return response

    monkeypatch.setattr(roster.requests, 'get', get)
    client = app.app.test_client()
    with client.session_transaction() as session:
        session.update(admin_logged=True, admin_session_version=app.ADMIN_SESSION_VERSION)
    return client, planning, feed, calls, response


def test_preview_and_direct_export_read_fresh_roster_dates_ids_and_support(case):
    client, planning, feed, calls, _ = case
    original = deepcopy(planning)
    preview = client.get(BASE + 'preview').json['preview']
    assert (preview['studentCount'], preview['missingIdCount'], preview['totalPlannedHours']) == (2, 0, 22)
    rows = client.get(BASE + 'roster').json['students']
    assert [(s['id'], s['entryDate'], s['ranHours']) for s in rows] == [
        ('new-b', '2026-11-18', 0), ('new-a', '2026-11-16', 40)]
    result = client.get(BASE + 'generate')
    assert result.status_code == 200 and 'no-store' in result.headers['Cache-Control']
    book = load_workbook(BytesIO(result.data))
    week = book.worksheets[0]
    assert (week['B14'].value, week['B16'].value) == ('000B', '000A')
    assert week['B14'].data_type == 's' and week['B14'].number_format == '@'
    assert week['C14'].fill.fill_type == 'solid' and week['C16'].fill.fill_type is None
    assert week['H15'].value is None and week['H17'].value == 2
    assert week['M19'].value == 14 and book.worksheets[1]['M19'].value == 8
    feed['students'][0].update(entryDate='2026-11-23', france_travail_id='001B')
    refreshed = load_workbook(BytesIO(client.get(BASE + 'generate').data))
    assert refreshed.worksheets[0]['B14'].value == '000A'
    assert refreshed.worksheets[1]['B14'].value == '001B'
    assert calls == [{'date_start': '2026-11-16', 'date_end': '2026-11-23'}] * 4
    assert planning == original


def test_no_names_or_identifiers_from_template_before_anyone_starts(case):
    client, planning, feed, *_ = case
    planning['apsAttendanceStudents'] = []
    for student in feed['students']:
        student['entryDate'] = '2026-11-23'
    book = load_workbook(BytesIO(client.get(BASE + 'generate').data))
    assert all(book.active.cell(row, col).value is None for row in (14, 15) for col in range(1, 14))
    assert book.worksheets[1]['B14'].value == '000B'


def test_association_resolves_before_save_and_blocks_unavailable_exports(case):
    client, planning, _, calls, response = case
    response.status_code = 404
    assert client.post(BASE + 'settings', json={'sourceSessionId': 'unknown'}).status_code == 409
    assert 'afcAttendanceSourceSessionId' not in planning
    response.status_code = 200
    url = 'https://gestionstagiaires-r5no.onrender.com/admin/sessions/source/trainees'
    assert client.post(BASE + 'settings', json={'sourceSessionId': url}).status_code == 200
    assert planning['afcAttendanceSourceSessionId'] == 'source' and calls[-1] == {'session_id': 'source'}
    for status, expected in ((409, 409), (503, 503), (403, 503)):
        response.status_code = status
        for action in ('roster', 'preview', 'generate'):
            result = client.get(BASE + action)
            assert result.status_code == expected and result.json['ok'] is False


def test_empty_remote_session_does_not_reinstate_local_students(case):
    client, _, feed, *_ = case
    feed['students'] = []
    assert client.get(BASE + 'preview').json['preview']['studentCount'] == 0
    assert client.get(BASE + 'generate').status_code == 409


def test_missing_id_reported_and_ambiguous_names_never_inherit_other_students_slots(case):
    client, _, feed, *_ = case
    feed['students'][0].update(lastName='Dupré', firstName='Zoé', france_travail_id='')
    payload = client.get(BASE + 'preview').json['preview']
    assert payload['missingIdCount'] == 1 and payload['totalPlannedHours'] == 20
    assert client.get(BASE + 'roster').json['students'][0]['france_travail_id'] == ''


def test_feed_requires_an_authenticated_platform_session_and_an_afc_training(case):
    client, planning, _, calls, _ = case
    assert app.app.test_client().get(BASE + 'roster').status_code == 302
    planning['formation'] = 'APS'
    for action in ('roster', 'preview', 'generate'):
        assert client.get(BASE + action).status_code == 403
    assert not calls


def test_edit_from_roster_updates_source_preview_and_next_workbook(case, monkeypatch):
    client, planning, feed, _, _ = case
    student = feed['students'][0]
    student['france_travail_id'] = ''
    assert client.get(BASE + 'preview').json['preview']['missingIdCount'] == 1
    original = deepcopy(planning)
    writes = []

    def patch(url, *, params, json, headers, timeout, allow_redirects):
        assert url == roster.FEED_URL and headers == {'Authorization': 'Bearer test-feed'}
        assert not allow_redirects and timeout
        assert json['sourceSessionId'] == 'source' and json['studentId'] == student['id']
        assert json['previous'] == {key: student[key] for key in json['changes']}
        writes.append(params)
        student.update(json['changes'])
        return SourceResponse(200, {'ok': True, 'student': student})

    monkeypatch.setattr(roster.requests, 'patch', patch)
    def edit(changes):
        return client.patch(BASE + 'roster/new-b', json={
            'sourceSessionId': 'source', 'studentId': 'ignore-client-override', 'changes': changes,
            'previous': {key: student[key] for key in changes}})

    result = edit({'france_travail_id': '0000123B', 'entryDate': '2026-11-23', 'ranHours': 40})
    assert result.status_code == 200 and 'no-store' in result.headers['Cache-Control']
    assert result.json['student']['france_travail_id'] == '0000123B'
    preview = client.get(BASE + 'preview').json['preview']
    assert preview['missingIdCount'] == 0 and preview['totalPlannedHours'] == 18
    assert client.get(BASE + 'roster').json['students'][0]['ranHours'] == 40
    assert planning == original
    planning['afcAttendanceSourceSessionId'] = 'source'
    assert edit({'france_travail_id': '0000124B'}).status_code == 200
    book = load_workbook(BytesIO(client.get(BASE + 'generate').data))
    assert book.active['B14'].value == '000A'
    assert (book.worksheets[1]['B14'].value, book.worksheets[1]['B14'].data_type) == ('0000124B', 's')
    assert writes == [{'date_start': planning['date_debut'], 'date_end': planning['date_fin']}, {'session_id': 'source'}]


class SourceResponse:
    def __init__(self, status, payload):
        self.status_code, self.payload = status, payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError()


def test_edit_rejects_unavailable_source_conflicts_and_out_of_scope_sessions(case, monkeypatch):
    client, planning, *_ = case
    url = BASE + 'roster/new-b'
    assert app.app.test_client().patch(url, json={}).status_code == 302
    assert client.patch(url, json=['wrong']).status_code == 400
    for code in (400, 404, 409, 403, 503):
        monkeypatch.setattr(roster.requests, 'patch', lambda *args, **kw: SourceResponse(code, {'ok': False, 'error': 'Actualisez la ligne.'}))
        result = client.patch(url, json={})
        assert result.status_code == (code if code in (400, 404, 409) else 503)
        assert result.json['ok'] is False
        if code == 409:
            assert result.json['error'] == 'Actualisez la ligne.'
    monkeypatch.setattr(roster.requests, 'patch', lambda *args, **kw: SourceResponse(200, {'ok': True, 'student': {'id': 'other'}}))
    assert client.patch(url, json={}).status_code == 503
    monkeypatch.delenv('AFC_ATTENDANCE_SYNC_TOKEN')
    assert client.patch(url, json={}).status_code == 503
    planning['formation'] = 'APS'
    assert client.patch(url, json={}).status_code == 403
    assert client.patch(url.replace('/planning/', '/absent/'), json={}).status_code == 404
