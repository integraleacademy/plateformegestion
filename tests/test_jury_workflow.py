from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import unescape
import os
from pathlib import Path
import re
import runpy
from unittest.mock import Mock

import pytest

import app
from services import jury_workflow as flow


NOW = datetime(2027, 3, 27, 11, tzinfo=timezone.utc)
CONTACT = dict(id='j1', prenom='Camille', nom='EXEMPLE', email='jury@example.test', telephone='0600000000')
ROOT = '/sessions/S/jury'


@pytest.fixture
def case(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'SESSIONS_FILE', str(tmp_path / 'sessions.json'))
    monkeypatch.setattr(app, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(flow, 'utcnow', lambda: NOW)
    monkeypatch.setenv('RENDER_EXTERNAL_URL', 'https://plateformegestion.example.test')
    monkeypatch.setenv('JURY_SYNC_TOKEN', 'fixture-key')
    row = dict(id='S', formation='APS', date_debut='2027-03-01', date_fin='2027-06-03',
               date_exam='2027-06-04', jurys=[], steps=[])
    app.save_sessions(dict(sessions=[row], jurys=[deepcopy(CONTACT)]))
    email = Mock(return_value=(True, None))
    sms = Mock(return_value=(True, None))
    api = Mock(return_value=Mock(status_code=200, json=lambda: {'ok': True, 'session_id': 'destination'}))
    monkeypatch.setattr(app, 'send_email', email)
    monkeypatch.setattr(app, 'deliver_jury_sms', sms)
    monkeypatch.setattr(flow.requests, 'post', api)
    client = app.app.test_client()
    with client.session_transaction() as auth:
        auth.update(admin_logged=True, admin_session_version=app.ADMIN_SESSION_VERSION)
    return client, email, sms, api


def preview(client, channels=('email', 'sms'), exam=''):
    response = client.post(ROOT + '/preview', data={'jury_ids': ['j1'], 'channels': list(channels), 'examen': exam})
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    ticket = unescape(re.search(r'name="preview" value="([^"]+)"', html)[1])
    return html, ticket


def invite(client, channels=('email', 'sms')):
    _, ticket = preview(client, channels)
    assert client.post(ROOT + '/notify', data={'preview': ticket}).status_code == 302
    return ticket


def snapshot():
    return app.load_sessions()['sessions'][0]


def scan(now):
    with app.app.app_context():
        flow.scan(app, now)


def test_preview_uses_actual_prepared_content_no_delivery_and_replay_is_harmless(case):
    client, email, sms, _ = case
    html, ticket = preview(client)
    assert 'E-mail' in html and 'jury@example.test' in html and '0600000000' in html
    assert 'Dernier rappel pour le jury' in html and '<iframe sandbox=""' in html
    assert unescape(html).count('>Bonjour Camille,</p>') == 3
    assert 'aria-disabled=&#34;true&#34;' in html and 'href=&#34;https://plateformegestion' not in html
    assert not snapshot()['jurys']
    client.post(ROOT + '/notify', data={'jury_ids': ['j1']})
    email.assert_not_called()
    sms.assert_not_called()
    for _ in range(2):
        client.post(ROOT + '/notify', data={'preview': ticket})
    email.assert_called_once()
    sms.assert_called_once()
    assert sms.call_args.args[1] in unescape(html)
    assert email.call_args.args[1] in unescape(html)
    assert 'href="https://plateformegestion.example.test/jury-response/S/j1/present' in email.call_args.args[2]
    member, = snapshot()['jurys']
    assert member['notified_at'] == NOW.isoformat()
    assert member['invited_channels'] == ['email', 'sms']


def test_changed_contact_invalidates_preview(case):
    client, email, sms, _ = case
    _, ticket = preview(client)
    data = app.load_sessions()
    data['jurys'][0]['email'] = 'changed@example.test'
    app.save_sessions(data)
    client.post(ROOT + '/notify', data={'preview': ticket})
    email.assert_not_called()
    sms.assert_not_called()


def test_24_and_48_real_elapsed_hours_single_delivery_per_channel(case):
    client, email, sms, _ = case
    invite(client)
    for delta in (23.99, 24, 24, 47.99, 48, 48, 90):
        scan(NOW + timedelta(hours=delta))
        count = 1 + int(delta >= 24) + int(delta >= 48)
        assert email.call_count == sms.call_count == count
    assert 'Dernier rappel' in email.call_args.args[1]
    assert all('>Bonjour Camille,</p>' in call.args[2] for call in email.call_args_list)


@pytest.mark.parametrize('answer', ['present', 'absent'])
def test_read_only_response_link_and_stop_after_personal_confirmation(case, answer):
    client, email, sms, api = case
    invite(client, ('sms',))
    member, = snapshot()['jurys']
    path = f"/jury-response/S/j1/{answer}?token={member['token']}"
    assert client.get(path).status_code == 200
    assert client.head(path).status_code == 200
    assert snapshot()['jurys'][0]['status'] == 'pending'
    api.assert_not_called()
    scan(NOW + timedelta(hours=24))
    assert sms.call_count == 2
    assert client.post(path).status_code == 200
    assert client.post(path).status_code == 200
    scan(NOW + timedelta(hours=49))
    assert sms.call_count == 2
    email.assert_not_called()
    assert api.call_count == (answer == 'present')
    if answer == 'present':
        assert snapshot()['jurys'][0]['jury_sync']['target_id'] == 'destination'
        assert api.call_args.kwargs['json']['member']['first_name'] == 'Camille'
        assert api.call_args.kwargs['headers'] == {'Authorization': 'Bearer fixture-key'}


def test_legacy_invitations_and_partial_reminders_retry_independently(case):
    _, email, sms, _ = case
    data = app.load_sessions()
    # France switches to summer time overnight. The old timestamp is Paris local time.
    data['sessions'][0]['jurys'] = [{**CONTACT, 'notified_at': '2027-03-27 12:00:00', 'status': 'pending', 'token': 'old'}]
    app.save_sessions(data)
    sms.side_effect = [(False, 'SMS HTTP 429'), (True, None), (True, None)]
    scan(NOW + timedelta(hours=24))
    scan(NOW + timedelta(hours=24, minutes=15))
    assert (email.call_count, sms.call_count) == (1, 1)
    scan(NOW + timedelta(hours=24, minutes=30))
    assert (email.call_count, sms.call_count) == (1, 2)
    scan(NOW + timedelta(hours=48, minutes=30))
    assert (email.call_count, sms.call_count) == (2, 3)


def test_existing_present_retries_sync_and_worker_never_sends_to_unsolicited_jurors(case):
    client, email, sms, api = case
    data = app.load_sessions()
    data['sessions'][0]['jurys'] = [{**CONTACT, 'status': 'present'}, {**CONTACT, 'id': 'j2', 'status': 'pending'}]
    app.save_sessions(data)
    api.side_effect = [flow.requests.Timeout(), Mock(status_code=200, json=lambda: {'ok': True, 'session_id': 'destination'})]
    scan(NOW)
    assert snapshot()['jurys'][0]['jury_sync']['status'] == 'pending'
    scan(NOW + timedelta(seconds=59))
    assert api.call_count == 1
    scan(NOW + timedelta(minutes=1))
    assert snapshot()['jurys'][0]['jury_sync']['target_id'] == 'destination'
    scan(NOW + timedelta(days=3))
    assert api.call_count == 2 and email.call_count == sms.call_count == 0


def test_concurrent_workers_send_once_and_card_distinguishes_added_from_invited(case):
    client, email, sms, _ = case
    invite(client, ('email',))
    data = app.load_sessions()
    data['sessions'][0]['jurys'].append({**CONTACT, 'id': 'never-invited', 'status': 'pending'})
    app.save_sessions(data)
    with ThreadPoolExecutor(2) as workers:
        list(workers.map(scan, [NOW + timedelta(hours=24)] * 2))
    assert email.call_count == 2 and not sms.called
    html = client.get('/sessions?statut=toutes').get_data(as_text=True)
    assert '<b>1</b> en attente de réponse' in html
    assert 'Jurys 0/2 présents' in html


def test_outage_paces_overdue_messages_and_respects_closed_sessions(case):
    client, email, _, _ = case
    invite(client, ('email',))
    scan(NOW + timedelta(hours=60))
    scan(NOW + timedelta(hours=60, minutes=2))
    assert email.call_count == 2
    data = app.load_sessions()
    data['sessions'][0]['archived'] = True
    app.save_sessions(data)
    scan(NOW + timedelta(hours=90))
    assert email.call_count == 2


def test_admin_retry_only_transfers_a_confirmed_member_once(case):
    client, email, sms, api = case
    data = app.load_sessions()
    data['sessions'][0]['jurys'] = [
        {**CONTACT, 'status': 'present', 'jury_sync': {'status': 'pending', 'at': NOW.isoformat()}},
        {**CONTACT, 'id': 'j2', 'status': 'pending'},
    ]
    app.save_sessions(data)
    with client.session_transaction() as auth:
        auth['jury_link_nonce'] = 'example'
    path = ROOT + '/j1/synchroniser'
    assert client.post(path).status_code == 403
    assert client.post(ROOT + '/j2/synchroniser', data={'csrf': 'example'}).status_code == 404
    api.assert_not_called()
    for _ in range(2):
        assert client.post(path, data={'csrf': 'example'}).status_code == 302
    assert snapshot()['jurys'][0]['jury_sync']['target_id'] == 'destination'
    api.assert_called_once()
    email.assert_not_called()
    sms.assert_not_called()


def test_locks_are_released_even_if_a_fork_copied_the_descriptor(case, monkeypatch):
    original_flock = flow.fcntl.flock
    copies = []

    def keep_descriptor(file, operation):
        original_flock(file, operation)
        if operation & flow.fcntl.LOCK_EX:
            copies.append((os.dup(file.fileno()), file.name))

    monkeypatch.setattr(flow.fcntl, 'flock', keep_descriptor)
    def fail_scan(_services):
        raise RuntimeError('interrupted scan')
    monkeypatch.setattr(flow, 'scan', fail_scan)
    try:
        with pytest.raises(RuntimeError, match='interrupted scan'):
            flow.scan_once(app.app, app)
        with flow.member_lock(app, 'S', 'j1'):
            pass
        assert len(copies) == 2
        for _, path in copies:
            with open(path, 'a') as independent:
                original_flock(independent, flow.fcntl.LOCK_EX | flow.fcntl.LOCK_NB)
    finally:
        for duplicate, _ in copies:
            os.close(duplicate)


def test_gunicorn_starts_one_scanner_per_serving_process(case, monkeypatch):
    threads = Mock()
    monkeypatch.setattr(app, 'IS_RENDER', True)
    monkeypatch.setattr(flow.threading, 'Thread', threads)
    monkeypatch.delitem(app.app.extensions, 'jury_worker', raising=False)
    conf = runpy.run_path(str(Path(app.__file__).with_name('gunicorn.conf.py')))
    threads.assert_not_called()
    conf['post_worker_init'](Mock())
    case[0].get('/healthz')
    threads.return_value.start.assert_called_once()


@pytest.fixture
def afc(case):
    data = app.load_sessions()
    row = data['sessions'][0]
    row.update(formation='AFC_APS_SSIAP', date_exam='2027-04-20', afcAttendanceSourceSessionId='destination',
               apsPlanningData=[{'date': '2027-04-02', 'slots': [{'afcCategory': 'EXAM_APS'}] * 2},
                                {'date': '2027-04-20', 'slots': [{'category': 'EXAM_SSIAP1'}]}])
    app.save_sessions(data)
    return case


def test_two_afc_invitations_answers_and_reminders_are_independent(afc):
    client, email, sms, api = afc
    data = {'jury_ids': ['j1'], 'channels': ['email']}
    assert client.post(ROOT + '/preview', data=data).status_code == 400
    for key, level, date in [('aps', 'APS', '02/04/2027'), ('ssiap1', 'SSIAP 1', '20/04/2027')]:
        html, ticket = preview(client, exam=key)
        assert level + ' · AFC France Travail · ' + date in unescape(html)
        assert client.post(ROOT + '/notify', data={'preview': ticket}).status_code == 302
        assert level in sms.call_args.args[1] and date in sms.call_args.args[1]
        assert 'examen=' + key in sms.call_args.args[1]
    assert email.call_count == sms.call_count == 2
    scopes = snapshot()['afc_exam_jurys']
    token_aps, token_ssiap = (scopes[k][0]['token'] for k in ('aps', 'ssiap1'))
    assert token_aps != token_ssiap
    route = '/jury-response/S/j1/present'
    assert client.post(route, query_string={'token': token_aps, 'examen': 'ssiap1'}).status_code == 403
    response = client.post(route, query_string={'token': token_aps, 'examen': 'aps'})
    assert response.status_code == 200 and '02/04/2027' in response.get_data(as_text=True)
    selector = api.call_args.kwargs['json']['session']
    assert selector['level'] == 'APS' and selector['exam_date'] == '2027-04-02' and selector['target_id'] == 'destination'
    scan(NOW + timedelta(hours=24))
    scan(NOW + timedelta(hours=48))
    assert email.call_count == sms.call_count == 4
    for call in sms.call_args_list[2:]:
        assert 'SSIAP 1' in call.args[1] and '20/04/2027' in call.args[1]
    assert client.post('/jury-response/S/j1/absent', query_string={'token': token_ssiap, 'examen': 'ssiap1'}).status_code == 200
    scopes = snapshot()['afc_exam_jurys']
    assert scopes['aps'][0]['status'] == 'present' and scopes['ssiap1'][0]['status'] == 'absent'
    assert api.call_count == 1
    assert client.post(ROOT + '/j1/delete').status_code == 400
    assert client.post(ROOT + '/j1/delete', data={'examen': 'ssiap1'}).status_code == 302
    scopes = snapshot()['afc_exam_jurys']
    assert len(scopes['aps']) == 1 and scopes['ssiap1'] == []


def test_afc_migration_pins_legacy_members_and_preserves_their_links(afc):
    client, email, sms, api = afc
    data = app.load_sessions()
    row = data['sessions'][0]
    row['jurys'] = [{**CONTACT, 'status': 'pending', 'token': 'original', 'notified_at': NOW.isoformat()},
                    {**CONTACT, 'id': 'j2', 'status': 'present', 'token': 'confirmed',
                     'jury_sync': {'status': 'synced', 'target_id': 'destination'}},
                    {**CONTACT, 'id': 'j3', 'status': 'pending', 'token': 'never-invited'}]
    app.save_sessions(data)
    flow.migrate_afc_jurys(app)
    flow.migrate_afc_jurys(app)
    row = snapshot()
    assert row['jurys'] == [] and row['afc_exam_jurys']['aps'] == []
    assert [m['id'] for m in row['afc_exam_jurys']['ssiap1']] == ['j1', 'j2']
    assert row['afc_exam_jurys']['ssiap1'][1]['jury_sync']['status'] == 'synced'
    html = client.get('/sessions/S').get_data(as_text=True)
    assert 'Notifier le jury APS' in html and 'Notifier le jury SSIAP 1' in html and 'Jurés à rattacher' in html
    with client.session_transaction() as auth:
        nonce = auth['jury_link_nonce']
    client.post(ROOT + '/j3/affecter', data={'csrf': nonce, 'examen': 'aps'})
    assert [m['id'] for m in snapshot()['afc_exam_jurys']['aps']] == ['j3']
    assert client.post('/jury-response/S/j1/present?token=original').status_code == 200
    selector = api.call_args.kwargs['json']['session']
    assert selector['level'] == 'SSIAP 1' and selector['exam_date'] == '2027-04-20'
    email.assert_not_called()
    sms.assert_not_called()


def test_afc_missing_or_ambiguous_dates_do_not_choose_an_exam(afc):
    client, email, sms, api = afc
    data = app.load_sessions()
    row = data['sessions'][0]
    row['apsPlanningData'] = [{'date': row['date_exam'], 'slots': [{'uv': 'EXAM_APS'}, {'uv': 'EXAM_SSIAP1'}]}]
    row['jurys'] = [{**CONTACT, 'status': 'present', 'token': 'legacy'}]
    app.save_sessions(data)
    flow.migrate_afc_jurys(app)
    assert snapshot()['afc_exam_jurys']['unassigned'][0]['id'] == 'j1'
    scan(NOW)
    data = app.load_sessions()
    data['sessions'][0]['apsPlanningData'] = []
    app.save_sessions(data)
    r = client.post(ROOT + '/preview', data={'jury_ids': ['j1'], 'channels': ['email'], 'examen': 'aps'})
    assert r.status_code == 302
    api.assert_not_called()
    email.assert_not_called()
    sms.assert_not_called()


def test_afc_changed_date_invalidates_an_existing_preview(afc):
    client, email, sms, _ = afc
    _, ticket = preview(client, exam='aps')
    data = app.load_sessions()
    data['sessions'][0]['apsPlanningData'][0]['date'] = '2027-04-04'
    app.save_sessions(data)
    client.post(ROOT + '/notify', data={'preview': ticket})
    email.assert_not_called()
    sms.assert_not_called()


def test_same_contact_can_be_added_to_both_afc_juries(afc):
    client, email, sms, _ = afc
    fields = {key: CONTACT[key] for key in ('nom', 'prenom', 'email', 'telephone')}
    for key in ('aps', 'ssiap1', 'aps'):
        assert client.post(ROOT + '/add', data={**fields, 'examen': key}).status_code == 302
    groups = snapshot()['afc_exam_jurys']
    assert [m['id'] for m in groups['aps']] == [m['id'] for m in groups['ssiap1']] == ['j1']
    assert groups['aps'][0]['token'] != groups['ssiap1'][0]['token']
    email.assert_not_called()
    sms.assert_not_called()
