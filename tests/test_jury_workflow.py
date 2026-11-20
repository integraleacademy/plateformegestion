from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from html import unescape
import re
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


def preview(client, channels=('email', 'sms')):
    response = client.post(ROOT + '/preview', data={'jury_ids': ['j1'], 'channels': list(channels)})
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
    assert 'href=&#34;#apercu&#34;' in html
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
    scan(NOW + timedelta(minutes=5))
    scan(NOW + timedelta(minutes=16))
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
